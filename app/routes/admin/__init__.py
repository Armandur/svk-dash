from fastapi import APIRouter

from . import auth, screens, views, widgets

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(screens.router)
router.include_router(views.router)
router.include_router(widgets.router)
