import json
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select

from app.database import get_session
from app.models import Widget, WidgetRevision
from app.routes.kiosk import broadcast_widget_updated
from app.templating import templates

router = APIRouter()

_NO_EDIT_TOKEN_KINDS = {"raw_html"}


def _render(template_name: str, **kwargs) -> HTMLResponse:
    content = templates.get_template(template_name).render(**kwargs)
    response = HTMLResponse(content)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get("/edit/{token}", response_class=HTMLResponse)
async def edit_get(request: Request, token: str):
    with get_session() as db:
        widget = db.exec(select(Widget).where(Widget.edit_token == token)).first()
    if not widget or widget.kind in _NO_EDIT_TOKEN_KINDS:
        return HTMLResponse("Länken är ogiltig eller har återkallats.", status_code=404)
    return _render(
        f"edit/{widget.kind}.html" if _has_custom_template(widget.kind) else "edit/generic.html",
        request=request,
        widget=widget,
        config=widget.config_json,
        config_json=json.dumps(widget.config_json, indent=2, ensure_ascii=False),
        error=None,
    )


@router.post("/edit/{token}")
async def edit_post(request: Request, token: str, config_json: str = Form(...)):
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError:
        with get_session() as db:
            widget = db.exec(select(Widget).where(Widget.edit_token == token)).first()
        if not widget:
            return HTMLResponse("Länken är ogiltig.", status_code=404)
        return _render(
            f"edit/{widget.kind}.html"
            if _has_custom_template(widget.kind)
            else "edit/generic.html",
            request=request,
            widget=widget,
            config=widget.config_json,
            config_json=config_json,
            error="Ogiltig JSON.",
        )

    client_ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    with get_session() as db:
        widget = db.exec(select(Widget).where(Widget.edit_token == token)).first()
        if not widget or widget.kind in _NO_EDIT_TOKEN_KINDS:
            return HTMLResponse("Länken är ogiltig eller har återkallats.", status_code=404)

        revision = WidgetRevision(
            widget_id=widget.id,
            config_json=widget.config_json,
            name_at_save=widget.name,
            saved_via="edit_token",
            editor_ip=client_ip,
            editor_user_agent=ua,
        )
        db.add(revision)

        widget.config_json = config
        widget.updated_at = datetime.utcnow()
        db.add(widget)
        db.commit()

        _prune_revisions(db, widget.id)

    broadcast_widget_updated(widget.id)
    response = RedirectResponse(f"/edit/{token}?saved=1", status_code=302)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _has_custom_template(kind: str) -> bool:
    import os

    return os.path.exists(f"app/templates/edit/{kind}.html")


def _prune_revisions(db, widget_id: int) -> None:
    revisions = db.exec(
        select(WidgetRevision)
        .where(WidgetRevision.widget_id == widget_id)
        .order_by(WidgetRevision.saved_at.desc())
    ).all()
    for old in revisions[20:]:
        db.delete(old)
    db.commit()
