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
from app.widgets.ics_common import should_filter, source_color

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
    max_per_day = config.get("max_per_day")
    if max_per_day is not None:
        max_per_day = max(1, int(max_per_day))
    show_location = bool(config.get("show_location", True))
    show_colors = bool(config.get("show_source_colors", False))
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

    # (start, all_day, summary, location, color)
    events: list[tuple[datetime, bool, str, str, str]] = []
    has_error = False
    oldest_fetched: datetime | None = None

    for url_idx, url in enumerate(urls):
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

        color = source_color(url_idx) if show_colors else ""

        for ev in raw_events:
            dtstart = ev.get("DTSTART")
            if not dtstart:
                continue
            dt = dtstart.dt
            raw_summary = str(ev.get("SUMMARY", "Ingen titel"))
            if should_filter(raw_summary, config):
                continue
            all_day = _is_all_day(dt)
            start = _to_local(dt)
            summary = html_mod.escape(raw_summary)
            location = html_mod.escape(str(ev.get("LOCATION", "")).strip()) if show_location else ""
            events.append((start, all_day, summary, location, color))

    events.sort(key=lambda e: (e[0].date(), not e[1], e[0]))
    events = events[:max_events]

    if not events:
        return f'<div class="widget-ics-list {size_cls} ics-notice">Inga kommande händelser.</div>'

    parts: list[str] = []

    if group_by_day:
        # Gruppera per dag med heldagshändelser överst
        from itertools import groupby
        for day, day_events_iter in groupby(events, key=lambda e: e[0].date()):
            day_events = list(day_events_iter)
            parts.append(f'<div class="ics-day">{_fmt_day(day, today_local)}</div>')

            all_day_evs = [e for e in day_events if e[1]]
            timed_evs = [e for e in day_events if not e[1]]

            shown = 0
            total = len(day_events)
            limit = max_per_day if max_per_day is not None else total

            for start, all_day, summary, location, color in all_day_evs:
                if shown >= limit:
                    break
                parts.append(_render_event("Heldag", summary, location, color))
                shown += 1

            for start, all_day, summary, location, color in timed_evs:
                if shown >= limit:
                    break
                parts.append(_render_event(start.strftime("%H:%M"), summary, location, color))
                shown += 1

            if total > limit:
                parts.append(f'<div class="ics-more-day">+{total - limit} till</div>')
    else:
        for start, all_day, summary, location, color in events:
            time_str = "Heldag" if all_day else start.strftime("%H:%M")
            parts.append(_render_event(time_str, summary, location, color))

    if oldest_fetched:
        fetched_local = oldest_fetched.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ)
        fetched_str = fetched_local.strftime("%H:%M")
        if has_error:
            parts.append(f'<div class="ics-warn">⚠ Kan ej uppdatera – visar data från {fetched_str}</div>')
        else:
            parts.append(f'<div class="ics-updated">Uppdaterad {fetched_str}</div>')

    return f'<div class="widget-ics-list {size_cls}">{"".join(parts)}</div>'


def _render_event(time_str: str, summary: str, location: str, color: str) -> str:
    color_bar = f'<span class="ics-color-bar" style="background:{color}"></span>' if color else ""
    loc_html = f' <span class="ics-loc">{location}</span>' if location else ""
    return (
        f'<div class="ics-ev">'
        f'{color_bar}'
        f'<span class="ics-t">{time_str}</span>'
        f'<span class="ics-s">{summary}{loc_html}</span>'
        f"</div>"
    )
