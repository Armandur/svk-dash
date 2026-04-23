import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from app import sse as sse_registry
from app.database import get_session
from app.models import Layout, LayoutZone, Screen, ScreenLayoutAssignment, View, Widget
from app.templating import templates
from app.widgets.base import render_widget

router = APIRouter()

_VERSION = "dev"


def _active_assignment(assignments, now: datetime):
    """Väljer den mest prioriterade aktiva tilldelningen baserat på schema."""
    active = []
    current_day = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"][int(now.strftime("%w"))]
    current_time = now.strftime("%H:%M")

    for a in assignments:
        # Veckodagar
        if a.weekdays:
            days = [d.strip() for d in a.weekdays.split(",")]
            if current_day not in days:
                continue

        # Tid
        if a.time_start and current_time < a.time_start:
            continue
        if a.time_end and current_time >= a.time_end:
            continue

        active.append(a)

    if not active:
        return None

    # Sortera på prioritet (högst först)
    active.sort(key=lambda x: x.priority, reverse=True)
    return active[0]


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
        "schedule_weekdays": view.schedule_weekdays,
        "schedule_time_start": view.schedule_time_start,
        "schedule_time_end": view.schedule_time_end,
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

        # Kolla om skärmen har en layout
        assignments = db.exec(
            select(ScreenLayoutAssignment).where(ScreenLayoutAssignment.screen_id == screen.id)
        ).all()

        now = datetime.now()
        assignment = _active_assignment(assignments, now)

        zones_rendered = None
        layout = None
        legacy_views = None

        if assignment:
            layout = db.get(Layout, assignment.layout_id)
            if layout:
                db_zones = db.exec(
                    select(LayoutZone)
                    .where(LayoutZone.layout_id == layout.id)
                    .order_by(LayoutZone.z_index)
                ).all()
                zones_rendered = []
                for zone in db_zones:
                    zone_views = db.exec(
                        select(View)
                        .where(View.screen_id == screen.id, View.zone_id == zone.id)
                        .order_by(View.position)
                    ).all()
                    views_data = [_render_view(v, context, db) for v in zone_views]
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
                            "views": views_data,
                        }
                    )

        if zones_rendered is None:
            # Legacy: ingen layout, visa vyer direkt
            db_views = db.exec(
                select(View)
                .where(View.screen_id == screen.id, View.zone_id == None)  # noqa: E711
                .order_by(View.position)
            ).all()
            legacy_views = []
            for v in db_views:
                rv = _render_view(v, context, db)
                rv["duration_seconds"] = rv["duration_seconds"] or 30
                legacy_views.append(rv)

    def _strip_html(zones):
        """Returnerar en kopia av zones utan widget-HTML (för JS-konstanten)."""
        if zones is None:
            return None
        result = []
        for z in zones:
            views_meta = [
                {
                    "position": v["position"],
                    "name": v["name"],
                    "duration_seconds": v["duration_seconds"],
                    "schedule_weekdays": v["schedule_weekdays"],
                    "schedule_time_start": v["schedule_time_start"],
                    "schedule_time_end": v["schedule_time_end"],
                }
                for v in z["views"]
            ]
            result.append({k: v for k, v in z.items() if k != "views"} | {"views": views_meta})
        return result

    def _legacy_meta(views):
        if views is None:
            return None
        return [
            {
                "position": v["position"],
                "name": v["name"],
                "duration_seconds": v["duration_seconds"],
                "schedule_weekdays": v["schedule_weekdays"],
                "schedule_time_start": v["schedule_time_start"],
                "schedule_time_end": v["schedule_time_end"],
            }
            for v in views
        ]

    show_debug = debug == "1"
    return HTMLResponse(
        templates.get_template("kiosk/screen.html").render(
            request=request,
            screen=screen,
            zones=zones_rendered,
            zones_js=_strip_html(zones_rendered),
            legacy_views=legacy_views,
            legacy_views_js=_legacy_meta(legacy_views),
            show_debug=show_debug,
            version=_VERSION,
        )
    )


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

    q = sse_registry.register(screen_id)
    _update_heartbeat(screen_id)

    async def event_generator():
        try:
            yield {"event": "connected", "data": json.dumps({"screen_id": screen_id})}
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield {"event": event.get("type", "message"), "data": json.dumps(event)}
                except TimeoutError:
                    _update_heartbeat(screen_id)
                    yield {"comment": "keepalive"}
        finally:
            sse_registry.unregister(screen_id, q)
            _update_connection_count(screen_id)

    return EventSourceResponse(event_generator())


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
                screen_ids.add(view.screen_id)
    for screen_id in screen_ids:
        sse_registry.broadcast(screen_id, {"type": "widget_updated", "widget_id": widget_id})
