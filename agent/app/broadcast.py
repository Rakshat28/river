"""Broadcast payload models and transport message utilities for live frontend state syncing."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pipecat.frames.frames import (
    Frame,
    LLMFullResponseEndFrame,
    OutputTransportMessageFrame,
)
from pipecat.processors.frame_processor import FrameProcessor

try:
    from agent.app.session_store import locked_state
    from agent.app.state import Conflict, Debt, Entry, SessionState
except ImportError:
    from app.session_store import locked_state
    from app.state import Conflict, Debt, Entry, SessionState

logger = logging.getLogger(__name__)


# Daily app-messages have a practical size limit (commonly cited around a few KB),
# and a growing audit trail on every entry would eventually risk exceeding it —
# trimming it from the live-update path avoids that risk entirely rather than hoping it never comes up.
class TrimmedEntry(Entry):
    """Entry model variant with history defaulted to an empty list for broadcast payloads."""

    history: list[Any] = Field(default_factory=list)


class TrimmedDebt(Debt):
    """Debt model variant with history defaulted to an empty list for broadcast payloads."""

    history: list[Any] = Field(default_factory=list)


class BroadcastPayload(BaseModel):
    """Trimmed view of SessionState sent to the frontend over WebRTC app-messages."""

    model_config = ConfigDict(extra="forbid")

    room_name: str
    today: date
    income: list[TrimmedEntry] = Field(default_factory=list)
    essential_expenses: list[TrimmedEntry] = Field(default_factory=list)
    optional_expenses: list[TrimmedEntry] = Field(default_factory=list)
    debts: list[TrimmedDebt] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    plan: Any | None = None
    turn_index: int = 0
    state_version: int = 0
    updated_at: datetime


def _trim_entry(entry: Entry) -> TrimmedEntry:
    data = entry.model_dump()
    data["history"] = []
    return TrimmedEntry(**data)


def _trim_debt(debt: Debt) -> TrimmedDebt:
    data = debt.model_dump()
    data["history"] = []
    return TrimmedDebt(**data)


def to_broadcast_payload(state: SessionState) -> BroadcastPayload:
    """Convert SessionState to a trimmed BroadcastPayload (excluding history)."""
    return BroadcastPayload(
        room_name=state.room_name,
        today=state.today,
        income=[_trim_entry(e) for e in state.income],
        essential_expenses=[_trim_entry(e) for e in state.essential_expenses],
        optional_expenses=[_trim_entry(e) for e in state.optional_expenses],
        debts=[_trim_debt(d) for d in state.debts],
        conflicts=list(state.conflicts),
        plan=state.plan,
        turn_index=state.turn_index,
        state_version=state.state_version,
        updated_at=state.updated_at,
    )


_dirty_rooms: set[str] = set()
_transports: dict[str, Any] = {}


def mark_room_dirty(room_name: str) -> None:
    """Set the per-room dirty flag when state is mutated during an LLM turn."""
    _dirty_rooms.add(room_name)


def clear_room_dirty(room_name: str) -> None:
    """Clear the per-room dirty flag after turn broadcast."""
    _dirty_rooms.discard(room_name)


def is_room_dirty(room_name: str) -> bool:
    """Check if state has been mutated during the current turn."""
    return room_name in _dirty_rooms


def register_room_transport(room_name: str, transport: Any) -> None:
    """Register a room's active DailyTransport for app-message broadcasts."""
    _transports[room_name] = transport


def unregister_room_transport(room_name: str) -> None:
    """Unregister a room's transport on session end."""
    _transports.pop(room_name, None)


async def broadcast_state_update(room_name: str) -> bool:
    """Build BroadcastPayload from current SessionState and send via Daily app-message."""
    try:
        async with locked_state(room_name) as state:
            payload = to_broadcast_payload(state)

        message_data = {
            "type": "state_update",
            "payload": payload.model_dump(mode="json"),
        }

        transport = _transports.get(room_name)
        if transport is not None:
            # If transport pipeline output is accessible, push OutputTransportMessageFrame
            if hasattr(transport, "output"):
                frame = OutputTransportMessageFrame(message=message_data)
                await transport.output().process_frame(frame, None)
            elif hasattr(transport, "send_app_message"):
                await transport.send_app_message(message_data)
        logger.info(
            f"Broadcast state update for room {room_name} (version={payload.state_version})"
        )
        return True
    except Exception as exc:
        logger.error(
            f"Failed to broadcast state update for room {room_name}: {exc}",
            exc_info=True,
        )
        return False


class TurnBroadcastProcessor(FrameProcessor):
    """Pipeline processor that triggers a single broadcast update at the end of an LLM turn."""

    def __init__(self, room_name: str):
        super().__init__()
        self._room_name = room_name

    async def process_frame(self, frame: Frame, direction: Any) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMFullResponseEndFrame):
            if is_room_dirty(self._room_name):
                await broadcast_state_update(self._room_name)
                clear_room_dirty(self._room_name)
        await self.push_frame(frame, direction)
