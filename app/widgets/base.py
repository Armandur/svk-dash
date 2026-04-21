from typing import Any, Protocol


class WidgetRenderer(Protocol):
    def render(self, config: dict[str, Any], context: dict[str, Any]) -> str: ...


def render_widget(kind: str, config: dict[str, Any], context: dict[str, Any]) -> str:
    from app.widgets import clock, debug, markdown, raw_html

    renderers: dict[str, WidgetRenderer] = {
        "markdown": markdown,
        "clock": clock,
        "raw_html": raw_html,
        "debug": debug,
    }
    renderer = renderers.get(kind)
    if renderer is None:
        return f'<div class="widget-placeholder">Widget-typ "{kind}" saknar renderer.</div>'
    return renderer.render(config, context)
