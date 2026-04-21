from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth import clear_session, create_session, verify_password
from app.config import ADMIN_PASSWORD_HASH
from app.templating import templates

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if _is_admin(request):
        return RedirectResponse("/admin/", status_code=302)
    return HTMLResponse(
        templates.get_template("admin/login.html").render(request=request, error=None)
    )


@router.post("/login")
async def login_post(request: Request, password: str = Form(...)):
    if ADMIN_PASSWORD_HASH and verify_password(password, ADMIN_PASSWORD_HASH):
        response = RedirectResponse("/admin/", status_code=302)
        create_session(response)
        return response
    return HTMLResponse(
        templates.get_template("admin/login.html").render(request=request, error="Fel lösenord."),
        status_code=401,
    )


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse("/admin/login", status_code=302)
    clear_session(response)
    return response


def _is_admin(request: Request) -> bool:
    from app.auth import is_authenticated

    return is_authenticated(request)
