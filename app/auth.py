import bcrypt
from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import SECRET_KEY, SESSION_COOKIE_NAME, SESSION_MAX_AGE

_serializer = URLSafeTimedSerializer(SECRET_KEY)
_SESSION_PAYLOAD = "admin"


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_session(response: Response) -> None:
    token = _serializer.dumps(_SESSION_PAYLOAD, salt="session")
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # True i prod bakom Caddy (HTTPS)
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def is_authenticated(request: Request) -> bool:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return False
    try:
        payload = _serializer.loads(token, salt="session", max_age=SESSION_MAX_AGE)
        return payload == _SESSION_PAYLOAD
    except (BadSignature, SignatureExpired):
        return False
