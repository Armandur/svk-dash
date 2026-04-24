from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.widgets.base import build_common_style


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    fmt = config.get("format", "time_date")
    timezone = config.get("timezone", "Europe/Stockholm")
    locale = config.get("locale", "sv-SE")
    show_seconds = "1" if config.get("show_seconds", True) else "0"
    hour12 = "1" if config.get("hour12", False) else "0"
    date_format = config.get("date_format", "")

    try:
        now = datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        now = datetime.now()

    if date_format:
        date_text = now.strftime(date_format)
    else:
        date_str = now.strftime("%-d %B %Y")
        day_str = now.strftime("%A %-d %B")
        date_text = day_str if fmt == "day_time" else date_str

    show_time = fmt in ("time_only", "time_date", "day_time")
    show_date = fmt in ("date_only", "time_date", "day_time")

    spans = ""
    if show_time:
        spans += '  <span class="clock-time"></span>\n'
    if show_date:
        spans += f'  <span class="clock-date">{date_text}</span>\n'

    style = build_common_style(config)
    return (
        f'<div class="widget-clock" style="{style}"'
        f'     data-clock-format="{fmt}"'
        f'     data-clock-timezone="{timezone}"'
        f'     data-clock-locale="{locale}"'
        f'     data-clock-show-seconds="{show_seconds}"'
        f'     data-clock-hour12="{hour12}"'
        f'     data-clock-date-format="{date_format}">\n'
        f"{spans}"
        f"</div>"
    )
