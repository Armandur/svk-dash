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
from app.widgets.ics_common import apply_private, get_event_kind, online_badge_html, should_filter, source_color

_TZ = ZoneInfo("Europe/Stockholm")

_WEEKDAYS_SHORT = ["Mån", "Tis", "Ons", "Tor", "Fre", "Lör", "Sön"]
_MONTHS_SHORT = [
    "", "jan", "feb", "mar", "apr", "maj", "jun",
    "jul", "aug", "sep", "okt", "nov", "dec",
]


def _to_local(dt) -> datetime:
    if isinstance(dt, datetime):
        return dt.astimezone(_TZ) if dt.tzinfo else dt.replace(tzinfo=_TZ)
    return datetime(dt.year, dt.month, dt.day, tzinfo=_TZ)


def _is_all_day(dt) -> bool:
    return not isinstance(dt, datetime)


def _pct(minutes: int, total: int) -> str:
    return f"{100 * minutes / total:.4f}%"


def _assign_lanes(events: list[tuple]) -> list[tuple]:
    """Tilldelar lane-index och total lanes till parallella händelser.
    Input: [(offset, duration, total, time_str, summary, location, color, kind), ...]
    Output: [(offset, duration, total, time_str, summary, location, color, kind, lane, n_lanes), ...]
    """
    if not events:
        return []

    # Bygg överlappningsgrupper med sweep-line
    sorted_evs = sorted(events, key=lambda e: e[0])
    groups: list[list[int]] = []  # Grupper av index i sorted_evs
    active: list[int] = []  # Index i sorted_evs för aktiva händelser

    for i, ev in enumerate(sorted_evs):
        start, dur = ev[0], ev[1]
        end = start + dur
        # Ta bort händelser som slutat
        active = [j for j in active if sorted_evs[j][0] + sorted_evs[j][1] > start]
        if active:
            # Lägg till i befintlig grupp om den täcker denna händelse
            merged = False
            for g in groups:
                if i - 1 in g or any(j in active for j in g):
                    g.append(i)
                    merged = True
                    break
            if not merged:
                groups.append([i])
        else:
            groups.append([i])
        active.append(i)

    # Tilldela lanes inom varje grupp
    lane_map: dict[int, tuple[int, int]] = {}  # index → (lane, n_lanes)
    for group in groups:
        n = len(group)
        for lane, idx in enumerate(group):
            lane_map[idx] = (lane, n)

    result = []
    for i, ev in enumerate(sorted_evs):
        lane, n_lanes = lane_map.get(i, (0, 1))
        result.append((*ev, lane, n_lanes))
    return result


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    widget_id = context.get("widget_id")
    urls = get_ics_urls(config)
    show_full_week = bool(config.get("show_full_week", False))
    week_offset = int(config.get("week_offset", 0))
    day_offset = int(config.get("day_offset", 0))
    day_count = max(1, min(7, int(config.get("day_count", 1))))
    start_hour = max(0, min(23, int(config.get("start_hour", 8))))
    end_hour = max(start_hour + 1, min(24, int(config.get("end_hour", 17))))
    show_location = bool(config.get("show_location", False))
    show_colors = bool(config.get("show_source_colors", False))
    free_color = config.get("free_color", "#f59e0b")
    hide_free = bool(config.get("hide_free_events", False))
    font_size = config.get("font_size", "normal")
    size_cls = {"small": "ics-sm", "large": "ics-lg"}.get(font_size, "")

    total_minutes = (end_hour - start_hour) * 60
    start_minute = start_hour * 60

    if not widget_id or not urls:
        return '<div class="widget-ics-schedule ics-notice">Ingen ICS-URL konfigurerad.</div>'

    with get_session() as db:
        caches = db.exec(select(IcsCache).where(IcsCache.widget_id == widget_id)).all()

    if not caches:
        return '<div class="widget-ics-schedule ics-notice">Kalender hämtas…</div>'

    cache_by_url = {c.source_url: c for c in caches}
    today = datetime.now(_TZ).date()
    if show_full_week:
        week_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
        days = [week_monday + timedelta(days=i) for i in range(7)]
    else:
        days = [today + timedelta(days=day_offset + i) for i in range(day_count)]

    DayData = dict
    day_data: list[DayData] = [{
        "date": d, "all_day": [], "before": [], "main": [], "after": []
    } for d in days]

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
            raw_events = recurring_ical_events.of(cal).between(days[0], days[-1] + timedelta(days=1))
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
            display_summary = apply_private(raw_summary, ev, config)
            summary = html_mod.escape(display_summary)
            location = html_mod.escape(str(ev.get("LOCATION", "")).strip()) if show_location else ""

            ev_color = free_color if kind == "free" and not show_colors else color
            badge = online_badge_html(ev, config)

            if _is_all_day(dt):
                ev_date = dt if isinstance(dt, date) else dt.date()
                for dd in day_data:
                    if dd["date"] == ev_date:
                        dd["all_day"].append((summary, location, ev_color, kind, badge))
                continue

            start_local = _to_local(dt)
            ev_date = start_local.date()

            dtend = ev.get("DTEND")
            end_local = _to_local(dtend.dt) if dtend else start_local + timedelta(hours=1)
            ev_start_min = start_local.hour * 60 + start_local.minute
            ev_end_min = end_local.hour * 60 + end_local.minute
            if ev_end_min <= ev_start_min:
                ev_end_min = ev_start_min + 30

            for dd in day_data:
                if dd["date"] != ev_date:
                    continue
                if ev_end_min <= start_minute:
                    dd["before"].append((start_local.strftime("%H:%M"), summary, location, ev_color, kind, badge))
                elif ev_start_min >= end_hour * 60:
                    dd["after"].append((start_local.strftime("%H:%M"), summary, location, ev_color, kind, badge))
                else:
                    clipped_start = max(ev_start_min, start_minute)
                    clipped_end = min(ev_end_min, end_hour * 60)
                    offset = clipped_start - start_minute
                    duration = max(clipped_end - clipped_start, 10)
                    dd["main"].append((offset, duration, total_minutes,
                                       start_local.strftime("%H:%M"), summary, location, ev_color, kind, badge))

    # Tilldela lanes för parallella händelser
    for dd in day_data:
        dd["main"] = _assign_lanes(dd["main"])

    parts: list[str] = [f'<div class="widget-ics-schedule {size_cls}">']

    # Tidsetiketter (vänster kolumn)
    hour_labels: list[str] = []
    for h in range(start_hour, end_hour + 1):
        pct = _pct(h * 60 - start_minute, total_minutes)
        hour_labels.append(
            f'<div class="isch-hour-label" style="top:{pct}">{h:02d}</div>'
        )

    col_style = f"grid-template-columns: 1.8em repeat({day_count}, 1fr);"
    parts.append(f'<div class="isch-outer" style="{col_style}">')

    # Rubrikrad
    parts.append('<div class="isch-corner"></div>')
    for dd in day_data:
        d = dd["date"]
        today_cls = " isch-today" if d == today else ""
        parts.append(
            f'<div class="isch-col-head{today_cls}">'
            f'<span class="isch-dow">{_WEEKDAYS_SHORT[d.weekday()]}</span>'
            f' <span class="isch-date">{d.day} {_MONTHS_SHORT[d.month]}</span>'
            f'</div>'
        )

    # Heldagshändelser
    parts.append('<div class="isch-corner-allday"></div>')
    for dd in day_data:
        parts.append('<div class="isch-allday-col">')
        for summary, location, color, kind, badge in dd["all_day"]:
            color_style = f'border-left:2px solid {color};padding-left:2px;' if color else ""
            kind_cls = f" isch-ev-{kind}" if kind != "busy" else ""
            parts.append(f'<div class="isch-allday-ev{kind_cls}" style="{color_style}">{summary}{badge}</div>')
        if not dd["all_day"]:
            parts.append('<div class="isch-allday-empty"></div>')
        parts.append('</div>')

    # "Tidigare"-sektion
    has_before = any(dd["before"] for dd in day_data)
    if has_before:
        parts.append('<div class="isch-section-label">↑</div>')
        for dd in day_data:
            parts.append('<div class="isch-overflow-col">')
            for time_str, summary, location, color, kind, badge in dd["before"]:
                color_style = f'border-left:2px solid {color};padding-left:2px;' if color else ""
                kind_cls = f" isch-ev-{kind}" if kind != "busy" else ""
                parts.append(
                    f'<div class="isch-overflow-ev{kind_cls}" style="{color_style}">'
                    f'<span class="isch-t">{time_str}</span>{summary}{badge}</div>'
                )
            parts.append('</div>')

    # Tidsblock-sektion
    now_time_attrs = f' data-now-start="{start_hour}" data-now-end="{end_hour}"' if today in days else ""
    parts.append(f'<div class="isch-time-col" style="position:relative;"{now_time_attrs}>')
    for label in hour_labels:
        parts.append(label)
    if today in days:
        parts.append('<div class="isch-now-dot"></div>')
    parts.append('</div>')

    for dd in day_data:
        is_today = dd["date"] == today
        today_cls = " isch-today-col" if is_today else ""
        now_attrs = (f' data-now-start="{start_hour}" data-now-end="{end_hour}"'
                     if is_today else "")
        parts.append(f'<div class="isch-main-col{today_cls}"{now_attrs}>')
        for h in range(start_hour, end_hour):
            pct = _pct(h * 60 - start_minute, total_minutes)
            parts.append(f'<div class="isch-grid-line" style="top:{pct}"></div>')

        if dd["date"] == today:
            parts.append('<div class="isch-now-line"></div>')

        for ev in dd["main"]:
            offset, duration, total, time_str, summary, location, color, kind, badge, lane, n_lanes = ev
            top = _pct(offset, total)
            height = _pct(duration, total)
            # Parallell-layout: dela bredden
            lane_w = 100 / n_lanes
            left = f"{lane * lane_w:.4f}%"
            width = f"{lane_w - 1:.4f}%"
            kind_cls = f" isch-ev-{kind}" if kind != "busy" else ""
            border = f'border-left:3px solid {color};' if color else ""

            # Anpassa innehåll efter block-höjd (duration i minuter)
            if duration < 15:
                # Mycket kort: bara titeln, ingen tid
                inner = f'<span class="isch-ev-title isch-ev-compact">{summary}</span>'
            elif duration < 25:
                # Kort: tid och titel på samma rad
                inner = (
                    f'<span class="isch-ev-inline">'
                    f'<span class="isch-ev-time">{time_str}</span>'
                    f'<span class="isch-ev-title">{summary}</span>'
                    f'</span>'
                )
            else:
                loc_html = f'<span class="isch-loc">{location}</span>' if location else ""
                inner = (
                    f'<span class="isch-ev-time">{time_str}</span>'
                    f'<span class="isch-ev-title">{summary}{badge}</span>'
                    f'{loc_html}'
                )

            parts.append(
                f'<div class="isch-ev-block{kind_cls}" style="top:{top};height:{height};left:{left};width:{width};{border}">'
                f'{inner}'
                f'</div>'
            )
        parts.append('</div>')

    # "Senare"-sektion
    has_after = any(dd["after"] for dd in day_data)
    if has_after:
        parts.append('<div class="isch-section-label">↓</div>')
        for dd in day_data:
            parts.append('<div class="isch-overflow-col">')
            for time_str, summary, location, color, kind, badge in dd["after"]:
                color_style = f'border-left:2px solid {color};padding-left:2px;' if color else ""
                kind_cls = f" isch-ev-{kind}" if kind != "busy" else ""
                parts.append(
                    f'<div class="isch-overflow-ev{kind_cls}" style="{color_style}">'
                    f'<span class="isch-t">{time_str}</span>{summary}{badge}</div>'
                )
            parts.append('</div>')

    parts.append('</div>')  # isch-outer

    if oldest_fetched:
        fetched_local = oldest_fetched.replace(tzinfo=ZoneInfo("UTC")).astimezone(_TZ)
        fetched_str = fetched_local.strftime("%H:%M")
        if has_error:
            parts.append(f'<div class="ics-warn">⚠ Kan ej uppdatera – visar data från {fetched_str}</div>')
        else:
            parts.append(f'<div class="ics-updated">Uppdaterad {fetched_str}</div>')

    parts.append('</div>')
    return "".join(parts)
