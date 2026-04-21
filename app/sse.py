import asyncio
from collections import defaultdict

# screen_id → set av asyncio.Queue per aktiv SSE-connection
_connections: dict[int, set[asyncio.Queue]] = defaultdict(set)


def register(screen_id: int) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=10)
    _connections[screen_id].add(q)
    return q


def unregister(screen_id: int, q: asyncio.Queue) -> None:
    _connections[screen_id].discard(q)


def connection_count(screen_id: int) -> int:
    return len(_connections[screen_id])


def broadcast(screen_id: int, event: dict) -> None:
    dead = set()
    for q in list(_connections[screen_id]):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.add(q)
    for q in dead:
        _connections[screen_id].discard(q)
