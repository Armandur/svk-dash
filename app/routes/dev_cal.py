"""Lokal ICS-kalender för dev-miljön. Registreras bara när DEV_SEED=true."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()

DEV_CAL_URL = "http://localhost:8000/dev-cal.ics"
_TZ = ZoneInfo("Europe/Stockholm")


def _fmt_dt(d: date, h: int, m: int) -> str:
    return f"{d.year}{d.month:02d}{d.day:02d}T{h:02d}{m:02d}00"


def _fmt_date(d: date) -> str:
    return f"{d.year}{d.month:02d}{d.day:02d}"


def _ev(n: int, summary: str, d: date, h0: int, m0: int, h1: int, m1: int,
        location: str = "", cls: str = "", status: str = "", transp: str = "") -> str:
    lines = [
        "BEGIN:VEVENT",
        f"UID:dev-{n:03d}@skarmar",
        f"SUMMARY:{summary}",
        f"DTSTART;TZID=Europe/Stockholm:{_fmt_dt(d, h0, m0)}",
        f"DTEND;TZID=Europe/Stockholm:{_fmt_dt(d, h1, m1)}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    if cls:
        lines.append(f"CLASS:{cls}")
    if status:
        lines.append(f"STATUS:{status}")
    if transp:
        lines.append(f"TRANSP:{transp}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


def _ad(n: int, summary: str, d: date, days: int = 1,
        location: str = "", status: str = "") -> str:
    end = d + timedelta(days=days)
    lines = [
        "BEGIN:VEVENT",
        f"UID:dev-{n:03d}@skarmar",
        f"SUMMARY:{summary}",
        f"DTSTART;VALUE=DATE:{_fmt_date(d)}",
        f"DTEND;VALUE=DATE:{_fmt_date(end)}",
    ]
    if location:
        lines.append(f"LOCATION:{location}")
    if status:
        lines.append(f"STATUS:{status}")
    lines.append("END:VEVENT")
    return "\r\n".join(lines)


def generate_ics() -> str:
    today = datetime.now(_TZ).date()
    mon = today - timedelta(days=today.weekday())

    events = [
        # ── Historik (bakåt 30 dagar — för månadsvy) ────────────────────────
        _ev(1,  "Styrelsemöte",           today - timedelta(28),  9,  0, 11,  0, "Konferensrum A"),
        _ad(2,  "Personalutbildning",     today - timedelta(25),  days=2),
        _ev(3,  "Uppföljning budget",     today - timedelta(21), 13,  0, 14, 30, "Rum 201"),
        _ev(4,  "Teams: Projektmöte",    today - timedelta(14), 10,  0, 11,  0,
            "https://teams.microsoft.com/l/meetup-join/dev123"),
        _ev(5,  "Kvartalsmöte",          today - timedelta(10),  9,  0, 12,  0, "Stora salen"),
        _ad(6,  "Konferensdagar",        today - timedelta(7),   days=2, location="Sigtuna"),
        _ev(7,  "Veckovisa avstämning",  today - timedelta(3),   8, 30,  9,  0, "Rum 101"),
        # ── Resten av nuvarande vecka ────────────────────────────────────────
        _ev(10, "Morgonmöte",            mon,                     8,  0,  9,  0, "Rum 101"),
        _ev(11, "Projektuppstart",       mon + timedelta(1),     10,  0, 12,  0, "Konferensrum B"),
        _ev(12, "Lunch med leverantör",  mon + timedelta(2),     12,  0, 13, 30, "Restaurang Solen"),
        _ev(13, "Kvartalsgenomgång",     mon + timedelta(3),      9,  0, 11,  0, "Stora salen"),
        _ad(14, "Utbildningsdag",        mon + timedelta(4)),
        # ── Idag (flera typer) ───────────────────────────────────────────────
        _ev(20, "Daglig standup",        today,  9,  0,  9, 15, "Rum 101"),
        _ev(21, "Kundpresentation",      today, 14,  0, 15, 30, "Konferensrum A"),
        _ev(22, "Friskvård",             today, 12,  0, 13,  0, transp="TRANSPARENT"),
        _ev(23, "Privat: Läkartid",      today, 10,  0, 10, 30, cls="PRIVATE"),
        _ev(24, "Tentativt: Förstudien", today, 16,  0, 17,  0, "Rum 201", status="TENTATIVE"),
        # ── Kommande ────────────────────────────────────────────────────────
        _ev(30, "Zoom: Uppföljning",     today + timedelta(2),  10,  0, 11,  0,
            "https://zoom.us/j/987654321"),
        _ev(31, "Veckovisa avstämning",  today + timedelta(3),   8, 30,  9,  0, "Rum 101"),
        _ev(32, "Budgetmöte",            today + timedelta(7),   9,  0, 11,  0, "Konferensrum B"),
        _ad(33, "Sommarkonferens",       today + timedelta(10),  days=3, location="Göteborg"),
        _ev(34, "Personalfest",          today + timedelta(14), 17,  0, 22,  0, "Församlingshemmet"),
        _ev(35, "Musikövning",           today + timedelta(21), 18,  0, 20,  0, "Kyrksalen"),
        _ev(36, "Kyrkoråd",              today + timedelta(28), 17,  0, 19, 30, "Konferensrum A"),
        _ad(37, "Helgdag",               today + timedelta(30)),
    ]

    header = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//svk-dash//dev//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "X-WR-CALNAME:Dev-kalender\r\n"
        "X-WR-TIMEZONE:Europe/Stockholm\r\n"
    )
    return header + "\r\n".join(events) + "\r\nEND:VCALENDAR\r\n"


@router.get("/dev-cal.ics")
async def dev_calendar():
    return PlainTextResponse(generate_ics(), media_type="text/calendar; charset=utf-8")
