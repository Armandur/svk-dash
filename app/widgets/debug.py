from typing import Any


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    screen_name = context.get("screen_name", "–")
    screen_slug = context.get("screen_slug", "–")
    view_position = context.get("view_position", "–")
    view_count = context.get("view_count", "–")
    version = context.get("app_version") or context.get("version", "dev")

    return (
        '<div class="widget-debug fixed bottom-2 right-2 bg-black/70 text-white text-xs font-mono'
        ' rounded px-2 py-1 leading-5 z-50">'
        f"<div>{screen_name} / {screen_slug}</div>"
        f"<div>Vy {view_position}/{view_count}</div>"
        f'<div id="debug-sse-age">SSE: –</div>'
        f'<div id="debug-reconnects">Reconnects: 0</div>'
        f"<div>v{version}</div>"
        "</div>"
    )
