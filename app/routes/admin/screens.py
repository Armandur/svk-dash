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


def _get_screen_detail_ctx(
    db, screen_id: int, error: str | None = None, selected_id: int | None = None
) -> dict | None:
    screen = db.get(Screen, screen_id)
    if not screen:
        return None

    assignments = db.exec(
        select(ScreenLayoutAssignment)
        .where(ScreenLayoutAssignment.screen_id == screen_id)
        .order_by(ScreenLayoutAssignment.priority.desc())
    ).all()

    selected_assignment = None
    if selected_id:
        selected_assignment = next((a for a in assignments if a.id == selected_id), None)
    if not selected_assignment and assignments:
        selected_assignment = assignments[0]

    layout = None
    zones = []
    if selected_assignment:
        layout = db.get(Layout, selected_assignment.layout_id)
        if layout:
            zones = db.exec(
                select(LayoutZone)
                .where(LayoutZone.layout_id == layout.id)
                .order_by(LayoutZone.z_index)
            ).all()

    assignment_layouts = {}
    for a in assignments:
        al = db.get(Layout, a.layout_id)
        if al:
            assignment_layouts[a.id] = al

    # Vyer utan zon-tilldelning (äldre vyer eller skärm utan layout)
    legacy_views = db.exec(
        select(View)
        .where(View.screen_id == screen_id, View.zone_id == None)  # noqa: E711
        .order_by(View.position)
    ).all()

    # Antal vyer per zon
    zone_view_counts = {}
    for zone in zones:
        zone_view_counts[zone.id] = len(
            db.exec(select(View).where(View.screen_id == screen_id, View.zone_id == zone.id)).all()
        )

    all_layouts = db.exec(select(Layout).order_by(Layout.name)).all()
    assigned_layout_ids = {a.layout_id for a in assignments}

    return {
        "screen": screen,
        "assignments": assignments,
        "selected_assignment": selected_assignment,
        "assignment_layouts": assignment_layouts,
        "layout": layout,
        "zones": zones,
        "zone_view_counts": zone_view_counts,
        "legacy_views": legacy_views,
        "all_layouts": all_layouts,
        "assigned_layout_ids": assigned_layout_ids,
        "error": error,
        # Bakåtkompatibilitet för zone_detail-vyn
        "assignment": selected_assignment,
    }


@router.get("/screens/{screen_id}", response_class=HTMLResponse)
async def screen_detail(request: Request, screen_id: int, sel: int | None = None):
    with get_session() as db:
        ctx = _get_screen_detail_ctx(db, screen_id, selected_id=sel)
    if not ctx:
        return HTMLResponse("Skärmen hittades inte.", status_code=404)
    return HTMLResponse(
        templates.get_template("admin/screen_detail.html").render(request=request, **ctx)
    )


@router.post("/screens/{screen_id}/edit")
async def screen_edit(
    request: Request,
    screen_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    show_offline_banner: str | None = Form(None),
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
                templates.get_template("admin/screen_detail.html").render(request=request, **ctx),
                status_code=422,
            )
        screen.name = name
        screen.slug = slug
        screen.show_offline_banner = show_offline_banner is not None
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
        existing = db.exec(
            select(ScreenLayoutAssignment).where(
                ScreenLayoutAssignment.screen_id == screen_id,
                ScreenLayoutAssignment.layout_id == layout_id,
            )
        ).first()
        if not existing:
            count = len(
                db.exec(
                    select(ScreenLayoutAssignment).where(
                        ScreenLayoutAssignment.screen_id == screen_id
                    )
                ).all()
            )
            new_a = ScreenLayoutAssignment(
                screen_id=screen_id, layout_id=layout_id, priority=count
            )
            db.add(new_a)
            db.commit()
            db.refresh(new_a)
            return RedirectResponse(
                f"/admin/screens/{screen_id}?sel={new_a.id}", status_code=302
            )
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/layout/{assignment_id}/remove")
async def screen_remove_layout_assignment(screen_id: int, assignment_id: int):
    with get_session() as db:
        a = db.get(ScreenLayoutAssignment, assignment_id)
        if a and a.screen_id == screen_id:
            db.delete(a)
            db.commit()
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/layout/{assignment_id}/schedule")
async def screen_layout_assignment_schedule(
    screen_id: int,
    assignment_id: int,
    schedule_json: str = Form(None),
    duration_seconds: int | None = Form(None),
    transition: str = Form("fade"),
    transition_direction: str = Form("left"),
    transition_duration_ms: int = Form(700),
):
    with get_session() as db:
        a = db.get(ScreenLayoutAssignment, assignment_id)
        if not a or a.screen_id != screen_id:
            return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)
        
        if schedule_json:
            import json
            try:
                a.schedule_json = json.loads(schedule_json)
            except:
                pass
        else:
            a.schedule_json = None
            
        a.duration_seconds = duration_seconds
        a.transition = transition
        a.transition_direction = transition_direction
        a.transition_duration_ms = transition_duration_ms
        db.add(a)
        db.commit()
    return RedirectResponse(f"/admin/screens/{screen_id}?sel={assignment_id}", status_code=302)


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

        persistent_view = None
        if zone.role == "persistent":
            if views:
                persistent_view = views[0]
            else:
                # Skapa vy automatiskt första gången
                persistent_view = View(
                    screen_id=screen_id,
                    zone_id=zone_id,
                    name=zone.name,
                    position=0,
                    layout_json={"widgets": []},
                )
                db.add(persistent_view)
                db.commit()
                # commit() expirerar alla objekt — refresh de som används utanför sessionen
                db.refresh(persistent_view)
                db.refresh(zone)
                db.refresh(screen)

        assignment = db.exec(
            select(ScreenLayoutAssignment).where(ScreenLayoutAssignment.screen_id == screen_id)
        ).first()
        other_zones = []
        if assignment:
            other_zones = db.exec(
                select(LayoutZone)
                .where(LayoutZone.layout_id == assignment.layout_id, LayoutZone.id != zone_id)
                .order_by(LayoutZone.z_index)
            ).all()
        # Hämta views igen om vi committat (persistent_view-skapande expirerar allt)
        if persistent_view and persistent_view.id and not views:
            views = db.exec(
                select(View)
                .where(View.screen_id == screen_id, View.zone_id == zone_id)
                .order_by(View.position)
            ).all()

        # Beräkna zonens aspect-ratio för preview
        zone_aspect_css = "16 / 9"
        if assignment:
            layout = db.get(Layout, assignment.layout_id)
            if layout and zone.w_pct and zone.h_pct:
                _ASPECT = {"16:9": 16 / 9, "9:16": 9 / 16, "4:3": 4 / 3, "1:1": 1.0, "21:9": 21 / 9}
                sr = _ASPECT.get(layout.aspect_ratio, 16 / 9)
                zr = sr * (zone.w_pct / zone.h_pct)
                zone_aspect_css = f"{zr:.6f} / 1"

    return HTMLResponse(
        templates.get_template("admin/zone_detail.html").render(
            request=request,
            screen=screen,
            zone=zone,
            views=views,
            persistent_view=persistent_view,
            other_zones=other_zones,
            zone_aspect_css=zone_aspect_css,
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


@router.post("/screens/{screen_id}/zones/{zone_id}/settings")
async def zone_settings(
    screen_id: int,
    zone_id: int,
    rotation_seconds: int = Form(30),
    transition: str = Form("fade"),
    transition_direction: str = Form("left"),
    transition_duration_ms: int = Form(700),
):
    with get_session() as db:
        zone = db.get(LayoutZone, zone_id)
        if zone and zone.layout_id:
            zone.rotation_seconds = rotation_seconds
            zone.transition = transition
            zone.transition_direction = transition_direction
            zone.transition_duration_ms = transition_duration_ms
            db.add(zone)
            db.commit()
    return RedirectResponse(f"/admin/screens/{screen_id}/zones/{zone_id}", status_code=302)


@router.post("/screens/{screen_id}/zones/{zone_id}/views/{view_id}/delete")
async def zone_view_delete(screen_id: int, zone_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if view and view.screen_id == screen_id:
            db.delete(view)
            db.commit()
            _reorder_views(db, screen_id, zone_id)
    return RedirectResponse(f"/admin/screens/{screen_id}/zones/{zone_id}", status_code=302)


@router.post("/screens/{screen_id}/zones/{zone_id}/views/{view_id}/schedule")
async def zone_view_schedule(
    screen_id: int,
    zone_id: int,
    view_id: int,
    schedule_json: str = Form(None),
    transition: str | None = Form(None),
    transition_direction: str | None = Form(None),
    transition_duration_ms: int | None = Form(None),
):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view or view.screen_id != screen_id:
            return RedirectResponse(f"/admin/screens/{screen_id}/zones/{zone_id}", status_code=302)

        if schedule_json:
            import json
            try:
                view.schedule_json = json.loads(schedule_json)
            except:
                pass
        else:
            view.schedule_json = None

        view.transition = transition if transition else None
        view.transition_direction = transition_direction if transition_direction else None
        view.transition_duration_ms = transition_duration_ms

        db.add(view)
        db.commit()
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
async def zone_view_move(
    screen_id: int, zone_id: int, view_id: int, target_zone_id: int = Form(...)
):
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
