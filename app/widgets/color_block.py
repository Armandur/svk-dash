from typing import Any


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    color = config.get("color", "#1e3a5f")
    radius = max(0, min(200, int(config.get("border_radius", 0))))
    return (
        f'<div class="widget-color-block"'
        f' style="width:100%;height:100%;background:{color};border-radius:{radius}px;"></div>'
    )
