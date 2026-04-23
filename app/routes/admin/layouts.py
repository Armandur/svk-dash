from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select

from app.database import get_session
from app.deps import require_admin
from app.models import Layout, LayoutZone, ZoneWidgetPlacement
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])

ASPECT_RATIOS = [
    ("16:9", "16:9 (landskap)"),
    ("9:16", "9:16 (porträtt)"),
    ("4:3",  "4:3"),
    ("1:1",  "1:1 (kvadrat)"),
]


def _render(template_name: str, ctx: dict) -> HTMLResponse:
    return HTMLResponse(templates.get_template(template_name).render(**ctx))


# ── Lista ─────────────────────────────────────────────────────────────────────

@router.get("/layouts", response_class=HTMLResponse)
async def layouts_list(request: Request):
    with get_session() as db:
        layouts = db.exec(select(Layout).order_by(Layout.name)).all()
        zone_counts = {
            layout.id: len(db.exec(
                select(LayoutZone).where(LayoutZone.layout_id == layout.id)
            ).all())
            for layout in layouts
        }
    return _render("admin/layouts.html", {
        "request": request,
        "layouts": layouts,
        "zone_counts": zone_counts,
    })


# ── Skapa ─────────────────────────────────────────────────────────────────────

@router.get("/layouts/new", response_class=HTMLResponse)
async def layout_new_form(request: Request):
    return _render("admin/layout_form.html", {
        "request": request,
        "layout": None,
        "aspect_ratios": ASPECT_RATIOS,
        "error": None,
    })


@router.post("/layouts/new")
async def layout_new(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    aspect_ratio: str = Form("16:9"),
):
    name = name.strip()
    if not name:
        return _render("admin/layout_form.html", {
            "request": request,
            "layout": None,
            "aspect_ratios": ASPECT_RATIOS,
            "error": "Namn krävs.",
        })
    with get_session() as db:
        layout = Layout(name=name, description=description, aspect_ratio=aspect_ratio)
        db.add(layout)
        db.commit()
        db.refresh(layout)
        lid = layout.id
    return RedirectResponse(f"/admin/layouts/{lid}", status_code=302)


# ── Detalj / zon-editor ───────────────────────────────────────────────────────

@router.get("/layouts/{layout_id}", response_class=HTMLResponse)
async def layout_detail(request: Request, layout_id: int):
    with get_session() as db:
        layout = db.get(Layout, layout_id)
        if not layout:
            return RedirectResponse("/admin/layouts", status_code=302)
        zones = db.exec(
            select(LayoutZone)
            .where(LayoutZone.layout_id == layout_id)
            .order_by(LayoutZone.z_index)
        ).all()
    return _render("admin/layout_detail.html", {
        "request": request,
        "layout": layout,
        "zones": zones,
        "aspect_ratios": ASPECT_RATIOS,
    })


# ── Spara metadata ────────────────────────────────────────────────────────────

@router.post("/layouts/{layout_id}/edit")
async def layout_edit(
    layout_id: int,
    name: str = Form(...),
    description: str = Form(""),
    aspect_ratio: str = Form("16:9"),
):
    with get_session() as db:
        layout = db.get(Layout, layout_id)
        if not layout:
            return RedirectResponse("/admin/layouts", status_code=302)
        layout.name = name.strip()
        layout.description = description
        layout.aspect_ratio = aspect_ratio
        layout.updated_at = datetime.utcnow()
        db.add(layout)
        db.commit()
    return RedirectResponse(f"/admin/layouts/{layout_id}", status_code=302)


# ── Spara zoner (JSON API från zon-editorn) ───────────────────────────────────

@router.post("/layouts/{layout_id}/zones/save")
async def zones_save(request: Request, layout_id: int):
    body = await request.json()
    zones_data = body.get("zones", [])

    with get_session() as db:
        layout = db.get(Layout, layout_id)
        if not layout:
            return {"error": "Layout saknas"}

        incoming_ids = {z["id"] for z in zones_data if z.get("id")}
        existing = db.exec(
            select(LayoutZone).where(LayoutZone.layout_id == layout_id)
        ).all()
        for zone in existing:
            if zone.id not in incoming_ids:
                db.delete(zone)

        for z in zones_data:
            if z.get("id"):
                zone = db.get(LayoutZone, z["id"]) or LayoutZone(layout_id=layout_id)
            else:
                zone = LayoutZone(layout_id=layout_id)

            zone.name      = z.get("name", "Zon")
            zone.role      = z.get("role", "schedulable")
            zone.x_pct     = float(z.get("x_pct", 0))
            zone.y_pct     = float(z.get("y_pct", 0))
            zone.w_pct     = float(z.get("w_pct", 100))
            zone.h_pct     = float(z.get("h_pct", 100))
            zone.grid_cols = int(z.get("grid_cols", 12))
            zone.grid_rows = int(z.get("grid_rows", 9))
            zone.z_index   = int(z.get("z_index", 0))
            db.add(zone)

        layout.updated_at = datetime.utcnow()
        db.add(layout)
        db.commit()

    return {"ok": True}


# ── Ta bort layout ────────────────────────────────────────────────────────────

@router.post("/layouts/{layout_id}/delete")
async def layout_delete(layout_id: int):
    with get_session() as db:
        zones = db.exec(
            select(LayoutZone).where(LayoutZone.layout_id == layout_id)
        ).all()
        for zone in zones:
            for p in db.exec(
                select(ZoneWidgetPlacement).where(ZoneWidgetPlacement.zone_id == zone.id)
            ).all():
                db.delete(p)
            db.delete(zone)
        layout = db.get(Layout, layout_id)
        if layout:
            db.delete(layout)
        db.commit()
    return RedirectResponse("/admin/layouts", status_code=302)
