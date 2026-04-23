import asyncio
import logging
from datetime import datetime

import httpx
from sqlmodel import select

from app.database import get_session
from app.models import IcsCache, Widget

logger = logging.getLogger(__name__)

_ICS_KINDS = frozenset({"ics_list", "ics_month", "ics_week", "ics_schedule"})
_REFRESH_INTERVAL = 600  # sekunder


def get_ics_urls(config: dict) -> list[str]:
    """Returnerar lista med ICS-URL:er från config. Stödjer str och list."""
    raw = config.get("ics_url", "")
    if isinstance(raw, str):
        return [raw] if raw else []
    if isinstance(raw, list):
        urls = []
        for item in raw:
            if isinstance(item, str) and item:
                urls.append(item)
            elif isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
        return urls
    return []


async def fetch_and_cache(widget_id: int, source_url: str) -> None:
    """Hämtar ICS-data för en källa och uppdaterar cachen. Kastar aldrig undantag."""
    with get_session() as db:
        cache = db.get(IcsCache, (widget_id, source_url))
        etag = cache.etag if cache else None

    headers: dict[str, str] = {"User-Agent": "skarmar/1.0"}
    if etag:
        headers["If-None-Match"] = etag

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(source_url, headers=headers)

        if resp.status_code == 304:
            with get_session() as db:
                cache = db.get(IcsCache, (widget_id, source_url))
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
        _save_error(widget_id, source_url, str(exc)[:500])
        logger.warning("ICS-hämtning misslyckades för widget %d (%s): %s", widget_id, source_url, exc)
        return

    with get_session() as db:
        cache = db.get(IcsCache, (widget_id, source_url))
        now = datetime.utcnow()
        if cache:
            cache.raw_ics = raw_ics
            cache.fetched_at = now
            cache.etag = new_etag
            cache.last_error = None
        else:
            cache = IcsCache(
                widget_id=widget_id,
                source_url=source_url,
                raw_ics=raw_ics,
                fetched_at=now,
                etag=new_etag,
            )
        db.add(cache)
        db.commit()
    logger.debug("ICS-cache uppdaterad för widget %d (%d bytes)", widget_id, len(raw_ics))


def _save_error(widget_id: int, source_url: str, msg: str) -> None:
    with get_session() as db:
        cache = db.get(IcsCache, (widget_id, source_url))
        now = datetime.utcnow()
        if cache:
            cache.last_error = msg
            cache.fetched_at = now
            db.add(cache)
        else:
            db.add(IcsCache(widget_id=widget_id, source_url=source_url, raw_ics="", fetched_at=now, last_error=msg))
        db.commit()


async def refresh_all_ics() -> None:
    with get_session() as db:
        widgets = db.exec(select(Widget).where(Widget.kind.in_(list(_ICS_KINDS)))).all()
        tasks = []
        for w in widgets:
            for url in get_ics_urls(w.config_json or {}):
                tasks.append((w.id, url))

    for widget_id, url in tasks:
        try:
            await fetch_and_cache(widget_id, url)
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
