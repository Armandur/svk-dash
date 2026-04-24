from typing import Any

import nh3
from markdown_it import MarkdownIt

from app.widgets.base import build_common_style

_md = MarkdownIt()


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    content_md = config.get("content_md", "")
    raw_html = _md.render(content_md)
    safe_html = nh3.clean(raw_html)
    style = build_common_style(config)
    return f'<div class="widget-markdown" style="{style}">{safe_html}</div>'
