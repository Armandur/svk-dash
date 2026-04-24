import glob
import html as html_mod
import json
import os
from typing import Any

_PDF_PAGES_DIR = "data/pdf_pages"
_VALID_TRANSITIONS = {"none", "fade", "slide"}


def _get_pages(uuid_stem: str) -> list[str]:
    pattern = os.path.join(_PDF_PAGES_DIR, uuid_stem + "-p*.png")
    files = sorted(glob.glob(pattern))
    return ["/pdf-pages/" + os.path.basename(f) for f in files]


def render(config: dict[str, Any], context: dict[str, Any]) -> str:
    upload_path = config.get("upload_path", "")
    if not upload_path:
        return '<div class="widget-pdf pdf-empty">Ingen PDF vald.</div>'

    uuid_stem = upload_path.rsplit(".", 1)[0]
    pages = _get_pages(uuid_stem)
    img_style = "width:100%;height:100%;object-fit:contain;display:block;"

    if not pages:
        src = html_mod.escape("/uploads/" + upload_path)
        if not config.get("toolbar", False):
            src += "#toolbar=0&navpanes=0"
        return (
            '<div class="widget-pdf">'
            f'<iframe src="{src}" style="border:none;width:100%;height:100%;" allow="fullscreen"></iframe>'
            '</div>'
        )

    if len(pages) == 1:
        src = html_mod.escape(pages[0])
        return (
            '<div class="widget-pdf">'
            f'<img src="{src}" alt="" style="{img_style}">'
            '</div>'
        )

    interval = max(3000, int(float(config.get("interval", 8)) * 1000))
    transition = config.get("transition", "fade")
    if transition not in _VALID_TRANSITIONS:
        transition = "fade"
    tc = f" ss-{transition}" if transition != "none" else ""
    tr_json = json.dumps(transition)

    slides = []
    for i, url in enumerate(pages):
        active = " ss-active" if i == 0 else ""
        src = html_mod.escape(url)
        slides.append(
            f'<div class="ss-slide{active}">'
            f'<img src="{src}" alt="" style="{img_style}">'
            '</div>'
        )
    slides_html = "".join(slides)

    return (
        f'<div class="widget-pdf{tc}">\n'
        + slides_html
        + '\n<script>(function(){'
        + 'var el=document.currentScript.parentElement;'
        + 'var slides=el.querySelectorAll(".ss-slide");'
        + 'if(slides.length<2)return;'
        + 'var cur=0,tr=' + tr_json + ';'
        + 'function goNext(){'
        + 'slides[cur].classList.remove("ss-active");'
        + 'cur=(cur+1)%slides.length;'
        + 'slides[cur].classList.add("ss-active");'
        + '}'
        + f'setInterval(goNext,{interval});'
        + '})();</script>\n'
        + '</div>'
    )
