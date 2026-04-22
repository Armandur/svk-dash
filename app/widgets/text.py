import html
from typing import Any

_SIZE_CLASS = {
    "sm": "text-sm",
    "normal": "text-base",
    "large": "text-xl",
    "huge": "text-3xl",
}


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    text = config.get("text", "")
    size = _SIZE_CLASS.get(config.get("size", "large"), "text-xl")
    align = config.get("align", "center")
    weight = "font-bold" if config.get("bold", False) else "font-normal"
    color = config.get("color", "#ffffff")
    safe_text = html.escape(text).replace("\n", "<br>")
    return (
        f'<div class="widget-text h-full flex flex-col justify-center {size} {weight}"'
        f'     style="color:{color}; padding:0.75rem; text-align:{align};">'
        f"  {safe_text}"
        f"</div>"
    )
