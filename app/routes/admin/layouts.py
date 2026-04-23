from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select

from app.database import get_session
from app.deps import require_admin
from app.models import (
    Layout,
    LayoutRevision,
    LayoutZone,
    Screen,
    ScreenLayoutAssignment,
    ZoneWidgetPlacement,
)
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])

ASPECT_RATIOS = [
    ("16:9", "16:9 (landskap)"),
    ("9:16", "9:16 (porträtt)"),
    ("4:3", "4:3"),
    ("1:1", "1:1 (kvadrat)"),
]


def _render(template_name: str, ctx: dict) -> HTMLResponse:
    return HTMLResponse(templates.get_template(template_name).render(**ctx))


# ── Lista ─────────────────────────────────────────────────────────────────────


@router.get("/layouts", response_class=HTMLResponse)
async def layouts_list(request: Request):
    with get_session() as db:
        layouts = db.exec(select(Layout).order_by(Layout.name)).all()
        zone_counts = {
            layout.id: len(
                db.exec(select(LayoutZone).where(LayoutZone.layout_id == layout.id)).all()
            )
            for layout in layouts
        }
        assignments = db.exec(select(ScreenLayoutAssignment)).all()
        screens_by_id = {s.id: s for s in db.exec(select(Screen)).all()}
        screen_usages: dict[int, list[dict]] = {}
        for a in assignments:
            screen_usages.setdefault(a.layout_id, []).append(
                {
                    "id": a.screen_id,
                    "name": screens_by_id[a.screen_id].name
                    if a.screen_id in screens_by_id
                    else "?",
                }
            )
    return _render(
        "admin/layouts.html",
        {
            "request": request,
            "layouts": layouts,
            "zone_counts": zone_counts,
            "screen_usages": screen_usages,
        },
    )


# ── Skapa ─────────────────────────────────────────────────────────────────────


@router.get("/layouts/new", response_class=HTMLResponse)
async def layout_new_form(request: Request):
    return _render(
        "admin/layout_form.html",
        {
            "request": request,
            "layout": None,
            "aspect_ratios": ASPECT_RATIOS,
            "error": None,
        },
    )


@router.post("/layouts/new")
async def layout_new(
    request: Request,
    name: str = Form(...),
    description: str = Form(""),
    aspect_ratio: str = Form("16:9"),
):
    name = name.strip()
    if not name:
        return _render(
            "admin/layout_form.html",
            {
                "request": request,
                "layout": None,
                "aspect_ratios": ASPECT_RATIOS,
                "error": "Namn krävs.",
            },
        )
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
            select(LayoutZone).where(LayoutZone.layout_id == layout_id).order_by(LayoutZone.z_index)
        ).all()
        zones_data = [
            {
                "id": z.id,
                "name": z.name,
                "role": z.role,
                "x_pct": z.x_pct,
                "y_pct": z.y_pct,
                "w_pct": z.w_pct,
                "h_pct": z.h_pct,
                "grid_cols": z.grid_cols,
                "grid_rows": z.grid_rows,
                "z_index": z.z_index,
                "rotation_seconds": z.rotation_seconds,
                "transition": z.transition,
                "transition_direction": z.transition_direction,
            }
            for z in zones
        ]
        revisions = db.exec(
            select(LayoutRevision)
            .where(LayoutRevision.layout_id == layout_id)
            .order_by(LayoutRevision.saved_at.desc())
        ).all()
    return _render(
        "admin/layout_detail.html",
        {
            "request": request,
            "layout": layout,
            "zones": zones_data,
            "revisions": revisions,
            "aspect_ratios": ASPECT_RATIOS,
        },
    )


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
        existing = db.exec(select(LayoutZone).where(LayoutZone.layout_id == layout_id)).all()
        for zone in existing:
            if zone.id not in incoming_ids:
                db.delete(zone)

        for z in zones_data:
            if z.get("id"):
                zone = db.get(LayoutZone, z["id"]) or LayoutZone(layout_id=layout_id)
            else:
                zone = LayoutZone(layout_id=layout_id)

            zone.name = z.get("name", "Zon")
            zone.role = z.get("role", "schedulable")
            zone.x_pct = float(z.get("x_pct", 0))
            zone.y_pct = float(z.get("y_pct", 0))
            zone.w_pct = float(z.get("w_pct", 100))
            zone.h_pct = float(z.get("h_pct", 100))
            zone.grid_cols = int(z.get("grid_cols", 12))
            zone.grid_rows = int(z.get("grid_rows", 9))
            zone.z_index = int(z.get("z_index", 0))
            zone.rotation_seconds = int(z.get("rotation_seconds", 30))
            zone.transition = z.get("transition", "fade")
            zone.transition_direction = z.get("transition_direction", "left")
            db.add(zone)

        layout.updated_at = datetime.utcnow()
        db.add(layout)

        # Spara revision
        existing_zones = db.exec(select(LayoutZone).where(LayoutZone.layout_id == layout_id)).all()
        snapshot = [
            {
                "id": z.id,
                "name": z.name,
                "role": z.role,
                "x_pct": z.x_pct,
                "y_pct": z.y_pct,
                "w_pct": z.w_pct,
                "h_pct": z.h_pct,
                "grid_cols": z.grid_cols,
                "grid_rows": z.grid_rows,
                "z_index": z.z_index,
                "rotation_seconds": z.rotation_seconds,
                "transition": z.transition,
                "transition_direction": z.transition_direction,
            }
            for z in existing_zones
        ]
        db.add(LayoutRevision(layout_id=layout_id, zones_json=snapshot))
        db.commit()
        _prune_revisions(db, layout_id)

    return {"ok": True}


def _prune_revisions(db, layout_id: int) -> None:
    revisions = db.exec(
        select(LayoutRevision)
        .where(LayoutRevision.layout_id == layout_id)
        .order_by(LayoutRevision.saved_at.desc())
    ).all()
    for old in revisions[20:]:
        db.delete(old)
    db.commit()


# ── Återställ revision ────────────────────────────────────────────────────────


@router.post("/layouts/{layout_id}/revert/{revision_id}")
async def layout_revert(layout_id: int, revision_id: int):
    with get_session() as db:
        layout = db.get(Layout, layout_id)
        revision = db.get(LayoutRevision, revision_id)
        if not layout or not revision or revision.layout_id != layout_id:
            return RedirectResponse(f"/admin/layouts/{layout_id}", status_code=302)

        # Ta bort befintliga zoner
        existing = db.exec(select(LayoutZone).where(LayoutZone.layout_id == layout_id)).all()
        for z in existing:
            db.delete(z)

        # Återskapa från snapshot (utan id — nya rader)
        for z in revision.zones_json:
            db.add(
                LayoutZone(
                    layout_id=layout_id,
                    name=z.get("name", "Zon"),
                    role=z.get("role", "schedulable"),
                    x_pct=float(z.get("x_pct", 0)),
                    y_pct=float(z.get("y_pct", 0)),
                    w_pct=float(z.get("w_pct", 100)),
                    h_pct=float(z.get("h_pct", 100)),
                    grid_cols=int(z.get("grid_cols", 12)),
                    grid_rows=int(z.get("grid_rows", 9)),
                    z_index=int(z.get("z_index", 0)),
                    rotation_seconds=int(z.get("rotation_seconds", 30)),
                    transition=z.get("transition", "fade"),
                    transition_direction=z.get("transition_direction", "left"),
                )
            )

        layout.updated_at = datetime.utcnow()
        db.add(layout)
        db.commit()
    return RedirectResponse(f"/admin/layouts/{layout_id}", status_code=302)


# ── Ta bort layout ────────────────────────────────────────────────────────────


@router.post("/layouts/{layout_id}/delete")
async def layout_delete(layout_id: int):
    with get_session() as db:
        zones = db.exec(select(LayoutZone).where(LayoutZone.layout_id == layout_id)).all()
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
