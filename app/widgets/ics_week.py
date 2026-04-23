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
from app.widgets.ics_common import (
    apply_private,
    get_event_kind,
    online_badge_html,
    should_filter,
    source_color,
)

_TZ = ZoneInfo("Europe/Stockholm")

_WEEKDAYS_MON = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"]
_WEEKDAYS_SUN = ["Sön", "Mån", "Tis", "Ons", "Tor", "Fre", "Lör"]
_MONTHS = [
    "",
    "jan",
    "feb",
    "mar",
    "apr",
    "maj",
    "jun",
    "jul",
    "aug",
    "sep",
    "okt",
    "nov",
    "dec",
]


def _to_local(dt) -> datetime:
    if isinstance(dt, datetime):
        return dt.astimezone(_TZ) if dt.tzinfo else dt.replace(tzinfo=_TZ)
    return datetime(dt.year, dt.month, dt.day, tzinfo=_TZ)


def _is_all_day(dt) -> bool:
    return not isinstance(dt, datetime)


def _week_start(today: date, week_offset: int, start_on_monday: bool) -> date:
    if start_on_monday:
        monday = today - timedelta(days=today.weekday())
    else:
        sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        monday = sunday
    return monday + timedelta(weeks=week_offset)


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    widget_id = context.get("widget_id")
    urls = get_ics_urls(config)
    week_offset = int(config.get("week_offset", 0))
    start_on_monday = bool(config.get("start_on_monday", True))
    show_location = bool(config.get("show_location", False))
    show_colors = bool(config.get("show_source_colors", False))
    free_color = config.get("free_color", "#f59e0b")
    hide_free = bool(config.get("hide_free_events", False))
    max_per_day = config.get("max_per_day")
    if max_per_day is not None:
        max_per_day = max(1, int(max_per_day))
    font_size = config.get("font_size", "normal")
    size_cls = {"small": "ics-sm", "large": "ics-lg"}.get(font_size, "")

    if not widget_id or not urls:
        return '<div class="widget-ics-week ics-notice">Ingen ICS-URL konfigurerad.</div>'

    with get_session() as db:
        caches = db.exec(select(IcsCache).where(IcsCache.widget_id == widget_id)).all()

    if not caches:
        return '<div class="widget-ics-week ics-notice">Kalender hämtas…</div>'

    cache_by_url = {c.source_url: c for c in caches}
    today = datetime.now(_TZ).date()
    week_first = _week_start(today, week_offset, start_on_monday)
    week_days = [week_first + timedelta(days=i) for i in range(7)]
    week_last = week_days[-1]

    # day -> [(start_dt, all_day, summary, location, color)]
    day_events: dict[date, list[tuple[datetime, bool, str, str, str]]] = {d: [] for d in week_days}
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
            raw_events = recurring_ical_events.of(cal).between(
                week_first, week_last + timedelta(days=1)
            )
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
            kind = get_event_kind(ev)
            if hide_free and kind == "free":
                continue
            all_day = _is_all_day(dt)
            start = _to_local(dt)
            day = start.date()
            if day not in day_events:
                continue
            display_summary = apply_private(raw_summary, ev, config)
            summary = html_mod.escape(display_summary)
            location = html_mod.escape(str(ev.get("LOCATION", "")).strip()) if show_location else ""
            ev_color = free_color if kind == "free" and not show_colors else color
            badge = online_badge_html(ev, config)
            day_events[day].append((start, all_day, summary, location, ev_color, kind, badge))

    for d in week_days:
        day_events[d].sort(key=lambda e: (not e[1], e[0]))  # type: ignore[index]

    weekday_names = _WEEKDAYS_MON if start_on_monday else _WEEKDAYS_SUN

    parts: list[str] = [f'<div class="widget-ics-week {size_cls}">']

    # Rubrikrad
    parts.append('<div class="icw-grid">')
    for i, d in enumerate(week_days):
        today_cls = " icw-today" if d == today else ""
        parts.append(
            f'<div class="icw-col-head{today_cls}">'
            f'<span class="icw-dow">{weekday_names[i]}</span>'
            f'<span class="icw-date">{d.day} {_MONTHS[d.month]}</span>'
            f"</div>"
        )

    # Händelsekolumner
    for i, d in enumerate(week_days):
        today_cls = " icw-today-col" if d == today else ""
        parts.append(f'<div class="icw-col{today_cls}">')
        evs = day_events[d]
        all_day_evs = [e for e in evs if e[1]]
        timed_evs = [e for e in evs if not e[1]]
        shown = 0
        total = len(evs)
        limit = max_per_day if max_per_day is not None else total

        for start, all_day, summary, location, color, kind, badge in all_day_evs:
            if shown >= limit:
                break
            parts.append(
                _render_event("", summary, location, color, badge=badge, all_day=True, kind=kind)
            )
            shown += 1

        for start, all_day, summary, location, color, kind, badge in timed_evs:
            if shown >= limit:
                break
            parts.append(
                _render_event(
                    start.strftime("%H:%M"), summary, location, color, badge=badge, kind=kind
                )
            )
            shown += 1

        if total > limit:
            parts.append(f'<div class="icw-more">+{total - limit}</div>')

        if not evs:
            parts.append('<div class="icw-empty"></div>')

        parts.append("</div>")

    parts.append("</div>")  # icw-grid

    if oldest_fetched:
        fetched_local = oldest_fetched.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ)
        fetched_str = fetched_local.strftime("%H:%M")
        if has_error:
            parts.append(
                f'<div class="ics-warn">⚠ Kan ej uppdatera – visar data från {fetched_str}</div>'
            )
        else:
            parts.append(f'<div class="ics-updated">Uppdaterad {fetched_str}</div>')

    parts.append("</div>")
    return "".join(parts)


def _render_event(
    time_str: str,
    summary: str,
    location: str,
    color: str,
    badge: str = "",
    all_day: bool = False,
    kind: str = "busy",
) -> str:
    color_style = f"border-left:2px solid {color};padding-left:3px;" if color else ""
    heldag_cls = " icw-ev-allday" if all_day else ""
    kind_cls = f" icw-ev-{kind}" if kind != "busy" else ""
    time_html = f'<span class="icw-t">{time_str}</span>' if time_str else ""
    loc_html = f'<span class="icw-loc">{location}</span>' if location else ""
    return (
        f'<div class="icw-ev{heldag_cls}{kind_cls}" style="{color_style}">'
        f"{time_html}"
        f'<span class="icw-s">{summary}{badge}</span>'
        f"{loc_html}"
        f"</div>"
    )
