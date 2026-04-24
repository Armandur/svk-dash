import html as html_mod
from typing import Any


def _src(config: dict) -> str:
    base_url = ""
    if config.get("upload_path"):
        base_url = "/uploads/" + html_mod.escape(config["upload_path"])
    elif config.get("url"):
        base_url = html_mod.escape(config["url"])

    if not base_url:
        return ""

    toolbar = config.get("toolbar", False)
    if not toolbar:
        if "#" in base_url:
            base_url += "&toolbar=0&navpanes=0"
        else:
            base_url += "#toolbar=0&navpanes=0"
    return base_url


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    src = _src(config)
    if not src:
        return '<div class="widget-pdf pdf-empty">Ingen PDF vald.</div>'

    return (
        f'<div class="widget-pdf" style="width:100%;height:100%;">'
        f'<iframe src="{src}" style="border:none;width:100%;height:100%;" allow="fullscreen"></iframe>'
        f"</div>"
    )
