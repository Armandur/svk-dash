from fastapi import APIRouter

from . import auth, channels, layouts, media, notifications, palette, screens, settings, sse_control, views, widgets

router = APIRouter(prefix="/admin")
router.include_router(auth.router)
router.include_router(channels.router)
router.include_router(screens.router)
router.include_router(views.router)
router.include_router(widgets.router)
router.include_router(media.router)
router.include_router(layouts.router)
router.include_router(sse_control.router)
router.include_router(palette.router, prefix="/palette")
router.include_router(notifications.router, prefix="/notifications")
router.include_router(settings.router, prefix="/settings")
