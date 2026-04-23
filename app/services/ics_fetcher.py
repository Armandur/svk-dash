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


async def _fetch_raw(url: str, etag: str | None) -> tuple[str | None, str | None, str | None]:
    """Hämtar en ICS-URL. Returnerar (raw_ics, new_etag, error_msg).
    raw_ics är None vid 304 Not Modified."""
    headers: dict[str, str] = {"User-Agent": "skarmar/1.0"}
    if etag:
        headers["If-None-Match"] = etag
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 304:
            return None, etag, None
        resp.raise_for_status()
        return resp.text, resp.headers.get("etag"), None
    except Exception as exc:
        return None, None, str(exc)[:500]


def _write_cache(widget_id: int, source_url: str, raw_ics: str | None, etag: str | None, error: str | None) -> None:
    with get_session() as db:
        cache = db.get(IcsCache, (widget_id, source_url))
        now = datetime.utcnow()
        if cache:
            if raw_ics is not None:
                cache.raw_ics = raw_ics
                cache.etag = etag
            cache.fetched_at = now
            cache.last_error = error
        else:
            cache = IcsCache(
                widget_id=widget_id,
                source_url=source_url,
                raw_ics=raw_ics or "",
                fetched_at=now,
                etag=etag,
                last_error=error,
            )
        db.add(cache)
        db.commit()


async def fetch_and_cache(widget_id: int, source_url: str) -> None:
    """Hämtar ICS-data för en källa och uppdaterar cachen. Kastar aldrig undantag."""
    with get_session() as db:
        cache = db.get(IcsCache, (widget_id, source_url))
        etag = cache.etag if cache else None

    raw_ics, new_etag, error = await _fetch_raw(source_url, etag)
    if error:
        logger.warning("ICS-hämtning misslyckades för widget %d (%s): %s", widget_id, source_url, error)
    else:
        logger.debug("ICS-cache uppdaterad för widget %d (%s)", widget_id, source_url)
    _write_cache(widget_id, source_url, raw_ics, new_etag, error)


async def refresh_all_ics() -> None:
    """Hämtar varje unik ICS-URL en gång och skriver resultatet till alla widgets som använder den."""
    with get_session() as db:
        widgets = db.exec(select(Widget).where(Widget.kind.in_(list(_ICS_KINDS)))).all()

    # Samla url -> [widget_id, ...]
    url_to_widgets: dict[str, list[int]] = {}
    for w in widgets:
        for url in get_ics_urls(w.config_json or {}):
            url_to_widgets.setdefault(url, []).append(w.id)

    for url, widget_ids in url_to_widgets.items():
        # Hämta befintlig etag från första widget (alla delar samma data)
        with get_session() as db:
            first_cache = db.get(IcsCache, (widget_ids[0], url))
            etag = first_cache.etag if first_cache else None

        try:
            raw_ics, new_etag, error = await _fetch_raw(url, etag)
        except Exception as exc:
            error = str(exc)[:500]
            raw_ics, new_etag = None, None
            logger.exception("Oväntat fel vid ICS-hämtning (%s)", url)

        if error:
            logger.warning("ICS-hämtning misslyckades (%s): %s", url, error)
        else:
            logger.debug("ICS hämtad (%s) → %d widget(s)", url, len(widget_ids))

        for widget_id in widget_ids:
            _write_cache(widget_id, url, raw_ics, new_etag, error)


async def start_refresh_loop() -> None:
    """Kör refresh_all_ics() var tionde minut i bakgrunden."""
    while True:
        try:
            await refresh_all_ics()
        except Exception:
            logger.exception("Oväntat fel i ICS-refresh-loop")
        await asyncio.sleep(_REFRESH_INTERVAL)
