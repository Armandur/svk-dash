import asyncio
import logging
from datetime import datetime

import httpx
from sqlmodel import select

from app.database import get_session
from app.models import IcsCache, Widget

logger = logging.getLogger(__name__)

_ICS_KINDS = frozenset({"ics_list", "ics_month"})
_REFRESH_INTERVAL = 600  # sekunder


async def fetch_and_cache(widget_id: int, ics_url: str) -> None:
    """Hämtar ICS-data och uppdaterar cachen. Kastar aldrig undantag."""
    with get_session() as db:
        cache = db.get(IcsCache, widget_id)
        etag = cache.etag if cache else None

    headers: dict[str, str] = {"User-Agent": "skarmar/1.0"}
    if etag:
        headers["If-None-Match"] = etag

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(ics_url, headers=headers)

        if resp.status_code == 304:
            with get_session() as db:
                cache = db.get(IcsCache, widget_id)
                if cache:
                    cache.fetched_at = datetime.utcnow()
                    cache.last_error = None
                    db.add(cache)
                    db.commit()
            return

        resp.raise_for_status()
        raw_ics = resp.text
        new_etag = resp.headers.get("etag")

    except Exception as exc:
        _save_error(widget_id, str(exc)[:500])
        logger.warning("ICS-hämtning misslyckades för widget %d: %s", widget_id, exc)
        return

    with get_session() as db:
        cache = db.get(IcsCache, widget_id)
        now = datetime.utcnow()
        if cache:
            cache.raw_ics = raw_ics
            cache.fetched_at = now
            cache.etag = new_etag
            cache.last_error = None
        else:
            cache = IcsCache(
                widget_id=widget_id,
                raw_ics=raw_ics,
                fetched_at=now,
                etag=new_etag,
            )
        db.add(cache)
        db.commit()
    logger.debug("ICS-cache uppdaterad för widget %d (%d bytes)", widget_id, len(raw_ics))


def _save_error(widget_id: int, msg: str) -> None:
    with get_session() as db:
        cache = db.get(IcsCache, widget_id)
        now = datetime.utcnow()
        if cache:
            cache.last_error = msg
            cache.fetched_at = now
            db.add(cache)
        else:
            db.add(IcsCache(widget_id=widget_id, raw_ics="", fetched_at=now, last_error=msg))
        db.commit()


async def refresh_all_ics() -> None:
    with get_session() as db:
        widgets = db.exec(select(Widget).where(Widget.kind.in_(list(_ICS_KINDS)))).all()
        tasks = [(w.id, (w.config_json or {}).get("ics_url")) for w in widgets]

    for widget_id, ics_url in tasks:
        if not isinstance(ics_url, str) or not ics_url:
            continue
        try:
            await fetch_and_cache(widget_id, ics_url)
        except Exception:
            logger.exception("Oväntat fel vid ICS-hämtning för widget %d", widget_id)


async def start_refresh_loop() -> None:
    """Kör refresh_all_ics() var tionde minut i bakgrunden."""
    while True:
        try:
            await refresh_all_ics()
        except Exception:
            logger.exception("Oväntat fel i ICS-refresh-loop")
        await asyncio.sleep(_REFRESH_INTERVAL)
