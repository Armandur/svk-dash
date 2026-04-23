import asyncio
import logging
from datetime import datetime

from sqlmodel import select

from app import sse as sse_registry
from app.database import get_session
from app.models import Screen, ScreenLayoutAssignment

logger = logging.getLogger(__name__)

# screen_id -> senast aktiva assignment id
_last_active: dict[int, int | None] = {}


def _active_assignment_id(assignments: list[ScreenLayoutAssignment], now: datetime) -> int | None:
    """Väljer den mest prioriterade aktiva tilldelningen baserat på schema."""
    active = []
    current_day = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"][int(now.strftime("%w"))]
    current_time = now.strftime("%H:%M")

    for a in assignments:
        # Veckodagar
        if a.weekdays:
            days = [d.strip() for d in a.weekdays.split(",")]
            if current_day not in days:
                continue

        # Tid
        if a.time_start and current_time < a.time_start:
            continue
        if a.time_end and current_time >= a.time_end:
            continue

        active.append(a)

    if not active:
        return None

    # Sortera på prioritet (högst först)
    active.sort(key=lambda x: x.priority, reverse=True)
    return active[0].id


async def check_layout_schedules():
    with get_session() as db:
        screens = db.exec(select(Screen)).all()
        now = datetime.now()

        for screen in screens:
            assignments = db.exec(
                select(ScreenLayoutAssignment).where(ScreenLayoutAssignment.screen_id == screen.id)
            ).all()

            if not assignments:
                continue

            active_id = _active_assignment_id(assignments, now)
            prev_id = _last_active.get(screen.id, "not_set")

            if active_id != prev_id:
                if prev_id != "not_set":
                    logger.info(f"Layout change for screen {screen.slug}: {prev_id} -> {active_id}")
                    sse_registry.broadcast(screen.id, {"type": "reload"})
                _last_active[screen.id] = active_id


async def start_layout_scheduler():
    logger.info("Starting layout scheduler")
    while True:
        try:
            await check_layout_schedules()
        except Exception as e:
            logger.error(f"Error in layout scheduler: {e}")
        await asyncio.sleep(60)
