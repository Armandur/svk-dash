import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/skarmar.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "session")
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 dagar

UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "data/uploads")

DEFAULT_TIMEZONE = "Europe/Stockholm"


def get_setting(key: str, default: str = "") -> str:
    from app.database import get_session
    from app.models import AppSetting

    try:
        with get_session() as db:
            s = db.get(AppSetting, key)
            return s.value if s else default
    except Exception:
        return default


def set_setting(key: str, value: str) -> None:
    from app.database import get_session
    from app.models import AppSetting

    with get_session() as db:
        s = db.get(AppSetting, key) or AppSetting(key=key)
        s.value = value
        db.add(s)
        db.commit()
