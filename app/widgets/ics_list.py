import html as html_mod
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
from sqlmodel import select

from app.database import get_session
from app.models import IcsCache
from app.services.ics_fetcher import get_ics_urls

_TZ = ZoneInfo("Europe/Stockholm")

_WEEKDAYS = ["Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag", "Lördag", "Söndag"]
_MONTHS = [
    "",
    "januari",
    "februari",
    "mars",
    "april",
    "maj",
    "juni",
    "juli",
    "augusti",
    "september",
    "oktober",
    "november",
    "december",
]


def _to_local(dt) -> datetime:
    if isinstance(dt, datetime):
        return dt.astimezone(_TZ) if dt.tzinfo else dt.replace(tzinfo=_TZ)
    return datetime(dt.year, dt.month, dt.day, tzinfo=_TZ)


def _is_all_day(dt) -> bool:
    return not isinstance(dt, datetime)


def _fmt_day(d: date, today: date) -> str:
    if d == today:
        return "Idag"
    if d == today + timedelta(days=1):
        return "Imorgon"
    return f"{_WEEKDAYS[d.weekday()]} {d.day} {_MONTHS[d.month]}"


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    widget_id = context.get("widget_id")
    urls = get_ics_urls(config)
    days_ahead = max(1, int(config.get("days_ahead", 14)))
    max_events = max(1, int(config.get("max_events", 20)))
    show_location = bool(config.get("show_location", True))
    group_by_day = bool(config.get("group_by_day", True))
    font_size = config.get("font_size", "normal")  # small | normal | large

    size_cls = {"small": "ics-sm", "large": "ics-lg"}.get(font_size, "")

    if not widget_id or not urls:
        return '<div class="widget-ics-list ics-notice">Ingen ICS-URL konfigurerad.</div>'

    with get_session() as db:
        caches = db.exec(select(IcsCache).where(IcsCache.widget_id == widget_id)).all()

    if not caches:
        return '<div class="widget-ics-list ics-notice">Kalender hämtas…</div>'

    cache_by_url = {c.source_url: c for c in caches}
    today_local = datetime.now(_TZ).date()
    end_date = today_local + timedelta(days=days_ahead)

    events: list[tuple[datetime, bool, str, str]] = []
    has_error = False
    oldest_fetched: datetime | None = None

    for url in urls:
        cache = cache_by_url.get(url)
        if cache is None:
            continue
        if cache.last_error:
            has_error = True
        if not cache.raw_ics:
            continue
        if oldest_fetched is None or cache.fetched_at < oldest_fetched:
            oldest_fetched = cache.fetched_at
        try:
            cal = icalendar.Calendar.from_ical(cache.raw_ics)
            raw_events = recurring_ical_events.of(cal).between(today_local, end_date)
        except Exception:
            has_error = True
            continue

        for ev in raw_events:
            dtstart = ev.get("DTSTART")
            if not dtstart:
                continue
            dt = dtstart.dt
            all_day = _is_all_day(dt)
            start = _to_local(dt)
            summary = html_mod.escape(str(ev.get("SUMMARY", "Ingen titel")))
            location = html_mod.escape(str(ev.get("LOCATION", "")).strip()) if show_location else ""
            events.append((start, all_day, summary, location))

    events.sort(key=lambda e: e[0])
    events = events[:max_events]

    if not events:
        return f'<div class="widget-ics-list {size_cls} ics-notice">Inga kommande händelser.</div>'

    parts: list[str] = []
    current_day: date | None = None

    for start, all_day, summary, location in events:
        day = start.date()

        if group_by_day and day != current_day:
            current_day = day
            parts.append(f'<div class="ics-day">{_fmt_day(day, today_local)}</div>')

        time_str = "Heldag" if all_day else start.strftime("%H:%M")
        loc_html = f' <span class="ics-loc">{location}</span>' if location else ""
        parts.append(
            f'<div class="ics-ev">'
            f'<span class="ics-t">{time_str}</span>'
            f'<span class="ics-s">{summary}{loc_html}</span>'
            f"</div>"
        )

    if oldest_fetched:
        fetched_local = oldest_fetched.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ)
        fetched_str = fetched_local.strftime("%H:%M")
        if has_error:
            parts.append(f'<div class="ics-warn">⚠ Kan ej uppdatera – visar data från {fetched_str}</div>')
        else:
            parts.append(f'<div class="ics-updated">Uppdaterad {fetched_str}</div>')

    return f'<div class="widget-ics-list {size_cls}">{"".join(parts)}</div>'
