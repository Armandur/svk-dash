from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select

from app import sse as sse_registry
from app.database import get_session
from app.deps import require_admin
from app.models import Screen, View
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])


def _screen_status(screen: Screen, now: datetime) -> dict:
    conn_count = sse_registry.connection_count(screen.id)
    if conn_count > 0:
        status = "online"
    elif screen.last_seen_at and (now - screen.last_seen_at).total_seconds() < 900:
        status = "recent"
    elif screen.last_seen_at:
        status = "offline"
    else:
        status = "never"

    last_seen_str = None
    if screen.last_seen_at:
        delta_s = int((now - screen.last_seen_at).total_seconds())
        if delta_s < 60:
            last_seen_str = "nyss"
        elif delta_s < 3600:
            last_seen_str = f"{delta_s // 60} min sedan"
        else:
            last_seen_str = f"{delta_s // 3600} tim sedan"

    return {"screen": screen, "status": status, "conn_count": conn_count, "last_seen": last_seen_str}


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    with get_session() as db:
        screens = db.exec(select(Screen).order_by(Screen.name)).all()
    now = datetime.utcnow()
    screen_statuses = [_screen_status(s, now) for s in screens]
    return HTMLResponse(
        templates.get_template("admin/index.html").render(
            request=request, screen_statuses=screen_statuses
        )
    )


@router.get("/screens")
async def screens_list():
    return RedirectResponse("/admin/", status_code=302)


@router.get("/screens/new", response_class=HTMLResponse)
async def screen_new(request: Request):
    return HTMLResponse(
        templates.get_template("admin/screen_form.html").render(
            request=request, screen=None, error=None
        )
    )


@router.post("/screens/new")
async def screen_create(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
    rotation_seconds: int = Form(30),
    aspect_ratio: str = Form("16:9"),
):
    slug = slug.strip().lower()
    with get_session() as db:
        existing = db.exec(select(Screen).where(Screen.slug == slug)).first()
        if existing:
            return HTMLResponse(
                templates.get_template("admin/screen_form.html").render(
                    request=request, screen=None, error=f"Slug '{slug}' används redan."
                ),
                status_code=422,
            )
        screen = Screen(
            name=name, slug=slug, rotation_seconds=rotation_seconds, aspect_ratio=aspect_ratio
        )
        db.add(screen)
        db.commit()
        db.refresh(screen)
    return RedirectResponse(f"/admin/screens/{screen.id}", status_code=302)


@router.get("/screens/{screen_id}", response_class=HTMLResponse)
async def screen_detail(request: Request, screen_id: int):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        views = db.exec(
            select(View).where(View.screen_id == screen_id).order_by(View.position)
        ).all()
    return HTMLResponse(
        templates.get_template("admin/screen_detail.html").render(
            request=request, screen=screen, views=views
        )
    )


@router.post("/screens/{screen_id}/edit")
async def screen_edit(
    request: Request,
    screen_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    rotation_seconds: int = Form(30),
    aspect_ratio: str = Form("16:9"),
):
    slug = slug.strip().lower()
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        conflict = db.exec(
            select(Screen).where(Screen.slug == slug, Screen.id != screen_id)
        ).first()
        if conflict:
            views = db.exec(
                select(View).where(View.screen_id == screen_id).order_by(View.position)
            ).all()
            return HTMLResponse(
                templates.get_template("admin/screen_detail.html").render(
                    request=request,
                    screen=screen,
                    views=views,
                    error=f"Slug '{slug}' används redan.",
                ),
                status_code=422,
            )
        screen.name = name
        screen.slug = slug
        screen.rotation_seconds = rotation_seconds
        screen.aspect_ratio = aspect_ratio
        screen.updated_at = datetime.utcnow()
        db.add(screen)
        db.commit()
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/delete")
async def screen_delete(request: Request, screen_id: int):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        views = db.exec(select(View).where(View.screen_id == screen_id)).all()
        for view in views:
            db.delete(view)
        db.delete(screen)
        db.commit()
    return RedirectResponse("/admin/screens", status_code=302)


# --- Views ---


@router.post("/screens/{screen_id}/views/new")
async def view_create(
    request: Request,
    screen_id: int,
    name: str = Form(...),
    duration_seconds: str = Form(""),
):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        existing = db.exec(select(View).where(View.screen_id == screen_id)).all()
        position = len(existing)
        dur = int(duration_seconds) if duration_seconds.strip() else None
        view = View(
            screen_id=screen_id,
            name=name,
            position=position,
            duration_seconds=dur,
            layout_json={"widgets": []},
        )
        db.add(view)
        db.commit()
        db.refresh(view)
    return RedirectResponse(f"/admin/views/{view.id}", status_code=302)


@router.post("/screens/{screen_id}/views/{view_id}/delete")
async def view_delete(request: Request, screen_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view or view.screen_id != screen_id:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        db.delete(view)
        db.commit()
        _reorder_views(db, screen_id)
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


def _reorder_views(db, screen_id: int) -> None:
    views = db.exec(select(View).where(View.screen_id == screen_id).order_by(View.position)).all()
    for i, v in enumerate(views):
        v.position = i
        db.add(v)
    db.commit()
