from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import select

from app.database import get_session
from app.deps import require_admin
from app.models import BrandColor
from app.templating import templates

router = APIRouter(tags=["palette"])

@router.get("", dependencies=[Depends(require_admin)])
async def palette_list(request: Request):
    with get_session() as db:
        colors = db.exec(select(BrandColor).order_by(BrandColor.position, BrandColor.id)).all()
    return HTMLResponse(
        templates.get_template("admin/palette.html").render(request=request, colors=colors)
    )

@router.post("/add", dependencies=[Depends(require_admin)])
async def palette_add(request: Request, name: str = Form(...), color: str = Form(...)):
    if not color.strip():
        return RedirectResponse("/admin/palette", status_code=302)
    with get_session() as db:
        max_pos = db.exec(select(BrandColor)).all()
        position = max((c.position for c in max_pos), default=-1) + 1
        bc = BrandColor(name=name.strip(), color=color.strip(), position=position)
        db.add(bc)
        db.commit()
    return RedirectResponse("/admin/palette", status_code=302)

@router.post("/{color_id}/delete", dependencies=[Depends(require_admin)])
async def palette_delete(request: Request, color_id: int):
    with get_session() as db:
        bc = db.get(BrandColor, color_id)
        if bc:
            db.delete(bc)
            db.commit()
    return RedirectResponse("/admin/palette", status_code=302)

@router.post("/{color_id}/rename", dependencies=[Depends(require_admin)])
async def palette_rename(request: Request, color_id: int, name: str = Form(...)):
    with get_session() as db:
        bc = db.get(BrandColor, color_id)
        if bc and name.strip():
            bc.name = name.strip()
            db.add(bc)
            db.commit()
    return RedirectResponse("/admin/palette", status_code=302)

@router.post("/reorder", dependencies=[Depends(require_admin)])
async def palette_reorder(request: Request):
    data = await request.json()  # [{id: int, position: int}, ...]
    with get_session() as db:
        for item in data:
            bc = db.get(BrandColor, item["id"])
            if bc:
                bc.position = item["position"]
                db.add(bc)
        db.commit()
    return JSONResponse({"ok": True})
