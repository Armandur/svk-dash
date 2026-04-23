"""Delade hjälpfunktioner för ICS-kalender-widgets."""

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
