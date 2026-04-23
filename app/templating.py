import json
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

templates = Environment(
    loader=FileSystemLoader("app/templates"),
    autoescape=select_autoescape(["html"]),
)

templates.globals["now_local"] = datetime.now
templates.filters["tojson"] = lambda v: Markup(json.dumps(v, ensure_ascii=False))

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
