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
        return '<div class="widget-video vid-empty">Ingen video vald.</div>'

    fit = config.get("fit", "cover")
    loop = config.get("loop", True)
    muted = config.get("muted", True)
    controls = config.get("controls", False)
    radius = max(0, min(500, int(config.get("border_radius", 0))))

    loop_attr = " loop" if loop else ""
    muted_attr = " muted" if muted else ""
    controls_attr = " controls" if controls else ""

    # Kiosk-läget kräver autoplay, playsinline, preload="auto"
    return (
        f'<div class="widget-video" style="border-radius:{radius}px; overflow:hidden;">'
        f'<video autoplay{muted_attr}{loop_attr}{controls_attr} playsinline preload="auto" '
        f'style="width:100%;height:100%;object-fit:{fit};display:block;">'
        f'<source src="{src}">'
        f"</video>"
        f"</div>"
    )
