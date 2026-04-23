import html as html_mod
from typing import Any


def _src(config: dict) -> str:
    if config.get("upload_path"):
        return "/uploads/" + html_mod.escape(config["upload_path"])
    if config.get("url"):
        return html_mod.escape(config["url"])
    return ""


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    src = _src(config)
    if not src:
        return '<div class="widget-image img-empty">Ingen bild vald.</div>'
    fit = config.get("fit", "cover")
    alt = html_mod.escape(config.get("alt", ""))
    return (
        f'<div class="widget-image">'
        f'<img src="{src}" alt="{alt}" style="width:100%;height:100%;object-fit:{fit};display:block;">'
        f"</div>"
    )
