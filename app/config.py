import os

DATABASE_PATH = os.environ.get("DATABASE_PATH", "data/skarmar.db")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "session")
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 dagar

UPLOADS_DIR = os.environ.get("UPLOADS_DIR", "data/uploads")
