import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import select
from sse_starlette.sse import EventSourceResponse

from app import sse as sse_registry
from app.database import get_session
from app.models import Screen, View, Widget
from app.templating import templates
from app.widgets.base import render_widget

router = APIRouter()

_VERSION = "dev"


@router.get("/s/{slug}", response_class=HTMLResponse)
async def kiosk_view(request: Request, slug: str, debug: str = ""):
    with get_session() as db:
        screen = db.exec(select(Screen).where(Screen.slug == slug)).first()
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        views = db.exec(
            select(View).where(View.screen_id == screen.id).order_by(View.position)
        ).all()

        context = {
            "screen_name": screen.name,
            "screen_slug": screen.slug,
            "view_count": len(views),
            "version": _VERSION,
        }

        rendered_views = []
        for view in views:
            layout = view.layout_json or {"widgets": []}
            rendered_widgets = []
            row_max = 6
            for entry in layout.get("widgets", []):
                x = entry.get("x", 0)
                y = entry.get("y", 0)
                w = entry.get("w", 12)
                h = entry.get("h", 6)
                row_max = max(row_max, y + h)
                widget = db.get(Widget, entry["widget_id"])
                if widget is None:
                    inner = '<div class="widget-missing">Widget saknas</div>'
                else:
                    ctx = {**context, "view_position": view.position + 1, "widget_id": widget.id}
                    inner = render_widget(widget.kind, widget.config_json or {}, ctx)
                rendered_widgets.append(
                    {
                        "html": inner,
                        "widget_id": entry["widget_id"],
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "col_start": x + 1,
                        "col_end": x + w + 1,
                        "row_start": y + 1,
                        "row_end": y + h + 1,
                        "z_index": entry.get("z_index", 1),
                        "opacity": entry.get("opacity", 100),
                    }
                )

            rendered_views.append(
                {
                    "id": view.id,
                    "position": view.position,
                    "name": view.name,
                    "duration_seconds": view.duration_seconds or screen.rotation_seconds,
                    "widgets": rendered_widgets,
                    "grid_cols": view.grid_cols,
                    "grid_rows": view.grid_rows,
                }
            )

    show_debug = debug == "1"
    return HTMLResponse(
        templates.get_template("kiosk/screen.html").render(
            request=request,
            screen=screen,
            views=rendered_views,
            show_debug=show_debug,
            version=_VERSION,
        )
    )


@router.get("/s/{slug}/events")
async def kiosk_events(request: Request, slug: str):
    with get_session() as db:
        screen = db.exec(select(Screen).where(Screen.slug == slug)).first()
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        screen_id = screen.id

    q = sse_registry.register(screen_id)

    async def event_generator():
        try:
            yield {"event": "connected", "data": json.dumps({"screen_id": screen_id})}
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=30)
                    yield {"event": event.get("type", "message"), "data": json.dumps(event)}
                except TimeoutError:
                    # keepalive — håller proxier och klienter vakna
                    yield {"comment": "keepalive"}
        finally:
            sse_registry.unregister(screen_id, q)

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
    with get_session() as db:
        views = db.exec(select(View)).all()
        screen_ids: set[int] = set()
        for view in views:
            layout = view.layout_json or {}
            if any(w["widget_id"] == widget_id for w in layout.get("widgets", [])):
                screen_ids.add(view.screen_id)
    for screen_id in screen_ids:
        sse_registry.broadcast(screen_id, {"type": "widget_updated", "widget_id": widget_id})
