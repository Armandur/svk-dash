import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from app.config import DEFAULT_TIMEZONE, get_setting

templates = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"]),
)

def _static_version(path: str) -> int:
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return 0

def get_now_local():
    tz_name = get_setting("timezone", DEFAULT_TIMEZONE)
    try:
        return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
    except Exception:
        # Fallback om tidszonen är ogiltig
        return datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).replace(tzinfo=None)

templates.globals["now_local"] = get_now_local
templates.globals["static_version"] = _static_version
templates.filters["tojson"] = lambda v: Markup(json.dumps(v, ensure_ascii=False))


def _human_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.1f} GB"
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    if size_bytes >= 1_024:
        return f"{size_bytes / 1_024:.1f} KB"
    return f"{size_bytes} B"


templates.filters["human_size"] = _human_size

def schedule_summary(value):
    if not value:
        return "Visa alltid"
    
    try:
        if isinstance(value, str):
            import json
            data = json.loads(value)
        else:
            data = value
            
        type_ = data.get("type", "always")
        if type_ == "always":
            return "Visa alltid"
            
        time_str = ""
        if data.get("time_start") or data.get("time_end"):
            start = data.get("time_start") or "00:00"
            end = data.get("time_end") or "23:59"
            time_str = f" ({start}–{end})"

        if type_ == "weekly":
            days = data.get("weekdays", [])
            if not days:
                return "Aldrig (inga dagar valda)"
            day_map = {
                "mon": "mån", "tue": "tis", "wed": "ons", "thu": "tor", 
                "fri": "fre", "sat": "lör", "sun": "sön"
            }
            day_names = [day_map.get(d, d) for d in days]
            return f"{', '.join(day_names)}{time_str}"
            
        if type_ == "monthly":
            day = data.get("day")
            return f"Dag {day} i månaden{time_str}"
            
        if type_ == "yearly":
            month = data.get("month")
            day = data.get("day")
            months = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
            month_name = months[month-1] if 1 <= month <= 12 else str(month)
            return f"{day} {month_name} varje år{time_str}"
            
        if type_ == "dates":
            dates = data.get("dates", [])
            if not dates:
                return "Aldrig (inga datum valda)"
            return f"{', '.join(dates[:2])}{'...' if len(dates) > 2 else ''}{time_str}"
            
        return "Anpassat schema"
    except Exception:
        return "Ogiltigt schema"

templates.filters["schedule_summary"] = schedule_summary


def _unseen_notification_count() -> int:
    from sqlmodel import select, func
    from app.database import get_session
    from app.models import Notification
    try:
        with get_session() as db:
            return db.exec(
                select(func.count()).where(Notification.seen_at == None)  # noqa: E711
            ).one()
    except Exception:
        return 0

templates.globals["unseen_notification_count"] = _unseen_notification_count
