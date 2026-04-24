from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import DEFAULT_TIMEZONE, get_setting, set_setting
from app.deps import require_admin
from app.templating import templates

router = APIRouter(dependencies=[Depends(require_admin)])

COMMON_TIMEZONES = [
    "Europe/Stockholm",
    "Europe/Helsinki",
    "Europe/Berlin",
    "Europe/London",
    "UTC",
]


def _render(request: Request, current_tz: str, error: str | None = None) -> HTMLResponse:
    return HTMLResponse(
        templates.get_template("admin/settings.html").render(
            request=request,
            current_tz=current_tz,
            common_timezones=COMMON_TIMEZONES,
            error=error,
        )
    )


@router.get("/", response_class=HTMLResponse)
async def settings_index(request: Request):
    return _render(request, get_setting("timezone", DEFAULT_TIMEZONE))


@router.post("/")
async def save_settings(request: Request, timezone: str = Form(...)):
    timezone = timezone.strip()
    try:
        ZoneInfo(timezone)
    except Exception:
        return _render(
            request,
            timezone,
            error=f"Ogiltig tidszon: '{timezone}'. Ange en giltig IANA-tidszon, t.ex. Europe/Stockholm.",
        )
    set_setting("timezone", timezone)
    return RedirectResponse("/admin/settings/", status_code=302)
