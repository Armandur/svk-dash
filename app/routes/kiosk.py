import asyncio
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from app import sse as sse_registry
from app.database import get_session
from app.models import Channel, ChannelLayoutAssignment, Layout, LayoutZone, Screen, View, Widget
from app.templating import templates
from app.widgets.base import render_widget

router = APIRouter()

_VERSION = "dev"


def _is_active(schedule, now: datetime):
    if not schedule:
        return True
    
    if isinstance(schedule, str):
        try:
            schedule = json.loads(schedule)
        except:
            return True
            
    type_ = schedule.get("type", "always")
    if type_ == "always":
        return True
        
    # Check time
    current_time = now.strftime("%H:%M")
    time_start = schedule.get("time_start")
    time_end = schedule.get("time_end")
    if time_start and current_time < time_start:
        return False
    if time_end and current_time >= time_end:
        return False
        
    if type_ == "weekly":
        current_day = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"][int(now.strftime("%w"))]
        days = schedule.get("weekdays", [])
        return current_day in days
        
    if type_ == "monthly":
        return now.day == schedule.get("day")
        
    if type_ == "yearly":
        return now.day == schedule.get("day") and now.month == schedule.get("month")
        
    if type_ == "dates":
        current_date = now.strftime("%Y-%m-%d")
        return current_date in schedule.get("dates", [])
        
    return True


def _get_active_assignments(assignments, now: datetime):
    import logging as _log
    active = [a for a in assignments if a.enabled and _is_active(a.schedule_json, now)]

    if not active:
        _log.getLogger(__name__).info("layout-val: inga aktiva tilldelningar")
        return []

    rotating = [a for a in active if a.duration_seconds]
    if rotating:
        rotating.sort(key=lambda x: (x.priority, x.id), reverse=True)
        _log.getLogger(__name__).info("layout-val: roterande=%s", [a.id for a in rotating])
        return rotating
    
    active.sort(key=lambda x: (x.priority, x.id), reverse=True)
    _log.getLogger(__name__).info("layout-val: vinnare=%s", active[0].id)
    return [active[0]]


def _render_layout(assignment, screen, context, db):
    layout = db.get(Layout, assignment.layout_id)
    if not layout:
        return None
        
    db_zones = db.exec(
        select(LayoutZone)
        .where(LayoutZone.layout_id == layout.id)
        .order_by(LayoutZone.z_index)
    ).all()
    
    zones_rendered = []
    for zone in db_zones:
        zone_views = db.exec(
            select(View)
            .where(View.channel_id == screen.channel_id, View.zone_id == zone.id)
            .order_by(View.position)
        ).all()
        views_data = [_render_view(v, context, db) for v in zone_views if v.enabled]
        zones_rendered.append(
            {
                "id": zone.id,
                "name": zone.name,
                "role": zone.role,
                "x_pct": zone.x_pct,
                "y_pct": zone.y_pct,
                "w_pct": zone.w_pct,
                "h_pct": zone.h_pct,
                "z_index": zone.z_index,
                "rotation_seconds": zone.rotation_seconds,
                "transition": zone.transition,
                "transition_direction": zone.transition_direction,
                "transition_duration_ms": zone.transition_duration_ms,
                "views": views_data,
            }
        )

    return {
        "assignment_id": assignment.id,
        "layout_id": layout.id,
        "duration_seconds": assignment.duration_seconds,
        "transition": assignment.transition,
        "transition_direction": assignment.transition_direction,
        "transition_duration_ms": assignment.transition_duration_ms,
        "zones": zones_rendered,
    }


def _render_view(view: View, context: dict, db) -> dict:
    layout = view.layout_json or {"widgets": []}
    rendered_widgets = []
    for entry in layout.get("widgets", []):
        x = entry.get("x", 0)
        y = entry.get("y", 0)
        w = entry.get("w", 12)
        h = entry.get("h", 6)
        if "inline_id" in entry:
            ctx = {**context, "view_position": view.position + 1}
            inner = render_widget(entry["kind"], entry.get("config") or {}, ctx)
            eid = entry["inline_id"]
        else:
            widget = db.get(Widget, entry["widget_id"])
            if widget is None:
                inner = '<div class="widget-missing">Widget saknas</div>'
            else:
                ctx = {**context, "view_position": view.position + 1, "widget_id": widget.id}
                inner = render_widget(widget.kind, widget.config_json or {}, ctx)
            eid = entry["widget_id"]
        rendered_widgets.append(
            {
                "html": inner,
                "widget_id": eid,
                "col_start": x + 1,
                "col_end": x + w + 1,
                "row_start": y + 1,
                "row_end": y + h + 1,
                "z_index": entry.get("z_index", 1),
                "opacity": entry.get("opacity", 100),
            }
        )
    return {
        "id": view.id,
        "name": view.name,
        "position": view.position,
        "duration_seconds": view.duration_seconds,
        "transition": view.transition,
        "transition_direction": view.transition_direction,
        "transition_duration_ms": view.transition_duration_ms,
        "schedule_json": view.schedule_json,
        "widgets": rendered_widgets,
        "grid_cols": view.grid_cols,
        "grid_rows": view.grid_rows,
    }


@router.get("/s/{slug}", response_class=HTMLResponse)
async def kiosk_view(request: Request, slug: str, debug: str = ""):
    with get_session() as db:
        screen = db.exec(select(Screen).where(Screen.slug == slug)).first()
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)

        context = {
            "screen_name": screen.name,
            "screen_slug": screen.slug,
            "version": _VERSION,
        }

        # Hämta alla tilldelningar för skärmens kanal
        assignments = db.exec(
            select(ChannelLayoutAssignment).where(ChannelLayoutAssignment.channel_id == screen.channel_id)
        ).all()

        now = datetime.now()
        active_assignments = _get_active_assignments(assignments, now)

        layouts_rendered = []
        for assignment in active_assignments:
            rendered = _render_layout(assignment, screen, context, db)
            if rendered:
                layouts_rendered.append(rendered)

    def _strip_html(layout):
        """Returnerar en kopia av layouten utan widget-HTML (för JS-konstanten)."""
        stripped_zones = []
        for z in layout["zones"]:
            views_meta = [
                {
                    "position": v["position"],
                    "name": v["name"],
                    "duration_seconds": v["duration_seconds"],
                    "schedule_json": v["schedule_json"],
                }
                for v in z["views"]
            ]
            stripped_zones.append({k: v for k, v in z.items() if k != "views"} | {"views": views_meta})
        
        return {
            "assignment_id": layout["assignment_id"],
            "duration_seconds": layout["duration_seconds"],
            "transition": layout["transition"],
            "transition_direction": layout["transition_direction"],
            "transition_duration_ms": layout["transition_duration_ms"],
            "zones": stripped_zones,
        }

    show_debug = debug == "1"
    
    # Första layouten bestämmer initiala body-klasser om vi bara har en, 
    # annars hanteras det av JS.
    first_layout = layouts_rendered[0] if layouts_rendered else None
    
    response = HTMLResponse(
        templates.get_template("kiosk/screen.html").render(
            request=request,
            screen=screen,
            layouts=layouts_rendered,
            layouts_js=[_strip_html(l) for l in layouts_rendered] if layouts_rendered else None,
            layout_rotation={
                "duration_seconds": first_layout["duration_seconds"] if first_layout else None,
                "transition": first_layout["transition"] if first_layout else "fade",
                "transition_direction": first_layout["transition_direction"] if first_layout else "left",
                "transition_duration_ms": first_layout["transition_duration_ms"] if first_layout else 700,
            },
            show_offline_banner=screen.show_offline_banner,
            show_debug=show_debug,
            version=_VERSION,
        )
    )
    return response


def _update_heartbeat(screen_id: int) -> None:
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if screen:
            screen.last_seen_at = datetime.utcnow()
            screen.last_connection_count = sse_registry.connection_count(screen_id)
            db.add(screen)
            db.commit()


def _update_connection_count(screen_id: int) -> None:
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if screen:
            screen.last_connection_count = sse_registry.connection_count(screen_id)
            db.add(screen)
            db.commit()


@router.get("/s/{slug}/events")
async def kiosk_events(request: Request, slug: str):
    with get_session() as db:
        screen = db.exec(select(Screen).where(Screen.slug == slug)).first()
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        screen_id = screen.id

    forwarded = request.headers.get("X-Forwarded-For", "")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "okänd")
    client_id = str(uuid.uuid4())
    meta = {
        "client_id": client_id,
        "ip": ip,
        "user_agent": request.headers.get("User-Agent", ""),
        "connected_at": datetime.utcnow().isoformat(timespec="seconds"),
    }
    q = sse_registry.register(screen_id, meta)
    _update_heartbeat(screen_id)

    async def event_generator():
        try:
            yield {"event": "connected", "data": json.dumps({"screen_id": screen_id, "client_id": client_id})}
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield {"event": event.get("type", "message"), "data": json.dumps(event)}
                except TimeoutError:
                    _update_heartbeat(screen_id)
                    yield {"event": "keepalive", "data": ""}
        finally:
            sse_registry.unregister(screen_id, q)
            _update_connection_count(screen_id)

    return EventSourceResponse(event_generator())


@router.post("/s/{slug}/client-meta")
async def kiosk_client_meta(request: Request, slug: str):
    with get_session() as db:
        screen = db.exec(select(Screen).where(Screen.slug == slug)).first()
        if not screen:
            return JSONResponse({}, status_code=404)
        screen_id = screen.id
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({}, status_code=400)
    client_id = data.get("client_id", "")
    if client_id:
        extra = {k: data[k] for k in ("screen_width", "screen_height", "device_pixel_ratio", "timezone", "network_type") if k in data}
        sse_registry.update_client_meta(screen_id, client_id, extra)
    return JSONResponse({"ok": True})


@router.get("/api/widget/{widget_id}/data")
async def widget_data(request: Request, widget_id: int):
    with get_session() as db:
        widget = db.get(Widget, widget_id)
        if not widget:
            return HTMLResponse("", status_code=404)
        ctx = {"widget_id": widget.id, "version": _VERSION}
        inner = render_widget(widget.kind, widget.config_json or {}, ctx)
    return HTMLResponse(inner)


def broadcast_widget_updated(widget_id: int) -> None:
    """Hitta alla skärmar som visar widgeten och pusha widget_updated-event."""
    from sqlalchemy import String, cast

    with get_session() as db:
        pattern = f'%"widget_id": {widget_id}%'
        views = db.exec(select(View).where(cast(View.layout_json, String).like(pattern))).all()
        screen_ids: set[int] = set()
        for view in views:
            layout = view.layout_json or {}
            if any(w.get("widget_id") == widget_id for w in layout.get("widgets", [])):
                # view.channel_id är nu källan
                screens = db.exec(select(Screen).where(Screen.channel_id == view.channel_id)).all()
                for screen in screens:
                    screen_ids.add(screen.id)
    for screen_id in screen_ids:
        sse_registry.broadcast(screen_id, {"type": "widget_updated", "widget_id": widget_id})
