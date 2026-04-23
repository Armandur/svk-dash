import asyncio
import json
import secrets
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import select

from app.config import UPLOADS_DIR
from app.database import get_session
from app.deps import require_admin
from app.models import IcsCache, View, Widget, WidgetRevision
from app.routes.kiosk import broadcast_widget_updated
from app.services.ics_fetcher import fetch_and_cache, get_ics_urls
from app.templating import templates

_ICS_KINDS = frozenset({"ics_list", "ics_month", "ics_week", "ics_schedule"})

router = APIRouter(dependencies=[Depends(require_admin)])

WIDGET_KINDS = [
    ("ics_list", "ICS-kalender (lista)"),
    ("ics_month", "ICS-kalender (månad)"),
    ("ics_week", "ICS-kalender (vecka)"),
    ("ics_schedule", "ICS-kalender (schema/block)"),
    ("image", "Bild"),
    ("slideshow", "Bildspel"),
    ("markdown", "Markdown/text"),
    ("iframe", "Iframe"),
    ("clock", "Klocka/datum"),
    ("raw_html", "Rå HTML (admin-only)"),
    ("debug", "Debug/systemstatus"),
]

_WIDGET_KIND_LABELS = dict(WIDGET_KINDS)

_WIDGET_CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    ("Kalender", [(k, _WIDGET_KIND_LABELS[k]) for k in ("ics_list", "ics_month", "ics_week", "ics_schedule")]),
    ("Media",    [(k, _WIDGET_KIND_LABELS[k]) for k in ("image", "slideshow")]),
    ("Innehåll", [(k, _WIDGET_KIND_LABELS[k]) for k in ("markdown", "iframe", "raw_html")]),
    ("Övrigt",   [(k, _WIDGET_KIND_LABELS[k]) for k in ("clock", "debug")]),
]


@router.get("/widgets", response_class=HTMLResponse)
async def widgets_list(request: Request):
    with get_session() as db:
        widgets = db.exec(select(Widget).order_by(Widget.name)).all()
    kind_to_cat = {k: cat for cat, kinds in _WIDGET_CATEGORIES for k, _ in kinds}
    cat_buckets: dict[str, list] = {cat: [] for cat, _ in _WIDGET_CATEGORIES}
    for w in widgets:
        cat_buckets.setdefault(kind_to_cat.get(w.kind, "Övrigt"), []).append(w)
    grouped = [(cat, cat_buckets.get(cat, [])) for cat, _ in _WIDGET_CATEGORIES]
    return HTMLResponse(
        templates.get_template("admin/widgets.html").render(
            request=request, widgets=widgets, kinds=WIDGET_KINDS,
            grouped=grouped, categories=_WIDGET_CATEGORIES,
        )
    )


@router.get("/widgets/new", response_class=HTMLResponse)
async def widget_new(request: Request):
    return HTMLResponse(
        templates.get_template("admin/widget_form.html").render(
            request=request, widget=None, kinds=WIDGET_KINDS, error=None
        )
    )


@router.post("/widgets/new")
async def widget_create(
    request: Request,
    name: str = Form(...),
    kind: str = Form(...),
    config_json: str = Form("{}"),
):
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError:
        return HTMLResponse(
            templates.get_template("admin/widget_form.html").render(
                request=request,
                widget=None,
                kinds=WIDGET_KINDS,
                error="Ogiltig JSON i konfiguration.",
            ),
            status_code=422,
        )
    with get_session() as db:
        widget = Widget(
            name=name,
            kind=kind,
            config_json=config,
            edit_token=secrets.token_urlsafe(32),
        )
        db.add(widget)
        db.commit()
        db.refresh(widget)
    if kind in _ICS_KINDS:
        for url in get_ics_urls(config):
            asyncio.create_task(fetch_and_cache(widget.id, url))
    return RedirectResponse(f"/admin/widgets/{widget.id}", status_code=302)


@router.get("/widgets/{widget_id}", response_class=HTMLResponse)
async def widget_detail(request: Request, widget_id: int):
    with get_session() as db:
        widget = db.get(Widget, widget_id)
        if not widget:
            return HTMLResponse("Widgeten hittades inte.", status_code=404)
        revisions = db.exec(
            select(WidgetRevision)
            .where(WidgetRevision.widget_id == widget_id)
            .order_by(WidgetRevision.saved_at.desc())
            .limit(20)
        ).all()
        ics_caches = (
            db.exec(select(IcsCache).where(IcsCache.widget_id == widget_id)).all()
            if widget.kind in _ICS_KINDS
            else []
        )
    return HTMLResponse(
        templates.get_template("admin/widget_detail.html").render(
            request=request,
            widget=widget,
            revisions=revisions,
            kinds=WIDGET_KINDS,
            config_json=json.dumps(widget.config_json, indent=2, ensure_ascii=False),
            ics_caches=ics_caches,
        )
    )


@router.post("/widgets/{widget_id}/ics-refresh")
async def widget_ics_refresh(request: Request, widget_id: int):
    with get_session() as db:
        widget = db.get(Widget, widget_id)
        if not widget or widget.kind not in _ICS_KINDS:
            return HTMLResponse("Widgeten hittades inte.", status_code=404)
        urls = get_ics_urls(widget.config_json or {})
    for url in urls:
        asyncio.create_task(fetch_and_cache(widget_id, url))
    return RedirectResponse(f"/admin/widgets/{widget_id}", status_code=302)


@router.post("/widgets/{widget_id}/edit")
async def widget_edit(
    request: Request,
    widget_id: int,
    name: str = Form(...),
    config_json: str = Form("{}"),
):
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError:
        with get_session() as db:
            widget = db.get(Widget, widget_id)
            revisions = db.exec(
                select(WidgetRevision)
                .where(WidgetRevision.widget_id == widget_id)
                .order_by(WidgetRevision.saved_at.desc())
                .limit(20)
            ).all()
        return HTMLResponse(
            templates.get_template("admin/widget_detail.html").render(
                request=request,
                widget=widget,
                revisions=revisions,
                kinds=WIDGET_KINDS,
                config_json=config_json,
                error="Ogiltig JSON i konfiguration.",
            ),
            status_code=422,
        )

    client_ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    with get_session() as db:
        widget = db.get(Widget, widget_id)
        if not widget:
            return HTMLResponse("Widgeten hittades inte.", status_code=404)

        revision = WidgetRevision(
            widget_id=widget_id,
            config_json=widget.config_json,
            name_at_save=widget.name,
            saved_via="admin",
            editor_ip=client_ip,
            editor_user_agent=ua,
        )
        db.add(revision)

        widget.name = name
        widget.config_json = config
        widget.updated_at = datetime.utcnow()
        db.add(widget)
        db.commit()

        widget_kind = widget.kind
        _prune_revisions(db, widget_id)

    broadcast_widget_updated(widget_id)
    if widget_kind in _ICS_KINDS:
        for url in get_ics_urls(config):
            asyncio.create_task(fetch_and_cache(widget_id, url))
    return RedirectResponse(f"/admin/widgets/{widget_id}", status_code=302)


@router.post("/widgets/{widget_id}/rotate-token")
async def widget_rotate_token(request: Request, widget_id: int):
    with get_session() as db:
        widget = db.get(Widget, widget_id)
        if not widget:
            return HTMLResponse("Widgeten hittades inte.", status_code=404)
        widget.edit_token = secrets.token_urlsafe(32)
        widget.updated_at = datetime.utcnow()
        db.add(widget)
        db.commit()
    return RedirectResponse(f"/admin/widgets/{widget_id}", status_code=302)


@router.post("/widgets/{widget_id}/revert/{revision_id}")
async def widget_revert(request: Request, widget_id: int, revision_id: int):
    with get_session() as db:
        widget = db.get(Widget, widget_id)
        revision = db.get(WidgetRevision, revision_id)
        if not widget or not revision or revision.widget_id != widget_id:
            return HTMLResponse("Hittades inte.", status_code=404)

        save_revision = WidgetRevision(
            widget_id=widget_id,
            config_json=widget.config_json,
            name_at_save=widget.name,
            saved_via="admin",
            editor_ip=request.client.host if request.client else None,
            editor_user_agent=request.headers.get("user-agent"),
        )
        db.add(save_revision)

        widget.config_json = revision.config_json
        widget.name = revision.name_at_save
        widget.updated_at = datetime.utcnow()
        db.add(widget)
        db.commit()
        _prune_revisions(db, widget_id)

    broadcast_widget_updated(widget_id)
    return RedirectResponse(f"/admin/widgets/{widget_id}", status_code=302)


@router.post("/widgets/{widget_id}/delete")
async def widget_delete(request: Request, widget_id: int, force: str = Form("")):
    with get_session() as db:
        widget = db.get(Widget, widget_id)
        if not widget:
            return HTMLResponse("Widgeten hittades inte.", status_code=404)

        affected_views = _views_using_widget(db, widget_id)
        if affected_views and force != "1":
            return JSONResponse(
                {
                    "error": "Widget används i vyer",
                    "views": [{"id": v.id, "name": v.name} for v in affected_views],
                },
                status_code=409,
            )

        for view in affected_views:
            layout = view.layout_json or {"widgets": []}
            layout["widgets"] = [
                w for w in layout.get("widgets", []) if w["widget_id"] != widget_id
            ]
            view.layout_json = layout
            db.add(view)

        revisions = db.exec(
            select(WidgetRevision).where(WidgetRevision.widget_id == widget_id)
        ).all()
        for r in revisions:
            db.delete(r)
        db.flush()  # säkerställ att revisioner raderas före widgeten (FK-ordning)

        db.delete(widget)
        db.commit()

    return RedirectResponse("/admin/widgets", status_code=302)


def _views_using_widget(db, widget_id: int) -> list[View]:
    all_views = db.exec(select(View)).all()
    return [
        v
        for v in all_views
        if any(w.get("widget_id") == widget_id for w in (v.layout_json or {}).get("widgets", []))
    ]


_ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


@router.post("/uploads", response_class=JSONResponse)
async def upload_image(file: UploadFile = File(...)):
    content_type = file.content_type or ""
    ext = _ALLOWED_IMAGE_TYPES.get(content_type.split(";")[0].strip())
    if not ext:
        return JSONResponse({"error": "Filtypen stöds inte. Tillåtna: jpg, png, gif, webp, svg."}, status_code=400)
    filename = uuid.uuid4().hex + ext
    dest = Path(UPLOADS_DIR) / filename
    dest.write_bytes(await file.read())
    return JSONResponse({"path": filename, "url": f"/uploads/{filename}"})


def _prune_revisions(db, widget_id: int) -> None:
    revisions = db.exec(
        select(WidgetRevision)
        .where(WidgetRevision.widget_id == widget_id)
        .order_by(WidgetRevision.saved_at.desc())
    ).all()
    for old in revisions[20:]:
        db.delete(old)
    db.commit()
