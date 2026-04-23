import copy
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.database import get_session
from app.deps import require_admin
from app.models import Layout, LayoutZone, Screen, ScreenLayoutAssignment, View, Widget
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

_LAYOUT_ASPECT_FLOAT = {
    "16:9": 16 / 9,
    "9:16": 9 / 16,
    "4:3": 4 / 3,
    "3:4": 3 / 4,
    "1:1": 1.0,
    "A-L": 1.414,
    "A-P": 1 / 1.414,
}


def _zone_aspect_css(db, view: View) -> str:
    """Returnerar CSS aspect-ratio för vy-editorns canvas.
    Om vyn har en zon beräknas zonens egna proportioner.
    Annars faller vi tillbaka på 16/9.
    """
    if not view.zone_id:
        return "16 / 9"
    zone = db.get(LayoutZone, view.zone_id)
    if not zone or not zone.w_pct or not zone.h_pct:
        return "16 / 9"
    assignment = db.exec(
        select(ScreenLayoutAssignment).where(ScreenLayoutAssignment.screen_id == view.screen_id)
    ).first()
    if not assignment:
        return "16 / 9"
    layout = db.get(Layout, assignment.layout_id)
    if not layout:
        return "16 / 9"
    screen_ratio = _LAYOUT_ASPECT_FLOAT.get(layout.aspect_ratio, 16 / 9)
    zone_ratio = screen_ratio * (zone.w_pct / zone.h_pct)
    return f"{zone_ratio:.6f} / 1"


_WIDGET_CATEGORIES: list[tuple[str, set[str]]] = [
    ("Kalender", {"ics_list", "ics_month", "ics_week", "ics_schedule"}),
    ("Media", {"image", "slideshow"}),
    ("Innehåll", {"markdown", "iframe", "raw_html"}),
    ("Övrigt", {"clock", "color_block", "debug", "text"}),
]

_INLINE_DEFAULTS: dict[str, dict] = {
    "clock": {
        "format": "time_date",
        "size": "xl",
        "timezone": "Europe/Stockholm",
        "locale": "sv-SE",
    },
    "text": {"text": "Text", "size": "large", "align": "center", "bold": False, "color": "#ffffff"},
    "color_block": {"color": "#1e3a5f", "border_radius": 0},
    "image": {"url": "", "fit": "cover"},
    "slideshow": {"images": [], "interval": 5, "fit": "cover", "transition": "fade"},
}

_INLINE_LABELS: dict[str, str] = {
    "clock": "Klocka",
    "text": "Text",
    "color_block": "Färgblock",
    "image": "Bild",
    "slideshow": "Bildspel",
}

router = APIRouter(dependencies=[Depends(require_admin)])


def _migrate_layout(layout: dict) -> dict:
    """Säkerställer att layout har layers-fält. Migrerar äldre format."""
    if "layers" not in layout:
        default_layer_id = "l-default"
        layout["layers"] = [{"id": default_layer_id, "name": "Standard", "visible": True}]
        for w in layout.get("widgets", []):
            if "layer_id" not in w:
                w["layer_id"] = default_layer_id
    return layout


def _top_layer_id(layout: dict) -> str:
    """Returnerar ID för det översta lagret (sist i listan = framför)."""
    layers = layout.get("layers", [])
    return layers[-1]["id"] if layers else "l-default"


def _compute_z_indices(layout: dict) -> None:
    """Räknar om z_index för alla widgets baserat på lagerposition och intra-ordning."""
    layers = layout.get("layers", [])
    layer_pos = {layer["id"]: idx for idx, layer in enumerate(layers)}
    # Gruppera widgets per lager, i ordning de finns i widgets-listan
    layer_widgets: dict[str, list] = {layer["id"]: [] for layer in layers}
    orphans = []
    for w in layout.get("widgets", []):
        lid = w.get("layer_id", "")
        if lid in layer_widgets:
            layer_widgets[lid].append(w)
        else:
            orphans.append(w)
    # Tilldela z_index: lager 0 (botten) → z 100..199, lager 1 → z 200..299 osv.
    for layer in layers:
        lid = layer["id"]
        base = (layer_pos[lid] + 1) * 100
        for intra, w in enumerate(layer_widgets[lid]):
            w["z_index"] = base + intra
    for idx, w in enumerate(orphans):
        w["z_index"] = idx + 1


@router.get("/views/{view_id}", response_class=HTMLResponse)
async def view_detail(request: Request, view_id: int):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        screen = db.get(Screen, view.screen_id)
        layout = _migrate_layout(copy.deepcopy(view.layout_json or {"widgets": []}))
        layers = layout.get("layers", [])
        layout_entries = []
        for entry in layout.get("widgets", []):
            if "inline_id" in entry:
                kind = entry["kind"]
                config = entry.get("config", copy.deepcopy(_INLINE_DEFAULTS.get(kind, {})))
                ctx: dict = {"version": "admin-preview"}
                widget_html = render_widget(kind, config, ctx)
                layout_entries.append(
                    {
                        "is_inline": True,
                        "inline_id": entry["inline_id"],
                        "kind": kind,
                        "config": config,
                        "label": _INLINE_LABELS.get(kind, kind),
                        "widget_html": widget_html,
                        "x": entry.get("x", 0),
                        "y": entry.get("y", 0),
                        "w": entry.get("w", 4),
                        "h": entry.get("h", 3),
                        "z_index": entry.get("z_index", 1),
                        "opacity": entry.get("opacity", 100),
                        "layer_id": entry.get("layer_id", _top_layer_id(layout)),
                    }
                )
            else:
                w = db.get(Widget, entry["widget_id"])
                widget_html = None
                if w:
                    ctx = {"widget_id": w.id, "version": "admin-preview"}
                    widget_html = render_widget(w.kind, w.config_json or {}, ctx)
                layout_entries.append(
                    {
                        "is_inline": False,
                        "widget": w,
                        "widget_html": widget_html,
                        "widget_id": entry["widget_id"],
                        "x": entry.get("x", 0),
                        "y": entry.get("y", 0),
                        "w": entry.get("w", 12),
                        "h": entry.get("h", 6),
                        "z_index": entry.get("z_index", 1),
                        "opacity": entry.get("opacity", 100),
                        "layer_id": entry.get("layer_id", _top_layer_id(layout)),
                    }
                )
        all_widgets = db.exec(select(Widget).order_by(Widget.name)).all()
        _kind_to_cat = {k: cat for cat, kinds in _WIDGET_CATEGORIES for k in kinds}
        cat_buckets: dict[str, list] = {cat: [] for cat, _ in _WIDGET_CATEGORIES}
        for w in all_widgets:
            cat_buckets.setdefault(_kind_to_cat.get(w.kind, "Övrigt"), []).append(w)
        widget_categories = [(cat, cat_buckets.get(cat, [])) for cat, _ in _WIDGET_CATEGORIES]
        zone = db.get(LayoutZone, view.zone_id) if view.zone_id else None
        sibling_views = db.exec(
            select(View)
            .where(View.screen_id == view.screen_id, View.zone_id == view.zone_id)
            .order_by(View.position)
        ).all()
    aspect_ratio_css = _zone_aspect_css(db, view)
    sib_ids = [v.id for v in sibling_views]
    cur_idx = sib_ids.index(view_id) if view_id in sib_ids else 0
    is_persistent = zone is not None and zone.role == "persistent"
    prev_view = sibling_views[cur_idx - 1] if not is_persistent and cur_idx > 0 else None
    next_view = (
        sibling_views[cur_idx + 1]
        if not is_persistent and cur_idx < len(sibling_views) - 1
        else None
    )
    return HTMLResponse(
        templates.get_template("admin/view_detail.html").render(
            request=request,
            view=view,
            screen=screen,
            zone=zone,
            aspect_ratio_css=aspect_ratio_css,
            layout_entries=layout_entries,
            layers=layers,
            all_widgets=all_widgets,
            widget_categories=widget_categories,
            inline_labels=_INLINE_LABELS,
            prev_view=prev_view,
            next_view=next_view,
            view_index=cur_idx,
            view_count=len(sibling_views),
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
        new_cols = max(1, min(24, grid_cols))
        new_rows = max(1, min(24, grid_rows))
        if new_cols != view.grid_cols or new_rows != view.grid_rows:
            layout = copy.deepcopy(view.layout_json or {"widgets": []})
            for w in layout.get("widgets", []):
                x = min(w.get("x", 0), new_cols - 1)
                y = min(w.get("y", 0), new_rows - 1)
                w["x"] = x
                w["y"] = y
                w["w"] = max(1, min(w.get("w", 1), new_cols - x))
                w["h"] = max(1, min(w.get("h", 1), new_rows - y))
            view.layout_json = layout
            flag_modified(view, "layout_json")
        view.grid_cols = new_cols
        view.grid_rows = new_rows
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
        layout = _migrate_layout(copy.deepcopy(view.layout_json or {"widgets": []}))
        widgets_list = layout.get("widgets", [])
        if not any(w.get("widget_id") == widget_id for w in widgets_list):
            cols = view.grid_cols or 12
            rows = view.grid_rows or 9
            w_default = min(cols, 12)
            h_default = min(rows, 6)
            next_y = max((w.get("y", 0) + w.get("h", h_default) for w in widgets_list), default=0)
            # Om ny y hamnar utanför gridet, placera i övre vänstra hörnet
            if next_y + h_default > rows:
                next_y = 0
            widgets_list.append(
                {
                    "widget_id": widget_id,
                    "x": 0,
                    "y": next_y,
                    "w": w_default,
                    "h": h_default,
                    "opacity": 100,
                    "layer_id": _top_layer_id(layout),
                }
            )
        layout["widgets"] = widgets_list
        _compute_z_indices(layout)
        view.layout_json = layout
        flag_modified(view, "layout_json")
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return RedirectResponse(f"/admin/views/{view_id}", status_code=302)


@router.post("/views/{view_id}/inline/add")
async def view_add_inline(request: Request, view_id: int, kind: str = Form(...)):
    if kind not in _INLINE_DEFAULTS:
        return HTMLResponse("Okänd inline-typ.", status_code=400)
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        layout = _migrate_layout(copy.deepcopy(view.layout_json or {"widgets": []}))
        inline_id = "inline-" + uuid.uuid4().hex[:8]
        existing = layout.setdefault("widgets", [])
        cols = view.grid_cols or 12
        rows = view.grid_rows or 9
        existing.append(
            {
                "inline_id": inline_id,
                "kind": kind,
                "config": copy.deepcopy(_INLINE_DEFAULTS[kind]),
                "x": 0,
                "y": 0,
                "w": min(4, cols),
                "h": min(3, rows),
                "opacity": 100,
                "layer_id": _top_layer_id(layout),
            }
        )
        _compute_z_indices(layout)
        view.layout_json = layout
        flag_modified(view, "layout_json")
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return RedirectResponse(f"/admin/views/{view_id}", status_code=302)


@router.post("/views/{view_id}/inline/{inline_id}/remove")
async def view_remove_inline(request: Request, view_id: int, inline_id: str):
    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return HTMLResponse("Vyn hittades inte.", status_code=404)
        layout = copy.deepcopy(view.layout_json or {"widgets": []})
        layout["widgets"] = [
            w for w in layout.get("widgets", []) if w.get("inline_id") != inline_id
        ]
        view.layout_json = layout
        flag_modified(view, "layout_json")
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return RedirectResponse(f"/admin/views/{view_id}", status_code=302)


@router.post("/views/{view_id}/layout")
async def view_save_layout(request: Request, view_id: int):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Ogiltig JSON-data."}, status_code=400)

    widgets = body.get("widgets", [])
    layers = body.get("layers", [])

    if not isinstance(widgets, list):
        return JSONResponse({"error": "'widgets' måste vara en lista."}, status_code=400)
    if not isinstance(layers, list):
        return JSONResponse({"error": "'layers' måste vara en lista."}, status_code=400)

    with get_session() as db:
        view = db.get(View, view_id)
        if not view:
            return JSONResponse({"error": "Vyn hittades inte."}, status_code=404)

        # Validera och normalisera lager
        valid_layer_ids = {
            layer["id"] for layer in layers if isinstance(layer, dict) and "id" in layer
        }
        if not layers:
            # Fallback om inga lager skickades — behåll befintliga
            existing = view.layout_json or {}
            layers = existing.get(
                "layers", [{"id": "l-default", "name": "Standard", "visible": True}]
            )
            valid_layer_ids = {layer["id"] for layer in layers}

        clean_layers = [
            {
                "id": str(layer["id"]),
                "name": str(layer.get("name", "Lager"))[:40],
                "visible": bool(layer.get("visible", True)),
            }
            for layer in layers
            if isinstance(layer, dict) and "id" in layer
        ]

        result: list[dict] = []
        for w in widgets:
            if not isinstance(w, dict):
                continue
            layer_id = (
                str(w.get("layer_id", ""))
                if w.get("layer_id") in valid_layer_ids
                else (clean_layers[-1]["id"] if clean_layers else "l-default")
            )

            try:
                # Validera att x, y, w, h finns och är heltal
                for key in ["x", "y", "w", "h"]:
                    if key not in w:
                        return JSONResponse(
                            {"error": f"Widget saknar nyckeln '{key}'."}, status_code=400
                        )
                    int(w[key])

                if "inline_id" in w:
                    result.append(
                        {
                            "inline_id": str(w["inline_id"]),
                            "kind": str(w["kind"]),
                            "config": w.get("config") or {},
                            "x": int(w["x"]),
                            "y": int(w["y"]),
                            "w": int(w["w"]),
                            "h": int(w["h"]),
                            "opacity": max(0, min(100, int(w.get("opacity", 100)))),
                            "layer_id": layer_id,
                        }
                    )
                else:
                    if "widget_id" not in w:
                        return JSONResponse(
                            {"error": "Widget saknar 'widget_id' eller 'inline_id'."},
                            status_code=400,
                        )

                    wid = int(w["widget_id"])
                    if wid <= 0:
                        return JSONResponse(
                            {"error": "widget_id måste vara ett positivt heltal."}, status_code=400
                        )

                    result.append(
                        {
                            "widget_id": wid,
                            "x": int(w["x"]),
                            "y": int(w["y"]),
                            "w": int(w["w"]),
                            "h": int(w["h"]),
                            "opacity": max(0, min(100, int(w.get("opacity", 100)))),
                            "layer_id": layer_id,
                        }
                    )
            except (ValueError, TypeError):
                return JSONResponse(
                    {"error": "Koordinater, dimensioner och ID:n måste vara heltal."},
                    status_code=400,
                )

        layout = {"layers": clean_layers, "widgets": result}
        _compute_z_indices(layout)
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
        layout["widgets"] = [
            w for w in layout.get("widgets", []) if w.get("widget_id") != widget_id
        ]
        view.layout_json = layout
        flag_modified(view, "layout_json")
        view.updated_at = datetime.utcnow()
        db.add(view)
        db.commit()
    return RedirectResponse(f"/admin/views/{view_id}", status_code=302)
