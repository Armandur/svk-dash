from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select

from app import sse as sse_registry
from app.database import get_session
from app.deps import require_admin
from app.models import Layout, LayoutZone, Screen, ScreenLayoutAssignment, View
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

    return {
        "screen": screen,
        "status": status,
        "conn_count": conn_count,
        "last_seen": last_seen_str,
    }


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
        screen = Screen(name=name, slug=slug)
        db.add(screen)
        db.commit()
        db.refresh(screen)
    return RedirectResponse(f"/admin/screens/{screen.id}", status_code=302)


def _get_screen_detail_ctx(db, screen_id: int, error: str | None = None) -> dict | None:
    screen = db.get(Screen, screen_id)
    if not screen:
        return None

    assignment = db.exec(
        select(ScreenLayoutAssignment)
        .where(ScreenLayoutAssignment.screen_id == screen_id)
        .order_by(ScreenLayoutAssignment.priority.desc())
    ).first()

    layout = None
    zones = []
    if assignment:
        layout = db.get(Layout, assignment.layout_id)
        if layout:
            zones = db.exec(
                select(LayoutZone)
                .where(LayoutZone.layout_id == layout.id)
                .order_by(LayoutZone.z_index)
            ).all()

    # Vyer utan zon-tilldelning (äldre vyer eller skärm utan layout)
    legacy_views = db.exec(
        select(View)
        .where(View.screen_id == screen_id, View.zone_id == None)  # noqa: E711
        .order_by(View.position)
    ).all()

    # Antal vyer per zon
    zone_view_counts = {}
    for zone in zones:
        zone_view_counts[zone.id] = len(db.exec(
            select(View).where(View.screen_id == screen_id, View.zone_id == zone.id)
        ).all())

    all_layouts = db.exec(select(Layout).order_by(Layout.name)).all()

    return {
        "screen": screen,
        "assignment": assignment,
        "layout": layout,
        "zones": zones,
        "zone_view_counts": zone_view_counts,
        "legacy_views": legacy_views,
        "all_layouts": all_layouts,
        "error": error,
    }


@router.get("/screens/{screen_id}", response_class=HTMLResponse)
async def screen_detail(request: Request, screen_id: int):
    with get_session() as db:
        ctx = _get_screen_detail_ctx(db, screen_id)
    if not ctx:
        return HTMLResponse("Skärmen hittades inte.", status_code=404)
    return HTMLResponse(
        templates.get_template("admin/screen_detail.html").render(
            request=request, **ctx
        )
    )


@router.post("/screens/{screen_id}/edit")
async def screen_edit(
    request: Request,
    screen_id: int,
    name: str = Form(...),
    slug: str = Form(...),
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
            ctx = _get_screen_detail_ctx(db, screen_id, error=f"Slug '{slug}' används redan.")
            return HTMLResponse(
                templates.get_template("admin/screen_detail.html").render(
                    request=request, **ctx
                ),
                status_code=422,
            )
        screen.name = name
        screen.slug = slug
        screen.updated_at = datetime.utcnow()
        db.add(screen)
        db.commit()
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/delete")
async def screen_delete(screen_id: int):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        for view in db.exec(select(View).where(View.screen_id == screen_id)).all():
            db.delete(view)
        for a in db.exec(
            select(ScreenLayoutAssignment).where(ScreenLayoutAssignment.screen_id == screen_id)
        ).all():
            db.delete(a)
        db.delete(screen)
        db.commit()
    return RedirectResponse("/admin/screens", status_code=302)


# ── Layout-tilldelning ────────────────────────────────────────────────────────

@router.post("/screens/{screen_id}/layout/assign")
async def screen_assign_layout(screen_id: int, layout_id: int = Form(...)):
    with get_session() as db:
        # Ta bort eventuell befintlig tilldelning
        for a in db.exec(
            select(ScreenLayoutAssignment).where(ScreenLayoutAssignment.screen_id == screen_id)
        ).all():
            db.delete(a)
        db.add(ScreenLayoutAssignment(screen_id=screen_id, layout_id=layout_id))
        db.commit()
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/layout/remove")
async def screen_remove_layout(screen_id: int):
    with get_session() as db:
        for a in db.exec(
            select(ScreenLayoutAssignment).where(ScreenLayoutAssignment.screen_id == screen_id)
        ).all():
            db.delete(a)
        db.commit()
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


# ── Zon-hantering ─────────────────────────────────────────────────────────────

@router.get("/screens/{screen_id}/zones/{zone_id}", response_class=HTMLResponse)
async def zone_detail(request: Request, screen_id: int, zone_id: int):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        zone = db.get(LayoutZone, zone_id)
        if not screen or not zone:
            return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)
        views = db.exec(
            select(View)
            .where(View.screen_id == screen_id, View.zone_id == zone_id)
            .order_by(View.position)
        ).all()
        assignment = db.exec(
            select(ScreenLayoutAssignment)
            .where(ScreenLayoutAssignment.screen_id == screen_id)
        ).first()
        other_zones = []
        if assignment:
            other_zones = db.exec(
                select(LayoutZone)
                .where(LayoutZone.layout_id == assignment.layout_id, LayoutZone.id != zone_id)
                .order_by(LayoutZone.z_index)
            ).all()
    return HTMLResponse(
        templates.get_template("admin/zone_detail.html").render(
            request=request, screen=screen, zone=zone, views=views, other_zones=other_zones
        )
    )


@router.post("/screens/{screen_id}/zones/{zone_id}/views/new")
async def zone_view_create(
    screen_id: int,
    zone_id: int,
    name: str = Form(...),
    duration_seconds: str = Form(""),
):
    with get_session() as db:
        existing = db.exec(
            select(View).where(View.screen_id == screen_id, View.zone_id == zone_id)
        ).all()
        position = len(existing)
        dur = int(duration_seconds) if duration_seconds.strip().isdigit() else None
        view = View(
            screen_id=screen_id,
            zone_id=zone_id,
            name=name,
            position=position,
            duration_seconds=dur,
            layout_json={"widgets": []},
        )
        db.add(view)
        db.commit()
        db.refresh(view)
    return RedirectResponse(f"/admin/views/{view.id}", status_code=302)


@router.post("/screens/{screen_id}/zones/{zone_id}/views/{view_id}/delete")
async def zone_view_delete(screen_id: int, zone_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if view and view.screen_id == screen_id:
            db.delete(view)
            db.commit()
            _reorder_views(db, screen_id, zone_id)
    return RedirectResponse(f"/admin/screens/{screen_id}/zones/{zone_id}", status_code=302)


# ── Legacy: vyer direkt under skärm (utan zon) ───────────────────────────────

@router.post("/screens/{screen_id}/views/new")
async def view_create(
    screen_id: int,
    name: str = Form(...),
    duration_seconds: str = Form(""),
):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        existing = db.exec(
            select(View).where(View.screen_id == screen_id, View.zone_id == None)  # noqa: E711
        ).all()
        position = len(existing)
        dur = int(duration_seconds) if duration_seconds.strip().isdigit() else None
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
async def view_delete(screen_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view or view.screen_id != screen_id:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        db.delete(view)
        db.commit()
        _reorder_views(db, screen_id, None)
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


# ── Flytta vy till zon (drag-and-drop + formulär) ────────────────────────────

@router.post("/screens/{screen_id}/views/{view_id}/assign-zone")
async def view_assign_zone(request: Request, screen_id: int, view_id: int):
    body = await request.json()
    zone_id = body.get("zone_id")  # int eller null
    with get_session() as db:
        view = db.get(View, view_id)
        if not view or view.screen_id != screen_id:
            return {"error": "Vy saknas"}
        old_zone = view.zone_id
        view.zone_id = int(zone_id) if zone_id is not None else None
        # Lägg sist i målzonen
        existing = db.exec(
            select(View).where(View.screen_id == screen_id, View.zone_id == view.zone_id)
        ).all()
        view.position = len([v for v in existing if v.id != view_id])
        db.add(view)
        db.commit()
        _reorder_views(db, screen_id, old_zone)
    return {"ok": True}


@router.post("/screens/{screen_id}/zones/{zone_id}/views/{view_id}/detach")
async def zone_view_detach(screen_id: int, zone_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if view and view.screen_id == screen_id and view.zone_id == zone_id:
            view.zone_id = None
            existing = db.exec(
                select(View).where(View.screen_id == screen_id, View.zone_id == None)  # noqa: E711
            ).all()
            view.position = len([v for v in existing if v.id != view_id])
            db.add(view)
            db.commit()
            _reorder_views(db, screen_id, zone_id)
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/zones/{zone_id}/views/{view_id}/move")
async def zone_view_move(screen_id: int, zone_id: int, view_id: int, target_zone_id: int = Form(...)):
    with get_session() as db:
        view = db.get(View, view_id)
        if view and view.screen_id == screen_id and view.zone_id == zone_id:
            view.zone_id = target_zone_id
            existing = db.exec(
                select(View).where(View.screen_id == screen_id, View.zone_id == target_zone_id)
            ).all()
            view.position = len([v for v in existing if v.id != view_id])
            db.add(view)
            db.commit()
            _reorder_views(db, screen_id, zone_id)
    return RedirectResponse(f"/admin/screens/{screen_id}/zones/{zone_id}", status_code=302)


def _reorder_views(db, screen_id: int, zone_id: int | None) -> None:
    views = db.exec(
        select(View)
        .where(View.screen_id == screen_id, View.zone_id == zone_id)
        .order_by(View.position)
    ).all()
    for i, v in enumerate(views):
        v.position = i
        db.add(v)
    db.commit()
