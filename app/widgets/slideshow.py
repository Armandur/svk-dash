import html as html_mod
import json
from typing import Any


def _src(item: dict) -> str:
    if item.get("upload_path"):
        return "/uploads/" + html_mod.escape(str(item["upload_path"]))
    if item.get("url"):
        return html_mod.escape(str(item["url"]))
    return ""


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    images = config.get("images") or []
    if isinstance(images, str):
        images = []
    srcs = [s for item in images if (s := _src(item))]

    if not srcs:
        return '<div class="widget-slideshow ss-empty">Inga bilder valda.</div>'

    fit = config.get("fit", "cover")
    interval_ms = max(1000, int(float(config.get("interval", 5)) * 1000))
    transition = config.get("transition", "fade")
    fade = transition == "fade"

    slides_html = "".join(
        f'<div class="ss-slide{" ss-active" if i == 0 else ""}">'
        f'<img src="{src}" alt="" style="width:100%;height:100%;object-fit:{fit};display:block;">'
        f'</div>'
        for i, src in enumerate(srcs)
    )

    srcs_json = json.dumps(srcs)

    return f"""<div class="widget-slideshow{"" if not fade else " ss-fade"}">
{slides_html}
<script>(function(){{
  var el=document.currentScript.parentElement;
  var slides=el.querySelectorAll('.ss-slide');
  if(slides.length<2)return;
  var cur=0;
  setInterval(function(){{
    slides[cur].classList.remove('ss-active');
    cur=(cur+1)%slides.length;
    slides[cur].classList.add('ss-active');
  }},{interval_ms});
}})();</script>
</div>"""
