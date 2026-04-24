import copy
import json
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import Text, cast, or_
from sqlalchemy.orm.attributes import flag_modified
from sqlmodel import select

from app.config import UPLOADS_DIR
from app.database import get_session
from app.deps import require_admin
from app.models import MediaFile, MediaFolder, Screen, View, Widget
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])

_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "application/pdf": ".pdf",
}


def _breadcrumbs(folder_id: int | None, folders_by_id: dict) -> list[dict]:
    """Bygg brödsmulsstig från rot till aktuell mapps förälder (ej aktuell mapp själv)."""
    current = folders_by_id.get(folder_id) if folder_id else None
    crumbs = []
    fid = current.parent_id if current else None
    while fid is not None:
        f = folders_by_id.get(fid)
        if not f:
            break
        crumbs.insert(0, {"id": f.id, "name": f.name})
        fid = f.parent_id
    return crumbs


def _purge_media_id(obj, media_id: int):
    """Ta bort list-items och nollställ strängar kopplade till media_id."""
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "media_id" and v == media_id:
                obj[k] = None
            else:
                _purge_media_id(v, media_id)
        # Om dict har media_id=None och url="", ta bort url-fältet
        if obj.get("media_id") is None and obj.get("url") == "":
            obj.pop("url", None)
    elif isinstance(obj, list):
        to_remove = [
            i for i, v in enumerate(obj) if isinstance(v, dict) and v.get("media_id") == media_id
        ]
        for i in reversed(to_remove):
            obj.pop(i)
        for v in obj:
            _purge_media_id(v, media_id)


def _purge_refs(obj, filename: str):
    """Rekursivt rensa filename ur dict/lista.
    List-items (dict) som innehåller filnamnet tas bort helt (t.ex. bildspels-items).
    Strängar som innehåller filnamnet sätts till tom sträng."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and filename in v:
                obj[k] = ""
            else:
                _purge_refs(v, filename)
    elif isinstance(obj, list):
        to_remove = [
            i for i, v in enumerate(obj) if isinstance(v, dict) and filename in json.dumps(v)
        ]
        for i in reversed(to_remove):
            obj.pop(i)
        for v in obj:
            if not isinstance(v, (dict, list)):
                pass  # strängar i platta listor är ovanliga, skippa
            else:
                _purge_refs(v, filename)


def _purge_file_from_db(db, filename: str, media_id: int | None = None) -> None:
    """Ta bort alla referenser till filen ur widgets och vyer.
    Söker på media_id (nyare data) och filnamn (äldre data)."""
    mid_str = str(media_id) if media_id else None

    # Widgets
    w_conds = [cast(Widget.config_json, Text).like(f"%{filename}%")]
    if mid_str:
        w_conds.append(cast(Widget.config_json, Text).like(f"%{mid_str}%"))
    widgets = db.exec(select(Widget).where(or_(*w_conds))).all()

    for w in widgets:
        cfg = copy.deepcopy(w.config_json or {})
        _purge_refs(cfg, filename)
        if mid_str:
            _purge_media_id(cfg, media_id)
        w.config_json = cfg
        flag_modified(w, "config_json")
        db.add(w)

    # Views
    v_conds = [cast(View.layout_json, Text).like(f"%{filename}%")]
    if mid_str:
        v_conds.append(cast(View.layout_json, Text).like(f"%{mid_str}%"))
    views = db.exec(select(View).where(or_(*v_conds))).all()

    for v in views:
        layout = copy.deepcopy(v.layout_json or {})
        _purge_refs(layout, filename)
        if mid_str:
            _purge_media_id(layout, media_id)
        v.layout_json = layout
        flag_modified(v, "layout_json")
        db.add(v)


def _find_usages(filename: str, widgets: list, views: list, channel_to_screen: dict) -> list[dict]:
    needle = filename
    usages = []
    for w in widgets:
        if needle in json.dumps(w.config_json or {}):
            usages.append(
                {"kind": "widget", "id": w.id, "name": w.name, "url": f"/admin/widgets/{w.id}"}
            )
    for v in views:
        if needle in json.dumps(v.layout_json or {}):
            screen = channel_to_screen.get(v.channel_id)
            screen_name = screen.name if screen else f"Kanal {v.channel_id}"
            usages.append(
                {
                    "kind": "view",
                    "id": v.id,
                    "name": v.name,
                    "screen_name": screen_name,
                    "url": f"/admin/views/{v.id}",
                }
            )
    return usages


@router.get("/media", response_class=HTMLResponse)
async def media_list(request: Request, folder_id: int | None = None):
    with get_session() as db:
        all_folders = db.exec(select(MediaFolder).order_by(MediaFolder.name)).all()
        folders_by_id = {f.id: f for f in all_folders}
        subfolders = [f for f in all_folders if f.parent_id == folder_id]
        files = db.exec(
            select(MediaFile)
            .where(MediaFile.folder_id == folder_id)
            .order_by(MediaFile.created_at.desc())
        ).all()

        # Optimering: Hämta bara widgets och vyer som faktiskt innehåller någon av filerna i mappen
        filenames = [f.filename for f in files]
        widgets = []
        views = []
        if filenames:
            w_conds = [cast(Widget.config_json, Text).like(f"%{fn}%") for fn in filenames]
            widgets = db.exec(select(Widget).where(or_(*w_conds))).all()
            v_conds = [cast(View.layout_json, Text).like(f"%{fn}%") for fn in filenames]
            views = db.exec(select(View).where(or_(*v_conds))).all()

        screens = db.exec(select(Screen)).all()
        channel_to_screen = {s.channel_id: s for s in screens}

    crumbs = _breadcrumbs(folder_id, folders_by_id)
    files_with_usage = [
        {"file": f, "usages": _find_usages(f.filename, widgets, views, channel_to_screen)} for f in files
    ]
    current_folder = folders_by_id.get(folder_id) if folder_id else None
    return HTMLResponse(
        templates.get_template("admin/media.html").render(
            request=request,
            files_with_usage=files_with_usage,
            subfolders=subfolders,
            all_folders=all_folders,
            current_folder=current_folder,
            current_folder_id=folder_id,
            crumbs=crumbs,
        )
    )


@router.post("/media/upload", response_class=JSONResponse)
async def media_upload(file: UploadFile = File(...), folder_id: str = Form("")):
    content_type = (file.content_type or "").split(";")[0].strip()
    ext = _ALLOWED_TYPES.get(content_type)
    if not ext:
        return JSONResponse(
            {"error": "Filtypen stöds inte. Tillåtna: jpg, png, gif, webp, svg, mp4, webm, pdf."}, status_code=400
        )
    fid = int(folder_id) if folder_id.strip().isdigit() else None
    data = await file.read()
    filename = uuid.uuid4().hex + ext
    dest = Path(UPLOADS_DIR) / filename
    dest.write_bytes(data)
    with get_session() as db:
        mf = MediaFile(
            filename=filename,
            original_name=file.filename or filename,
            content_type=content_type,
            size_bytes=len(data),
            folder_id=fid,
        )
        db.add(mf)
        db.commit()
        db.refresh(mf)
    return JSONResponse(
        {
            "id": mf.id,
            "filename": filename,
            "url": f"/uploads/{filename}",
            "original_name": mf.original_name,
        }
    )


@router.post("/media/{file_id}/replace", response_class=JSONResponse)
async def media_replace(file_id: int, file: UploadFile = File(...)):
    content_type = (file.content_type or "").split(";")[0].strip()
    ext = _ALLOWED_TYPES.get(content_type)
    if not ext:
        return JSONResponse({"error": "Filtypen stöds inte."}, status_code=400)
    with get_session() as db:
        mf = db.get(MediaFile, file_id)
        if not mf:
            return JSONResponse({"error": "Filen hittades inte."}, status_code=404)
        data = await file.read()
        dest = Path(UPLOADS_DIR) / mf.filename
        dest.write_bytes(data)
        mf.original_name = file.filename or mf.original_name
        mf.content_type = content_type
        mf.size_bytes = len(data)
        mf.updated_at = datetime.utcnow()
        db.add(mf)
        db.commit()
    return JSONResponse({"ok": True, "url": f"/uploads/{mf.filename}"})


@router.post("/media/{file_id}/delete")
async def media_delete(request: Request, file_id: int):
    with get_session() as db:
        mf = db.get(MediaFile, file_id)
        if not mf:
            return HTMLResponse("Filen hittades inte.", status_code=404)
        folder_id = mf.folder_id
        filename = mf.filename
        file_id = mf.id
        path = Path(UPLOADS_DIR) / filename
        if path.exists():
            path.unlink()
        _purge_file_from_db(db, filename, file_id)
        db.delete(mf)
        db.commit()
    redirect = "/admin/media" + (f"?folder_id={folder_id}" if folder_id else "")
    return RedirectResponse(redirect, status_code=302)


@router.post("/media/{file_id}/move")
async def media_move(request: Request, file_id: int, folder_id: str = Form("")):
    with get_session() as db:
        mf = db.get(MediaFile, file_id)
        if not mf:
            return HTMLResponse("Filen hittades inte.", status_code=404)
        old_folder = mf.folder_id
        mf.folder_id = int(folder_id) if folder_id.strip().isdigit() else None
        db.add(mf)
        db.commit()
    redirect = "/admin/media" + (f"?folder_id={old_folder}" if old_folder else "")
    return RedirectResponse(redirect, status_code=302)


@router.post("/media/batch")
async def media_batch(
    request: Request,
    action: str = Form(...),
    file_ids: str = Form(""),
    folder_id: str = Form(""),
    current_folder_id: str = Form(""),
):
    ids = [int(i) for i in file_ids.split(",") if i.strip().isdigit()]
    target_folder = int(folder_id) if folder_id.strip().isdigit() else None
    cur_folder = int(current_folder_id) if current_folder_id.strip().isdigit() else None
    with get_session() as db:
        for fid in ids:
            mf = db.get(MediaFile, fid)
            if not mf:
                continue
            if action == "delete":
                path = Path(UPLOADS_DIR) / mf.filename
                if path.exists():
                    path.unlink()
                _purge_file_from_db(db, mf.filename, mf.id)
                db.delete(mf)
            elif action == "move":
                mf.folder_id = target_folder
                db.add(mf)
        db.commit()
    redirect = "/admin/media" + (f"?folder_id={cur_folder}" if cur_folder else "")
    return RedirectResponse(redirect, status_code=302)


@router.post("/media/folders/new")
async def folder_new(request: Request, name: str = Form(...), parent_id: str = Form("")):
    pid = int(parent_id) if parent_id.strip().isdigit() else None
    with get_session() as db:
        folder = MediaFolder(name=name.strip(), parent_id=pid)
        db.add(folder)
        db.commit()
    redirect = "/admin/media" + (f"?folder_id={pid}" if pid else "")
    return RedirectResponse(redirect, status_code=302)


@router.post("/media/folders/{folder_id}/delete")
async def folder_delete(request: Request, folder_id: int):
    with get_session() as db:
        folder = db.get(MediaFolder, folder_id)
        if not folder:
            return HTMLResponse("Mappen hittades inte.", status_code=404)
        has_files = db.exec(select(MediaFile).where(MediaFile.folder_id == folder_id)).first()
        has_subfolders = db.exec(
            select(MediaFolder).where(MediaFolder.parent_id == folder_id)
        ).first()
        if has_files or has_subfolders:
            return HTMLResponse("Mappen är inte tom.", status_code=409)
        parent_id = folder.parent_id
        db.delete(folder)
        db.commit()
    redirect = "/admin/media" + (f"?folder_id={parent_id}" if parent_id else "")
    return RedirectResponse(redirect, status_code=302)


@router.get("/media/picker", response_class=JSONResponse)
async def media_picker(request: Request):
    with get_session() as db:
        files = db.exec(select(MediaFile).order_by(MediaFile.created_at.desc())).all()
        folders = db.exec(select(MediaFolder).order_by(MediaFolder.name)).all()
    return JSONResponse(
        {
            "files": [
                {
                    "id": f.id,
                    "filename": f.filename,
                    "url": f"/uploads/{f.filename}",
                    "original_name": f.original_name,
                    "folder_id": f.folder_id,
                    "content_type": f.content_type,
                }
                for f in files
            ],
            "folders": [{"id": f.id, "name": f.name, "parent_id": f.parent_id} for f in folders],
        }
    )
