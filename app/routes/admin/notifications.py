from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select, delete

from app.database import get_session
from app.deps import require_admin
from app.models import Notification
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/", response_class=HTMLResponse)
async def list_notifications(request: Request):
    with get_session() as db:
        notifications = db.exec(
            select(Notification).order_by(Notification.created_at.desc())
        ).all()
    return HTMLResponse(
        templates.get_template("admin/notifications.html").render(
            request=request,
            notifications=notifications,
        )
    )


@router.post("/seen-all")
async def seen_all_notifications():
    with get_session() as db:
        notifications = db.exec(select(Notification).where(Notification.seen_at == None)).all()  # noqa: E711
        now = datetime.utcnow()
        for n in notifications:
            n.seen_at = now
            db.add(n)
        db.commit()
    return RedirectResponse("/admin/notifications/", status_code=303)


@router.post("/clear")
async def clear_seen_notifications():
    with get_session() as db:
        db.exec(delete(Notification).where(Notification.seen_at != None))  # noqa: E711
        db.commit()
    return RedirectResponse("/admin/notifications/", status_code=303)
