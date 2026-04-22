from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_FORMAT_LABELS = {
    "time_only": "time",
    "date_only": "date",
    "time_date": "time_date",
    "day_time": "day_time",
}

_SIZE_CLASS = {
    "sm": "text-4xl",
    "md": "text-6xl",
    "lg": "text-8xl",
    "xl": "text-9xl",
}


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    fmt = config.get("format", "time_date")
    size = _SIZE_CLASS.get(config.get("size", "xl"), "text-9xl")
    timezone = config.get("timezone", "Europe/Stockholm")
    locale = config.get("locale", "sv-SE")

    try:
        now = datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        now = datetime.now()
    time_str = now.strftime("%H:%M")
    date_str = now.strftime("%-d %B %Y")

    return (
        f'<div class="widget-clock flex flex-col items-center justify-center h-full {size} font-mono tabular-nums"'
        f'     data-clock-format="{fmt}"'
        f'     data-clock-timezone="{timezone}"'
        f'     data-clock-locale="{locale}">'
        f'  <span class="clock-time">{time_str}</span>'
        f'  <span class="clock-date text-3xl mt-2">{date_str}</span>'
        f"</div>"
    )
