from datetime import datetime
import json

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select, func

from app import sse as sse_registry
from app.database import get_session
from app.deps import require_admin
from app.models import Channel, ChannelLayoutAssignment, Layout, LayoutZone, Screen, View
from app.routes.admin.layouts import ASPECT_RATIOS
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/channels", response_class=HTMLResponse)
async def channels_list(request: Request):
    with get_session() as db:
        channels = db.exec(select(Channel).order_by(Channel.name)).all()
        # Count screens per channel
        screen_counts = {}
        for c in channels:
            count = db.exec(select(func.count(Screen.id)).where(Screen.channel_id == c.id)).one()
            screen_counts[c.id] = count
            
    return HTMLResponse(
        templates.get_template("admin/channels.html").render(
            request=request, channels=channels, screen_counts=screen_counts
        )
    )


@router.get("/channels/new", response_class=HTMLResponse)
async def channel_new(request: Request):
    return HTMLResponse(
        templates.get_template("admin/channel_form.html").render(
            request=request, channel=None, aspect_ratios=ASPECT_RATIOS
        )
    )


@router.post("/channels/new")
async def channel_create(
    name: str = Form(...),
    description: str = Form(""),
    aspect_ratio: str = Form("16:9"),
):
    with get_session() as db:
        channel = Channel(name=name, description=description, aspect_ratio=aspect_ratio)
        db.add(channel)
        db.commit()
        db.refresh(channel)
    return RedirectResponse(f"/admin/channels/{channel.id}", status_code=302)


def _get_channel_detail_ctx(
    db, channel_id: int, error: str | None = None, selected_id: int | None = None
) -> dict | None:
    channel = db.get(Channel, channel_id)
    if not channel:
        return None

    assignments = db.exec(
        select(ChannelLayoutAssignment)
        .where(ChannelLayoutAssignment.channel_id == channel_id)
        .order_by(ChannelLayoutAssignment.priority.desc())
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

    # Vyer utan zon-tilldelning
    legacy_views = db.exec(
        select(View)
        .where(View.channel_id == channel_id, View.zone_id == None)  # noqa: E711
        .order_by(View.position)
    ).all()

    # Antal vyer per zon
    zone_view_counts = {}
    for zone in zones:
        zone_view_counts[zone.id] = len(
            db.exec(select(View).where(View.channel_id == channel_id, View.zone_id == zone.id)).all()
        )

    all_layouts = db.exec(
        select(Layout)
        .where(Layout.aspect_ratio == channel.aspect_ratio)
        .order_by(Layout.name)
    ).all()
    assigned_layout_ids = {a.layout_id for a in assignments}
    
    # Skärmar som använder denna kanal
    screens = db.exec(select(Screen).where(Screen.channel_id == channel_id).order_by(Screen.name)).all()

    return {
        "channel": channel,
        "assignments": assignments,
        "selected_assignment": selected_assignment,
        "assignment_layouts": assignment_layouts,
        "layout": layout,
        "zones": zones,
        "zone_view_counts": zone_view_counts,
        "legacy_views": legacy_views,
        "all_layouts": all_layouts,
        "assigned_layout_ids": assigned_layout_ids,
        "screens": screens,
        "error": error,
        "aspect_ratios": ASPECT_RATIOS,
        # Bakåtkompatibilitet för zone_detail-vyn
        "assignment": selected_assignment,
    }


@router.get("/channels/{channel_id}", response_class=HTMLResponse)
async def channel_detail(request: Request, channel_id: int, sel: int | None = None):
    with get_session() as db:
        ctx = _get_channel_detail_ctx(db, channel_id, selected_id=sel)
    if not ctx:
        return HTMLResponse("Kanalen hittades inte.", status_code=404)
    return HTMLResponse(
        templates.get_template("admin/channel_detail.html").render(request=request, **ctx)
    )


@router.post("/channels/{channel_id}/edit")
async def channel_edit(
    channel_id: int,
    name: str = Form(...),
    description: str = Form(""),
    aspect_ratio: str = Form("16:9"),
):
    with get_session() as db:
        channel = db.get(Channel, channel_id)
        if not channel:
            return HTMLResponse("Kanalen hittades inte.", status_code=404)
        channel.name = name
        channel.description = description
        channel.aspect_ratio = aspect_ratio
        channel.updated_at = datetime.utcnow()
        db.add(channel)
        db.commit()
    return RedirectResponse(f"/admin/channels/{channel_id}", status_code=302)


@router.post("/channels/{channel_id}/delete")
async def channel_delete(channel_id: int):
    with get_session() as db:
        channel = db.get(Channel, channel_id)
        if not channel:
            return HTMLResponse("Kanalen hittades inte.", status_code=404)
            
        # Check if any screens are connected
        screens = db.exec(select(Screen).where(Screen.channel_id == channel_id)).all()
        if screens:
            # We should probably return an error message here, but for simplicity:
            return HTMLResponse("Kan inte radera kanal som används av skärmar.", status_code=400)
            
        for view in db.exec(select(View).where(View.channel_id == channel_id)).all():
            db.delete(view)
        for a in db.exec(
            select(ChannelLayoutAssignment).where(ChannelLayoutAssignment.channel_id == channel_id)
        ).all():
            db.delete(a)
            
        db.delete(channel)
        db.commit()
    return RedirectResponse("/admin/channels", status_code=302)


# ── Layout-tilldelning (flyttat från screens.py) ──────────────────────────────


@router.post("/channels/{channel_id}/layout/assign")
async def channel_assign_layout(channel_id: int, layout_id: int = Form(...)):
    with get_session() as db:
        channel = db.get(Channel, channel_id)
        if not channel:
            return RedirectResponse("/admin/channels", status_code=302)
            
        existing = db.exec(
            select(ChannelLayoutAssignment).where(
                ChannelLayoutAssignment.channel_id == channel_id,
                ChannelLayoutAssignment.layout_id == layout_id,
            )
        ).first()
        if not existing:
            count = len(
                db.exec(
                    select(ChannelLayoutAssignment).where(
                        ChannelLayoutAssignment.channel_id == channel_id
                    )
                ).all()
            )
            new_a = ChannelLayoutAssignment(
                channel_id=channel_id, layout_id=layout_id, priority=count
            )
            db.add(new_a)
            db.commit()
            db.refresh(new_a)
            return RedirectResponse(
                f"/admin/channels/{channel_id}?sel={new_a.id}", status_code=302
            )
    return RedirectResponse(f"/admin/channels/{channel_id}", status_code=302)


@router.post("/channels/{channel_id}/layout/{assignment_id}/remove")
async def channel_remove_layout_assignment(channel_id: int, assignment_id: int):
    with get_session() as db:
        a = db.get(ChannelLayoutAssignment, assignment_id)
        if a and a.channel_id == channel_id:
            db.delete(a)
            db.commit()
    return RedirectResponse(f"/admin/channels/{channel_id}", status_code=302)


@router.post("/channels/{channel_id}/layout/{assignment_id}/schedule")
async def channel_layout_assignment_schedule(
    channel_id: int,
    assignment_id: int,
    schedule_json: str = Form(None),
    enabled: str | None = Form(None),
    duration_seconds: str | None = Form(None),
    transition: str = Form("fade"),
    transition_direction: str = Form("left"),
    transition_duration_ms: str | None = Form(None),
):
    with get_session() as db:
        a = db.get(ChannelLayoutAssignment, assignment_id)
        if not a or a.channel_id != channel_id:
            return RedirectResponse(f"/admin/channels/{channel_id}", status_code=302)

        if schedule_json:
            try:
                a.schedule_json = json.loads(schedule_json)
            except:
                pass
        else:
            a.schedule_json = None

        a.enabled = enabled is not None
        a.duration_seconds = int(duration_seconds) if duration_seconds else None
        a.transition = transition
        a.transition_direction = transition_direction
        a.transition_duration_ms = int(transition_duration_ms) if transition_duration_ms else 700
        db.add(a)
        db.commit()
        
    # Broadcast to all screens using this channel
    with get_session() as db:
        screens = db.exec(select(Screen).where(Screen.channel_id == channel_id)).all()
        for s in screens:
            sse_registry.broadcast(s.id, {"type": "reload"})
            
    return RedirectResponse(f"/admin/channels/{channel_id}?sel={assignment_id}", status_code=302)


# ── Zon-hantering (flyttat från screens.py) ─────────────────────────────


@router.get("/channels/{channel_id}/zones/{zone_id}", response_class=HTMLResponse)
async def zone_detail(request: Request, channel_id: int, zone_id: int):
    with get_session() as db:
        channel = db.get(Channel, channel_id)
        zone = db.get(LayoutZone, zone_id)
        if not channel or not zone:
            return RedirectResponse(f"/admin/channels/{channel_id}", status_code=302)
        views = db.exec(
            select(View)
            .where(View.channel_id == channel_id, View.zone_id == zone_id)
            .order_by(View.position)
        ).all()

        persistent_view = None
        if zone.role == "persistent":
            if views:
                persistent_view = views[0]
            else:
                persistent_view = View(
                    channel_id=channel_id,
                    zone_id=zone_id,
                    name=zone.name,
                    position=0,
                    layout_json={"widgets": []},
                )
                db.add(persistent_view)
                db.commit()
                db.refresh(persistent_view)
                db.refresh(zone)
                db.refresh(channel)

        assignment = db.exec(
            select(ChannelLayoutAssignment).where(ChannelLayoutAssignment.channel_id == channel_id)
        ).first()
        other_zones = []
        if assignment:
            other_zones = db.exec(
                select(LayoutZone)
                .where(LayoutZone.layout_id == assignment.layout_id, LayoutZone.id != zone_id)
                .order_by(LayoutZone.z_index)
            ).all()
        if persistent_view and persistent_view.id and not views:
            views = db.exec(
                select(View)
                .where(View.channel_id == channel_id, View.zone_id == zone_id)
                .order_by(View.position)
            ).all()

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
            channel=channel,
            zone=zone,
            views=views,
            persistent_view=persistent_view,
            other_zones=other_zones,
            zone_aspect_css=zone_aspect_css,
        )
    )


@router.post("/channels/{channel_id}/zones/{zone_id}/views/new")
async def zone_view_create(
    channel_id: int,
    zone_id: int,
    name: str = Form(...),
    duration_seconds: str | None = Form(None),
):
    with get_session() as db:
        existing = db.exec(
            select(View).where(View.channel_id == channel_id, View.zone_id == zone_id)
        ).all()
        position = len(existing)
        dur = int(duration_seconds) if duration_seconds else None
        view = View(
            channel_id=channel_id,
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


@router.post("/channels/{channel_id}/zones/{zone_id}/settings")
async def zone_settings(
    channel_id: int,
    zone_id: int,
    rotation_seconds: str | None = Form(None),
    transition: str = Form("fade"),
    transition_direction: str = Form("left"),
    transition_duration_ms: str | None = Form(None),
):
    with get_session() as db:
        zone = db.get(LayoutZone, zone_id)
        if zone:
            zone.rotation_seconds = int(rotation_seconds) if rotation_seconds else 30
            zone.transition = transition
            zone.transition_direction = transition_direction
            zone.transition_duration_ms = int(transition_duration_ms) if transition_duration_ms else 700
            db.add(zone)
            db.commit()
    return RedirectResponse(f"/admin/channels/{channel_id}/zones/{zone_id}", status_code=302)


@router.post("/channels/{channel_id}/zones/{zone_id}/views/{view_id}/delete")
async def zone_view_delete(channel_id: int, zone_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if view and view.channel_id == channel_id:
            db.delete(view)
            db.commit()
            _reorder_views(db, channel_id, zone_id)
    return RedirectResponse(f"/admin/channels/{channel_id}/zones/{zone_id}", status_code=302)


@router.post("/channels/{channel_id}/zones/{zone_id}/views/{view_id}/schedule")
async def zone_view_schedule(
    channel_id: int,
    zone_id: int,
    view_id: int,
    schedule_json: str = Form(None),
    enabled: str | None = Form(None),
    duration_seconds: str | None = Form(None),
    transition: str | None = Form(None),
    transition_direction: str | None = Form(None),
    transition_duration_ms: str | None = Form(None),
):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view or view.channel_id != channel_id:
            return RedirectResponse(f"/admin/channels/{channel_id}/zones/{zone_id}", status_code=302)

        if schedule_json:
            try:
                view.schedule_json = json.loads(schedule_json)
            except:
                pass
        else:
            view.schedule_json = None

        view.enabled = enabled is not None
        view.duration_seconds = int(duration_seconds) if duration_seconds else None
        view.transition = transition if transition else None
        view.transition_direction = transition_direction if transition_direction else None
        view.transition_duration_ms = int(transition_duration_ms) if transition_duration_ms else None

        db.add(view)
        db.commit()
        
    # Broadcast to all screens using this channel
    with get_session() as db:
        screens = db.exec(select(Screen).where(Screen.channel_id == channel_id)).all()
        for s in screens:
            sse_registry.broadcast(s.id, {"type": "reload"})
            
    return RedirectResponse(f"/admin/channels/{channel_id}/zones/{zone_id}", status_code=302)


@router.post("/channels/{channel_id}/zones/{zone_id}/views/{view_id}/detach")
async def zone_view_detach(channel_id: int, zone_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if view and view.channel_id == channel_id and view.zone_id == zone_id:
            view.zone_id = None
            existing = db.exec(
                select(View).where(View.channel_id == channel_id, View.zone_id == None)  # noqa: E711
            ).all()
            view.position = len([v for v in existing if v.id != view_id])
            db.add(view)
            db.commit()
            _reorder_views(db, channel_id, zone_id)
    return RedirectResponse(f"/admin/channels/{channel_id}", status_code=302)


@router.post("/channels/{channel_id}/views/new")
async def view_create(
    channel_id: int,
    name: str = Form(...),
    duration_seconds: str | None = Form(None),
):
    with get_session() as db:
        existing = db.exec(
            select(View).where(View.channel_id == channel_id, View.zone_id == None)  # noqa: E711
        ).all()
        position = len(existing)
        dur = int(duration_seconds) if duration_seconds else None
        view = View(
            channel_id=channel_id,
            name=name,
            position=position,
            duration_seconds=dur,
            layout_json={"widgets": []},
        )
        db.add(view)
        db.commit()
        db.refresh(view)
    return RedirectResponse(f"/admin/views/{view.id}", status_code=302)


@router.post("/channels/{channel_id}/views/{view_id}/delete")
async def view_delete(channel_id: int, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view or view.channel_id != channel_id:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        db.delete(view)
        db.commit()
        _reorder_views(db, channel_id, None)
    return RedirectResponse(f"/admin/channels/{channel_id}", status_code=302)


@router.post("/channels/{channel_id}/zones/{zone_id}/views/{view_id}/move")
async def zone_view_move(
    channel_id: int, zone_id: int, view_id: int, target_zone_id: int = Form(...)
):
    with get_session() as db:
        view = db.get(View, view_id)
        if view and view.channel_id == channel_id and view.zone_id == zone_id:
            view.zone_id = target_zone_id
            existing = db.exec(
                select(View).where(View.channel_id == channel_id, View.zone_id == target_zone_id)
            ).all()
            view.position = len([v for v in existing if v.id != view_id])
            db.add(view)
            db.commit()
            _reorder_views(db, channel_id, zone_id)
    return RedirectResponse(f"/admin/channels/{channel_id}/zones/{zone_id}", status_code=302)


@router.post("/channels/{channel_id}/views/{view_id}/assign-zone")
async def view_assign_zone(request: Request, channel_id: int, view_id: int):
    body = await request.json()
    zone_id = body.get("zone_id")  # int eller null
    with get_session() as db:
        view = db.get(View, view_id)
        if not view or view.channel_id != channel_id:
            return {"error": "Vy saknas"}
        old_zone = view.zone_id
        view.zone_id = int(zone_id) if zone_id is not None else None
        # Lägg sist i målzonen
        existing = db.exec(
            select(View).where(View.channel_id == channel_id, View.zone_id == view.zone_id)
        ).all()
        view.position = len([v for v in existing if v.id != view_id])
        db.add(view)
        db.commit()
        _reorder_views(db, channel_id, old_zone)
    return {"ok": True}


def _reorder_views(db, channel_id: int, zone_id: int | None) -> None:
    views = db.exec(
        select(View)
        .where(View.channel_id == channel_id, View.zone_id == zone_id)
        .order_by(View.position)
    ).all()
    for i, v in enumerate(views):
        v.position = i
        db.add(v)
    db.commit()
