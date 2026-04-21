from fastapi import APIRouter

from . import auth, screens, sse_control, views, widgets

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(screens.router)
router.include_router(views.router)
router.include_router(widgets.router)
router.include_router(sse_control.router)
