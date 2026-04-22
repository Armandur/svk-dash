import html as html_mod
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

from app.database import get_session
from app.models import IcsCache

_TZ = ZoneInfo("Europe/Stockholm")

_WEEKDAYS_MON = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"]
_WEEKDAYS_SUN = ["Sön", "Mån", "Tis", "Ons", "Tor", "Fre", "Lör"]

_MONTHS = [
    "", "Januari", "Februari", "Mars", "April", "Maj", "Juni",
    "Juli", "Augusti", "September", "Oktober", "November", "December",
]


def _to_date(dt) -> date:
    if isinstance(dt, datetime):
        return dt.astimezone(_TZ).date()
    return dt


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    widget_id = context.get("widget_id")
    ics_url = config.get("ics_url", "")
    start_on_monday = bool(config.get("start_on_monday", True))
    highlight_today = bool(config.get("highlight_today", True))

    if not widget_id or not ics_url:
        return '<div class="widget-ics-month ics-notice">Ingen ICS-URL konfigurerad.</div>'

    with get_session() as db:
        cache = db.get(IcsCache, widget_id)

    if cache is None:
        return '<div class="widget-ics-month ics-notice">Kalender hämtas…</div>'

    if cache.last_error and not cache.raw_ics:
        err = html_mod.escape(cache.last_error[:200])
        return f'<div class="widget-ics-month ics-error">Kunde inte hämta kalender.<br><small>{err}</small></div>'

    try:
        cal = icalendar.Calendar.from_ical(cache.raw_ics)
    except Exception:
        return '<div class="widget-ics-month ics-error">Ogiltig ICS-data.</div>'

    today = datetime.now(_TZ).date()
    year, month = today.year, today.month
    first_day = date(year, month, 1)
    _, days_in_month = monthrange(year, month)
    last_day = date(year, month, days_in_month)

    try:
        raw_events = recurring_ical_events.of(cal).between(first_day, last_day + timedelta(days=1))
    except Exception:
        return '<div class="widget-ics-month ics-error">Kunde inte läsa händelser.</div>'

    # day → [(time_str, summary), ...]
    day_events: dict[date, list[tuple[str, str]]] = {}
    for ev in raw_events:
        dtstart = ev.get("DTSTART")
        if not dtstart:
            continue
        dt = dtstart.dt
        d = _to_date(dt)
        if not (first_day <= d <= last_day):
            continue
        if isinstance(dt, datetime):
            time_str = dt.astimezone(_TZ).strftime("%H:%M")
        else:
            time_str = ""
        summary = html_mod.escape(str(ev.get("SUMMARY", "")))
        day_events.setdefault(d, []).append((time_str, summary))

    # Calendar grid
    if start_on_monday:
        start_offset = first_day.weekday()  # Mon=0
        headers = _WEEKDAYS_MON
    else:
        start_offset = (first_day.weekday() + 1) % 7  # Sun=0
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

    parts: list[str] = ['<div class="widget-ics-month">']
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
            for time_str, summary in evs[:3]:
                label = f"{time_str} {summary}".strip() if time_str else summary
                parts.append(f'<div class="icm-ev">{label}</div>')
            if len(evs) > 3:
                parts.append(f'<div class="icm-more">+{len(evs) - 3}</div>')
            parts.append('</div>')

    parts.append('</div>')  # icm-grid

    fetched_local = cache.fetched_at.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ)
    fetched_str = fetched_local.strftime("%H:%M")
    if cache.last_error:
        parts.append(f'<div class="ics-warn">⚠ Kan ej uppdatera – visar data från {fetched_str}</div>')
    else:
        parts.append(f'<div class="ics-updated">Uppdaterad {fetched_str}</div>')

    parts.append('</div>')  # widget-ics-month
    return "".join(parts)
