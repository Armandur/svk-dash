import asyncio
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from sqlmodel import select

from app.database import get_session
from app.models import Screen

logger = logging.getLogger(__name__)

_ALERT_AFTER_MINUTES = 15
_ALERT_COOLDOWN_HOURS = 4
_CHECK_INTERVAL_SECONDS = 300


def _smtp_config() -> dict | None:
    import os

    host = os.environ.get("SMTP_HOST", "")
    if not host:
        return None
    return {
        "host": host,
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASS", ""),
        "from_addr": os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", "")),
    }


def _send_alert_email(screen: Screen, offline_since: str) -> None:
    import os

    alert_email = os.environ.get("ALERT_EMAIL", "")
    if not alert_email:
        logger.warning("Skärmen '%s' svarar inte men ALERT_EMAIL saknas.", screen.name)
        return
    cfg = _smtp_config()
    if not cfg:
        logger.warning("Skärmen '%s' svarar inte men SMTP_HOST saknas.", screen.name)
        return

    body = (
        f"Skärmen \"{screen.name}\" (/s/{screen.slug}) har inte anslutit sedan {offline_since}.\n\n"
        f"Kontrollera att enheten är påslagen och har nätverksåtkomst.\n\n"
        f"-- Skärmar"
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"Skärm offline: {screen.name}"
    msg["From"] = cfg["from_addr"]
    msg["To"] = alert_email

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as srv:
            srv.starttls()
            if cfg["user"]:
                srv.login(cfg["user"], cfg["password"])
            srv.send_message(msg)
        logger.info("Larm skickat för skärm '%s' till %s.", screen.name, alert_email)
    except Exception:
        logger.exception("Kunde inte skicka larm-e-post för skärm '%s'.", screen.name)


async def check_screens() -> None:
    now = datetime.utcnow()
    threshold = now - timedelta(minutes=_ALERT_AFTER_MINUTES)
    cooldown = now - timedelta(hours=_ALERT_COOLDOWN_HOURS)

    with get_session() as db:
        screens = db.exec(select(Screen)).all()
        for screen in screens:
            if screen.last_seen_at is None:
                continue
            if screen.last_seen_at >= threshold:
                continue
            if screen.alert_sent_at is not None and screen.alert_sent_at >= cooldown:
                continue

            offline_since = screen.last_seen_at.strftime("%Y-%m-%d %H:%M UTC")
            _send_alert_email(screen, offline_since)
            screen.alert_sent_at = now
            db.add(screen)
        db.commit()


async def start_monitor_loop() -> None:
    while True:
        try:
            await check_screens()
        except Exception:
            logger.exception("Fel i screen_monitor")
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
