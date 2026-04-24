import asyncio
from collections import defaultdict

# screen_id → {Queue: metadata_dict}
_connections: dict[int, dict[asyncio.Queue, dict]] = defaultdict(dict)


def register(screen_id: int, meta: dict | None = None) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=10)
    _connections[screen_id][q] = meta or {}
    return q


def unregister(screen_id: int, q: asyncio.Queue) -> None:
    _connections[screen_id].pop(q, None)


def connection_count(screen_id: int) -> int:
    return len(_connections[screen_id])


def get_clients(screen_id: int) -> list[dict]:
    return list(_connections[screen_id].values())


def update_client_meta(screen_id: int, client_id: str, extra: dict) -> bool:
    for meta in _connections[screen_id].values():
        if meta.get("client_id") == client_id:
            meta.update(extra)
            return True
    return False


def broadcast(screen_id: int, event: dict) -> None:
    dead = set()
    for q in list(_connections[screen_id]):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            dead.add(q)
    for q in dead:
        _connections[screen_id].pop(q, None)
