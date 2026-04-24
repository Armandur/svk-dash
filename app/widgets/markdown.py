from typing import Any

import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt()

_FONT_SIZE_STYLE = {
    "small": "0.875rem",
    "normal": "1rem",
    "large": "1.25rem",
    "huge": "1.875rem",
}


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    content_md = config.get("content_md", "")
    font_size = _FONT_SIZE_STYLE.get(config.get("font_size", "normal"), "1rem")
    alignment = config.get("alignment", "left")

    raw_html = _md.render(content_md)
    safe_html = nh3.clean(raw_html)

    return (
        f'<div class="widget-markdown" style="font-size:{font_size}; text-align:{alignment};">'
        f"{safe_html}</div>"
    )
