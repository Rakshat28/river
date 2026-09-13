"""In-memory, per-room session storage with per-room locking."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import AsyncGenerator

try:
    from agent.app.state import SessionState
except ImportError:  
    from app.state import SessionState


@dataclass
class RoomSession:
    """One room's mutable `SessionState` plus the lock serializing access to it.

    Pipecat can resolve several tool calls from a single LLM turn
    concurrently (parallel function calling). Without a per-room lock, two
    tool handlers could both read the same `SessionState.state_version`,
    each mutate their own view of the object, and the second write could
    silently clobber the first's changes — a classic read-modify-write race.
    """
    state: SessionState
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

_rooms: dict[str, RoomSession] = {}


def get_or_create(room_name: str, today: date) -> RoomSession:
    """Return the existing `RoomSession` for `room_name`, creating one if needed."""
    if room_name not in _rooms:
        now = datetime.now(timezone.utc)
        _rooms[room_name] = RoomSession(
            state=SessionState(room_name=room_name, today=today, updated_at=now)
        )
    return _rooms[room_name]


@asynccontextmanager
async def locked_state(room_name: str) -> AsyncGenerator[SessionState]:
    """Acquire `room_name`'s lock, yield its mutable `SessionState`, release on exit."""
    try:
        room = _rooms[room_name]
    except KeyError as exc:
        raise KeyError(
            f"No session exists for room {room_name!r}; get_or_create() must "
            "be called when the session is created, before any tool handler runs."
        ) from exc
    async with room.lock:
        yield room.state