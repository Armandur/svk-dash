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
            for entry in layout.get("widgets", []):
                widget = db.get(Widget, entry["widget_id"])
                if widget is None:
                    rendered_widgets.append(
                        '<div class="widget-missing text-red-400 text-sm p-4">Widget saknas</div>'
                    )
                else:
                    ctx = {**context, "view_position": view.position + 1, "widget_id": widget.id}
                    rendered_widgets.append(
                        render_widget(widget.kind, widget.config_json or {}, ctx)
                    )

            rendered_views.append(
                {
                    "id": view.id,
                    "position": view.position,
                    "name": view.name,
                    "duration_seconds": view.duration_seconds or screen.rotation_seconds,
                    "widgets_html": rendered_widgets,
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
