from typing import Any

import nh3
from markdown_it import MarkdownIt

_md = MarkdownIt()

_FONT_SIZE_CLASS = {
    "small": "text-sm",
    "normal": "text-base",
    "large": "text-xl",
    "huge": "text-3xl",
}

_ALIGN_CLASS = {
    "left": "text-left",
    "center": "text-center",
    "right": "text-right",
}


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    content_md = config.get("content_md", "")
    font_size = _FONT_SIZE_CLASS.get(config.get("font_size", "normal"), "text-base")
    alignment = _ALIGN_CLASS.get(config.get("alignment", "left"), "text-left")

    raw_html = _md.render(content_md)
    safe_html = nh3.clean(raw_html)

    return (
        f'<div class="widget-markdown prose max-w-none {font_size} {alignment}">{safe_html}</div>'
    )
