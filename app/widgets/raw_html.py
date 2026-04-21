from typing import Any


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    html = config.get("html", "")
    css = config.get("css", "")
    style_block = f"<style>{css}</style>" if css else ""
    return f'<div class="widget-raw-html">{style_block}{html}</div>'
