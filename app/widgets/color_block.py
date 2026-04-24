from typing import Any


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    use_gradient = bool(config.get("use_gradient", False))
    if use_gradient:
        g_start = config.get("gradient_start", "#1e3a5f")
        g_end = config.get("gradient_end", "#000000")
        angle = max(0, min(360, int(config.get("gradient_angle", 180))))
        bg_css = f"linear-gradient({angle}deg, {g_start}, {g_end})"
    else:
        bg_css = config.get("bg_color") or config.get("color", "#1e3a5f")

    radius = max(0, min(200, int(config.get("border_radius", 0))))
    return (
        f'<div class="widget-color-block"'
        f' style="width:100%;height:100%;background:{bg_css};border-radius:{radius}px;"></div>'
    )
