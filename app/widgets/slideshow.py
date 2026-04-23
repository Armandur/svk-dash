import html as html_mod
import json
from typing import Any

_VALID_TRANSITIONS = {"none", "fade", "slide", "wipe", "zoom"}
_VALID_DIRECTIONS = {"left", "right", "up", "down"}


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
    if transition not in _VALID_TRANSITIONS:
        transition = "fade"

    direction = config.get("direction", "left")
    if direction not in _VALID_DIRECTIONS:
        direction = "left"

    tc = f" ss-{transition}" if transition != "none" else ""
    dir_attr = f' data-ss-dir="{direction}"' if transition in {"slide", "wipe"} else ""

    slides_html = "".join(
        f'<div class="ss-slide{" ss-active" if i == 0 else ""}">'
        f'<img src="{src}" alt="" style="width:100%;height:100%;object-fit:{fit};display:block;">'
        f"</div>"
        for i, src in enumerate(srcs)
    )

    tr_json = json.dumps(transition)

    return f"""<div class="widget-slideshow{tc}"{dir_attr}>
{slides_html}
<script>(function(){{
  var el=document.currentScript.parentElement;
  var slides=el.querySelectorAll('.ss-slide');
  if(slides.length<2)return;
  var cur=0;
  var tr={tr_json};
  var DUR=700;
  function goNext(){{
    var lv=slides[cur];
    cur=(cur+1)%slides.length;
    var en=slides[cur];
    if(tr==='none'||tr==='fade'){{
      lv.classList.remove('ss-active');
      en.classList.add('ss-active');
    }}else{{
      lv.style.display='block';
      lv.classList.add('ss-leaving');
      en.classList.add('ss-entering','ss-active');
      var _lv=lv;
      setTimeout(function(){{
        _lv.classList.remove('ss-active','ss-leaving');
        _lv.style.display='';
        en.classList.remove('ss-entering');
      }},DUR);
    }}
  }}
  setInterval(goNext,{interval_ms});
}})();</script>
</div>"""
