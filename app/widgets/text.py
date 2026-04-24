import html as html_mod
from typing import Any

from app.widgets.base import build_common_style


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    content = config.get("text", "")
    weight = "font-bold" if config.get("bold", False) else ""
    safe = html_mod.escape(content).replace("\n", "<br>")
    style = build_common_style(config)
    return (
        f'<div class="widget-text" style="{style}">'
        f'<span class="{weight}">{safe}</span>'
        f"</div>"
    )
