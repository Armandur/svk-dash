from fastapi import Request

from app.auth import is_authenticated


class NotAuthenticatedError(Exception):
    pass


async def require_admin(request: Request) -> None:
    if not is_authenticated(request):
        raise NotAuthenticatedError
