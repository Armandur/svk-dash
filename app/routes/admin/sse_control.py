from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app import sse as sse_registry
from app.deps import require_admin

router = APIRouter(dependencies=[Depends(require_admin)])


@router.post("/screens/{screen_id}/reload")
async def screen_reload(request: Request, screen_id: int):
    sse_registry.broadcast(screen_id, {"type": "reload"})
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)


@router.post("/screens/{screen_id}/goto/{position}")
async def screen_goto(request: Request, screen_id: int, position: int):
    sse_registry.broadcast(screen_id, {"type": "goto_view", "position": position})
    return RedirectResponse(f"/admin/screens/{screen_id}", status_code=302)
