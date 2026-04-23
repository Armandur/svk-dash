from typing import Any, Protocol


class WidgetRenderer(Protocol):
    def render(self, config: dict[str, Any], context: dict[str, Any]) -> str: ...


def render_widget(kind: str, config: dict[str, Any], context: dict[str, Any]) -> str:
    from app.widgets import (
        clock,
        color_block,
        debug,
        ics_list,
        ics_month,
        ics_schedule,
        ics_week,
        image,
        markdown,
        raw_html,
        slideshow,
        text,
    )

    renderers: dict[str, WidgetRenderer] = {
        "markdown": markdown,
        "clock": clock,
        "raw_html": raw_html,
        "debug": debug,
        "text": text,
        "color_block": color_block,
        "image": image,
        "slideshow": slideshow,
        "ics_list": ics_list,
        "ics_month": ics_month,
        "ics_week": ics_week,
        "ics_schedule": ics_schedule,
    }
    renderer = renderers.get(kind)
    if renderer is None:
        return f'<div class="widget-placeholder">Widget-typ "{kind}" saknar renderer.</div>'
    try:
        html = renderer.render(config, context)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).exception(
            "Widget-rendering misslyckades: kind=%s context=%s", kind, context
        )
        return f'<div class="widget-placeholder" style="color:#f87171">Widget-fel ({kind}): {exc}</div>'
    custom_css = (config.get("custom_css") or "").strip()
    if custom_css:
        html = f"<style>{custom_css}</style>" + html
    return html
