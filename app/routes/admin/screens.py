from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlmodel import select

from app import sse as sse_registry
from app.database import get_session
from app.deps import require_admin
from app.models import (
    Channel,
    ChannelLayoutAssignment,
    LayoutZone,
    Screen,
    View,
    Widget,
    ZoneWidgetPlacement,
)
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])


def _total_video_widgets(channel_id: int, db) -> int:
    """Totalt antal video-widgets som renderas i kanalens DOM.

    V4L2-dekodern på RPi 4B/Trixie blir instabil så fort fler än EN
    <video>-tagg finns i DOM:et — även om JS-rotationen bara visar en
    åt gången. Räkningen är därför inte 'samtidigt synliga' utan
    'totalt antal som hamnar i HTML-utkasten'."""
    if channel_id is None:
        return 0

    def _entry_is_video(entry: dict) -> bool:
        if "inline_id" in entry:
            return entry.get("kind") == "video"
        widget = db.get(Widget, entry.get("widget_id"))
        return bool(widget and widget.kind == "video")

    assignments = db.exec(
        select(ChannelLayoutAssignment).where(
            ChannelLayoutAssignment.channel_id == channel_id,
            ChannelLayoutAssignment.enabled == True,  # noqa: E712
        )
    ).all()

    total = 0
    for a in assignments:
        zones = db.exec(
            select(LayoutZone).where(LayoutZone.layout_id == a.layout_id)
        ).all()
        for zone in zones:
            if zone.role == "persistent":
                placements = db.exec(
                    select(ZoneWidgetPlacement).where(
                        ZoneWidgetPlacement.zone_id == zone.id,
                        ZoneWidgetPlacement.channel_id == channel_id,
                    )
                ).all()
                if not placements:
                    placements = db.exec(
                        select(ZoneWidgetPlacement).where(
                            ZoneWidgetPlacement.zone_id == zone.id,
                            ZoneWidgetPlacement.channel_id.is_(None),
                        )
                    ).all()
                for p in placements:
                    if p.inline_kind == "video":
                        total += 1
                    elif p.widget_id:
                        w = db.get(Widget, p.widget_id)
                        if w and w.kind == "video":
                            total += 1
            else:  # schedulable: räkna alla video-widgets i alla aktiva vyer
                views = db.exec(
                    select(View).where(
                        View.channel_id == channel_id,
                        View.zone_id == zone.id,
                        View.enabled == True,  # noqa: E712
                    )
                ).all()
                for v in views:
                    for e in (v.layout_json or {}).get("widgets", []):
                        if _entry_is_video(e):
                            total += 1
    return total


def _screen_status(screen: Screen, channel_name: str | None, now: datetime) -> dict:
    conn_count = sse_registry.connection_count(screen.id)
    exp = screen.expected_connections  # 0 = övervaka ej antal

    if conn_count > 0:
        if exp > 0 and conn_count != exp:
            status = "mismatch"
        else:
            status = "online"
    elif screen.last_seen_at and (now - screen.last_seen_at).total_seconds() < 900:
        status = "recent"
    elif screen.last_seen_at:
        status = "offline"
    else:
        status = "never"

    last_seen_str = None
    if screen.last_seen_at:
        delta_s = int((now - screen.last_seen_at).total_seconds())
        if delta_s < 60:
            last_seen_str = "nyss"
        elif delta_s < 3600:
            last_seen_str = f"{delta_s // 60} min sedan"
        else:
            last_seen_str = f"{delta_s // 3600} tim sedan"

    return {
        "screen": screen,
        "channel_name": channel_name,
        "status": status,
        "conn_count": conn_count,
        "expected_conn": exp,
        "last_seen": last_seen_str,
    }


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    with get_session() as db:
        screens = db.exec(select(Screen).order_by(Screen.name)).all()
        channels = {c.id: c.name for c in db.exec(select(Channel)).all()}
        all_channels = db.exec(select(Channel).order_by(Channel.name)).all()
        
    now = datetime.utcnow()
    screen_statuses = [_screen_status(s, channels.get(s.channel_id), now) for s in screens]
    
    return HTMLResponse(
        templates.get_template("admin/index.html").render(
            request=request, 
            screen_statuses=screen_statuses,
            all_channels=all_channels
        )
    )


@router.get("/screens")
async def screens_list():
    return RedirectResponse("/admin/", status_code=302)


@router.get("/screens/new", response_class=HTMLResponse)
async def screen_new(request: Request):
    return HTMLResponse(
        templates.get_template("admin/screen_form.html").render(
            request=request, screen=None, error=None
        )
    )


@router.post("/screens/new")
async def screen_create(
    request: Request,
    name: str = Form(...),
    slug: str = Form(...),
):
    slug = slug.strip().lower()
    with get_session() as db:
        existing = db.exec(select(Screen).where(Screen.slug == slug)).first()
        if existing:
            return HTMLResponse(
                templates.get_template("admin/screen_form.html").render(
                    request=request, screen=None, error=f"Slug '{slug}' används redan."
                ),
                status_code=422,
            )
        
        screen = Screen(name=name, slug=slug, channel_id=None)
        db.add(screen)
        db.commit()
        db.refresh(screen)
    return RedirectResponse(f"/admin/screens/{screen.id}", status_code=302)


@router.get("/screens/{screen_id}", response_class=HTMLResponse)
async def screen_detail(request: Request, screen_id: int):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        current_channel = db.get(Channel, screen.channel_id) if screen.channel_id else None
        total_videos = _total_video_widgets(screen.channel_id, db)

    live_conn_count = sse_registry.connection_count(screen_id)
    capability_warning: str | None = None
    if screen.video_capability == "none" and total_videos > 0:
        capability_warning = (
            f"Skärmen är satt till «Ingen video» men kanalen innehåller "
            f"{total_videos} video-widget(s). Dessa filtreras bort i kioskvyn."
        )
    elif screen.video_capability == "single" and total_videos > 1:
        capability_warning = (
            f"Kanalen innehåller {total_videos} video-widgets totalt, men "
            f"skärmen är satt till «En video totalt». V4L2-dekodern på "
            f"RPi 4B/Trixie blir instabil så fort flera <video>-element "
            f"finns i DOM:et (även med rotation). Sätt skärmen till "
            f"«Flera samtidigt» (om hårdvaran klarar det) eller minska "
            f"antalet video-widgets i kanalen till ett."
        )

    return HTMLResponse(
        templates.get_template("admin/screen_detail.html").render(
            request=request,
            screen=screen,
            current_channel=current_channel,
            live_conn_count=live_conn_count,
            total_videos=total_videos,
            capability_warning=capability_warning,
        )
    )


@router.get("/screens/{screen_id}/connections")
async def screen_connections(request: Request, screen_id: int):
    return JSONResponse(sse_registry.get_clients(screen_id))


@router.get("/screens/{screen_id}/edit", response_class=HTMLResponse)
async def screen_edit_form(request: Request, screen_id: int):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        channels = db.exec(select(Channel).order_by(Channel.name)).all()
        current_channel = db.get(Channel, screen.channel_id) if screen.channel_id else None

    return HTMLResponse(
        templates.get_template("admin/screen_edit.html").render(
            request=request,
            screen=screen,
            channels=channels,
            current_channel=current_channel,
            error=None,
        )
    )


@router.post("/screens/{screen_id}/edit")
async def screen_edit(
    request: Request,
    screen_id: int,
    name: str = Form(...),
    slug: str = Form(...),
    channel_id: str | None = Form(None),
    expected_connections: str | None = Form(None),
    show_offline_banner: str | None = Form(None),
    performance_mode: str = Form("normal"),
    video_capability: str = Form("single"),
):
    slug = slug.strip().lower()
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
            
        conflict = db.exec(
            select(Screen).where(Screen.slug == slug, Screen.id != screen_id)
        ).first()
        if conflict:
            channels = db.exec(select(Channel).order_by(Channel.name)).all()
            current_channel = db.get(Channel, screen.channel_id) if screen.channel_id else None
            return HTMLResponse(
                templates.get_template("admin/screen_edit.html").render(
                    request=request,
                    screen=screen,
                    channels=channels,
                    current_channel=current_channel,
                    error=f"Slug '{slug}' används redan.",
                ),
                status_code=422,
            )
            
        screen.name = name
        screen.slug = slug
        screen.channel_id = int(channel_id) if channel_id else None
        screen.expected_connections = max(0, int(expected_connections)) if expected_connections and expected_connections.isdigit() else 0
        screen.show_offline_banner = show_offline_banner is not None
        screen.performance_mode = performance_mode
        if video_capability in ("none", "single", "multi"):
            screen.video_capability = video_capability
        screen.updated_at = datetime.utcnow()
        db.add(screen)
        db.commit()
    
    sse_registry.broadcast(screen_id, {"type": "reload"})
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/delete")
async def screen_delete(screen_id: int):
    with get_session() as db:
        screen = db.get(Screen, screen_id)
        if not screen:
            return HTMLResponse("Skärmen hittades inte.", status_code=404)
        db.delete(screen)
        db.commit()
    return RedirectResponse("/admin/screens", status_code=302)


@router.post("/screens/batch-assign-channel")
async def screen_batch_assign_channel(
    screen_ids: list[int] = Form(...),
    channel_id: str | None = Form(None),
):
    target_channel_id = int(channel_id) if channel_id else None
    with get_session() as db:
        for sid in screen_ids:
            screen = db.get(Screen, sid)
            if screen:
                screen.channel_id = target_channel_id
                db.add(screen)
        db.commit()
        
    # Broadcast reload to all affected screens
    for sid in screen_ids:
        sse_registry.broadcast(sid, {"type": "reload"})
        
    return RedirectResponse("/admin/screens", status_code=302)
