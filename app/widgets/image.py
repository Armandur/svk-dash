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

    radius = max(0, min(500, int(config.get("border_radius", 0))))

    pos = config.get("object_position", "center")
    valid_pos = {
        "center",
        "top",
        "bottom",
        "left",
        "right",
        "top left",
        "top right",
        "bottom left",
        "bottom right",
    }
    if pos not in valid_pos:
        pos = "center"

    return (
        f'<div class="widget-image" style="border-radius:{radius}px;">'
        f'<img src="{src}" alt="{alt}" style="width:100%;height:100%;object-fit:{fit};object-position:{pos};display:block;">'
        f"</div>"
    )
