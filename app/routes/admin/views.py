import copy
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.database import get_session
from app.deps import require_admin
from app.models import Screen, View, Widget
from app.templating import templates
from app.widgets.base import render_widget

_ASPECT_CSS = {
    "16:9": "16 / 9",
    "9:16": "9 / 16",
    "4:3": "4 / 3",
    "3:4": "3 / 4",
    "1:1": "1 / 1",
    "A-L": "1.414 / 1",
    "A-P": "1 / 1.414",
}

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/views/{view_id}", response_class=HTMLResponse)
async def view_detail(request: Request, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        screen = db.get(Screen, view.screen_id)
        layout = view.layout_json or {"widgets": []}
        layout_entries = []
        for entry in layout.get("widgets", []):
            w = db.get(Widget, entry["widget_id"])
            widget_html = None
            if w:
                ctx = {"widget_id": w.id, "version": "admin-preview"}
                widget_html = render_widget(w.kind, w.config_json or {}, ctx)
            layout_entries.append(
                {
                    "widget": w,
                    "widget_html": widget_html,
                    "widget_id": entry["widget_id"],
                    "x": entry.get("x", 0),
                    "y": entry.get("y", 0),
                    "w": entry.get("w", 12),
                    "h": entry.get("h", 6),
                    "z_index": entry.get("z_index", 1),
                    "opacity": entry.get("opacity", 100),
                }
            )
        all_widgets = db.exec(select(Widget).order_by(Widget.name)).all()
    aspect_ratio = screen.aspect_ratio if screen else "16:9"
    aspect_ratio_css = _ASPECT_CSS.get(aspect_ratio, "16 / 9")
    return HTMLResponse(
        templates.get_template("admin/view_detail.html").render(
            request=request,
            view=view,
            screen=screen,
            aspect_ratio_css=aspect_ratio_css,
            layout_entries=layout_entries,
            all_widgets=all_widgets,
        )
    )


@router.post("/views/{view_id}/edit")
async def view_edit(
    request: Request,
    view_id: int,
    name: str = Form(...),
    duration_seconds: str = Form(""),
    grid_cols: int = Form(12),
    grid_rows: int = Form(9),
):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        view.name = name
        view.duration_seconds = int(duration_seconds) if duration_seconds.strip() else None
        view.grid_cols = max(1, min(24, grid_cols))
        view.grid_rows = max(1, min(24, grid_rows))
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return RedirectResponse(f"/admin/views/{view_id}", status_code=302)


@router.post("/views/{view_id}/widgets/add")
async def view_add_widget(request: Request, view_id: int, widget_id: int = Form(...)):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        widget = db.get(Widget, widget_id)
        if not widget:
            return HTMLResponse("Widgeten hittades inte.", status_code=404)
        layout = copy.deepcopy(view.layout_json or {"widgets": []})
        widgets_list = layout.get("widgets", [])
        if not any(w["widget_id"] == widget_id for w in widgets_list):
            next_y = max((w.get("y", 0) + w.get("h", 6) for w in widgets_list), default=0)
            widgets_list.append(
                {
                    "widget_id": widget_id,
                    "x": 0,
                    "y": next_y,
                    "w": 12,
                    "h": 6,
                    "z_index": 1,
                    "opacity": 100,
                }
            )
        layout["widgets"] = widgets_list
        view.layout_json = layout
        flag_modified(view, "layout_json")
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return RedirectResponse(f"/admin/views/{view_id}", status_code=302)


@router.post("/views/{view_id}/layout")
async def view_save_layout(request: Request, view_id: int):
    body = await request.json()
    widgets = body.get("widgets", [])
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return JSONResponse({"error": "Vyn hittades inte."}, status_code=404)
        layout = {
            "widgets": [
                {
                    "widget_id": int(w["widget_id"]),
                    "x": int(w["x"]),
                    "y": int(w["y"]),
                    "w": int(w["w"]),
                    "h": int(w["h"]),
                    "z_index": max(1, min(20, int(w.get("z_index", 1)))),
                    "opacity": max(0, min(100, int(w.get("opacity", 100)))),
                }
                for w in widgets
            ]
        }
        view.layout_json = layout
        flag_modified(view, "layout_json")
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return JSONResponse({"ok": True})


@router.post("/views/{view_id}/widgets/{widget_id}/remove")
async def view_remove_widget(request: Request, view_id: int, widget_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        layout = copy.deepcopy(view.layout_json or {"widgets": []})
        layout["widgets"] = [w for w in layout.get("widgets", []) if w["widget_id"] != widget_id]
        view.layout_json = layout
        flag_modified(view, "layout_json")
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return RedirectResponse(f"/admin/views/{view_id}", status_code=302)
