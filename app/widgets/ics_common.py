"""Delade hjälpfunktioner för ICS-kalender-widgets."""

from __future__ import annotations

_SOURCE_COLORS = [
    "#60a5fa",  # blue-400
    "#34d399",  # emerald-400
    "#f87171",  # red-400
    "#fbbf24",  # amber-400
    "#a78bfa",  # violet-400
    "#f472b6",  # pink-400
    "#38bdf8",  # sky-400
    "#4ade80",  # green-400
]


def source_color(url_index: int) -> str:
    return _SOURCE_COLORS[url_index % len(_SOURCE_COLORS)]


def _parse_str_list(value) -> list[str]:
    """Normaliserar str (kommaseparerad) eller list till list[str]."""
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def get_event_kind(ev) -> str:
    """Returnerar 'free', 'tentative' eller 'busy' baserat på Outlook-fält."""
    busy = str(ev.get("X-MICROSOFT-CDO-BUSYSTATUS", "")).upper()
    if busy == "FREE":
        return "free"
    if busy == "TENTATIVE":
        return "tentative"
    # Fallback på standard iCal-fält
    transp = str(ev.get("TRANSP", "")).upper()
    if transp == "TRANSPARENT":
        return "free"
    status = str(ev.get("STATUS", "")).upper()
    if status == "TENTATIVE":
        return "tentative"
    return "busy"


def is_private(ev) -> bool:
    return str(ev.get("CLASS", "")).upper() == "PRIVATE"


def apply_private(summary: str, ev, config: dict) -> str:
    """Ersätter titeln med en platshållare om händelsen är privat och hide_private är aktivt."""
    if config.get("hide_private", False) and is_private(ev):
        return config.get("private_label", "Privat")
    return summary


_DEFAULT_ONLINE_PATTERNS = ["teams", "zoom", "meet", "skype", "webex", "whereby", "jitsi"]


def is_online_meeting(ev, config: dict) -> bool:
    """Returnerar True om platsen matchar något av online-mötesmönstren."""
    patterns = _parse_str_list(config.get("online_meeting_patterns", _DEFAULT_ONLINE_PATTERNS))
    if not patterns:
        return False
    location = str(ev.get("LOCATION", "")).lower()
    url = str(ev.get("URL", "")).lower()
    for p in patterns:
        if p.lower() in location or p.lower() in url:
            return True
    return False


def online_badge_html(ev, config: dict) -> str:
    """Returnerar HTML för ett online-mötes-märke om tillämpligt, annars tom sträng."""
    if config.get("show_online_badge", True) and is_online_meeting(ev, config):
        return '<span class="ics-online-badge" title="Digitalt möte">&#x1F4BB;</span>'
    return ""


def should_filter(summary: str, config: dict) -> bool:
    """Returnerar True om händelsen ska filtreras bort (döljas)."""
    prefixes = _parse_str_list(config.get("filter_prefixes", []))
    for prefix in prefixes:
        if summary.startswith(prefix):
            return True

    keywords = _parse_str_list(config.get("filter_keywords", []))
    lower = summary.lower()
    for kw in keywords:
        if kw.lower() in lower:
            return True

    return False
