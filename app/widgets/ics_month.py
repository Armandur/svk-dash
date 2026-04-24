import html as html_mod
from calendar import monthrange
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
    "Januari",
    "Februari",
    "Mars",
    "April",
    "Maj",
    "Juni",
    "Juli",
    "Augusti",
    "September",
    "Oktober",
    "November",
    "December",
]


def _to_date(dt) -> date:
    if isinstance(dt, datetime):
        return dt.astimezone(_TZ).date()
    return dt


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    widget_id = context.get("widget_id")
    urls = get_ics_urls(config)
    start_on_monday = bool(config.get("start_on_monday", True))
    highlight_today = bool(config.get("highlight_today", True))
    show_colors = bool(config.get("show_source_colors", False))
    free_color = config.get("free_color", "#f59e0b")
    hide_free = bool(config.get("hide_free_events", False))
    max_per_day = max(1, int(config.get("max_per_day", 3)))

    if not widget_id or not urls:
        return '<div class="widget-ics-month ics-notice">Ingen ICS-URL konfigurerad.</div>'

    with get_session() as db:
        caches = db.exec(select(IcsCache).where(IcsCache.widget_id == widget_id)).all()

    if not caches:
        return '<div class="widget-ics-month ics-notice">Kalender hämtas…</div>'

    cache_by_url = {c.source_url: c for c in caches}
    today = datetime.now(_TZ).date()
    year, month = today.year, today.month
    first_day = date(year, month, 1)
    _, days_in_month = monthrange(year, month)
    last_day = date(year, month, days_in_month)

    # day -> [(time_str, summary, color, kind, badge, span_pos)]
    # span_pos: None=single day, "start"|"mid"|"end"=multi-day all-day
    day_events: dict[date, list[tuple]] = {}
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
                first_day, last_day + timedelta(days=1)
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
            raw_summary = str(ev.get("SUMMARY", ""))
            if should_filter(raw_summary, config):
                continue
            kind = get_event_kind(ev)
            if hide_free and kind == "free":
                continue
            display_summary = apply_private(raw_summary, ev, config)
            summary = html_mod.escape(display_summary)
            ev_color = free_color if kind == "free" and not show_colors else color
            badge = online_badge_html(ev, config)
            all_day = not isinstance(dt, datetime)

            if all_day:
                start_date = dt if isinstance(dt, date) else dt.date()
                dtend_obj = ev.get("DTEND")
                if dtend_obj:
                    raw_end = dtend_obj.dt
                    end_date = (
                        raw_end if isinstance(raw_end, date) else raw_end.date()
                    ) - timedelta(days=1)
                else:
                    end_date = start_date

                if end_date > start_date:
                    # Flerdagarshändelse: lägg till på varje dag i spannet
                    curr = max(start_date, first_day)
                    span_end = min(end_date, last_day)
                    while curr <= span_end:
                        pos = (
                            "start"
                            if curr == start_date
                            else ("end" if curr == end_date else "mid")
                        )
                        day_events.setdefault(curr, []).append(
                            ("", summary, ev_color, kind, badge, pos)
                        )
                        curr += timedelta(days=1)
                else:
                    d = start_date
                    if first_day <= d <= last_day:
                        day_events.setdefault(d, []).append(
                            ("", summary, ev_color, kind, badge, None)
                        )
            else:
                d = _to_date(dt)
                if not (first_day <= d <= last_day):
                    continue
                time_str = dt.astimezone(_TZ).strftime("%H:%M")
                day_events.setdefault(d, []).append(
                    (time_str, summary, ev_color, kind, badge, None)
                )

    # Kalender-grid
    if start_on_monday:
        start_offset = first_day.weekday()
        headers = _WEEKDAYS_MON
    else:
        start_offset = (first_day.weekday() + 1) % 7
        headers = _WEEKDAYS_SUN

    weeks: list[list[date | None]] = []
    current_week: list[date | None] = [None] * start_offset
    for day_num in range(1, days_in_month + 1):
        current_week.append(date(year, month, day_num))
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
    if current_week:
        current_week += [None] * (7 - len(current_week))
        weeks.append(current_week)

    from app.widgets.base import build_common_style
    style = build_common_style(config)
    style_attr = f' style="{style}"' if style else ""
    parts: list[str] = [f'<div class="widget-ics-month"{style_attr}>']
    parts.append(f'<div class="icm-title">{_MONTHS[month]} {year}</div>')
    parts.append('<div class="icm-grid">')

    for h in headers:
        parts.append(f'<div class="icm-dow">{h}</div>')

    for week in weeks:
        for d in week:
            if d is None:
                parts.append('<div class="icm-cell icm-empty"></div>')
                continue
            cls = "icm-cell" + (" icm-today" if d == today and highlight_today else "")
            parts.append(f'<div class="{cls}">')
            parts.append(f'<div class="icm-num">{d.day}</div>')
            evs = day_events.get(d, [])
            for time_str, summary, color, kind, badge, span_pos in evs[:max_per_day]:
                kind_cls = f" icm-ev-{kind}" if kind != "busy" else ""
                if span_pos is not None:
                    # Flerdagarshändelse: visas som fylld balk
                    bg = f"background:{color};" if color else "background:rgba(255,255,255,0.18);"
                    span_cls = f" icm-ev-span icm-ev-span-{span_pos}"
                    parts.append(
                        f'<div class="icm-ev{kind_cls}{span_cls}" style="{bg}">'
                        f"{summary}{badge}"
                        f"</div>"
                    )
                else:
                    color_style = (
                        f"border-left:2px solid {color};padding-left:2px;" if color else ""
                    )
                    time_html = f'<span class="icm-t">{time_str}</span>' if time_str else ""
                    parts.append(
                        f'<div class="icm-ev{kind_cls}" style="{color_style}">'
                        f"{time_html}{summary}{badge}"
                        f"</div>"
                    )
            if len(evs) > max_per_day:
                parts.append(f'<div class="icm-more">+{len(evs) - max_per_day}</div>')
            parts.append("</div>")

    parts.append("</div>")  # icm-grid

    if oldest_fetched:
        fetched_local = oldest_fetched.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ)
        fetched_str = fetched_local.strftime("%H:%M")
        if has_error:
            parts.append(
                f'<div class="ics-warn">⚠ Kan ej uppdatera – visar data från {fetched_str}</div>'
            )
        else:
            parts.append(f'<div class="ics-updated">Uppdaterad {fetched_str}</div>')

    parts.append("</div>")  # widget-ics-month
    return "".join(parts)
