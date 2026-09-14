"""Unit tests for agent/app/broadcast.py and per-turn broadcast batching."""

import asyncio
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from pipecat.frames.frames import LLMFullResponseEndFrame

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.broadcast import (
    BroadcastPayload,
    TurnBroadcastProcessor,
    clear_room_dirty,
    is_room_dirty,
    mark_room_dirty,
    to_broadcast_payload,
)
from app.session_store import get_or_create, locked_state
from app.state import Entry, FieldHistory, SessionState
from app.tools import add_income
from app.validation import AddIncomeArgs


def _field_history(amount_paise=100000) -> FieldHistory:
    return FieldHistory(
        amount_paise=amount_paise,
        confidence="confirmed",
        turn_index=0,
        timestamp=datetime.now(timezone.utc),
    )


class TestBroadcastPayload:
    def test_to_broadcast_payload_excludes_history(self):
        """Step 5.1 Acceptance check: history list must be stripped in broadcast payload."""
        now = datetime.now(timezone.utc)
        history_5_items = [
            _field_history(amount_paise=(i + 1) * 100000) for i in range(5)
        ]

        entry_with_history = Entry(
            name="Primary Salary",
            current=_field_history(amount_paise=5000000),
            history=history_5_items,
        )

        state = SessionState(
            room_name="test-broadcast-room-1",
            today=date(2026, 9, 14),
            income=[entry_with_history],
            state_version=3,
            updated_at=now,
        )

        payload: BroadcastPayload = to_broadcast_payload(state)

        assert payload.state_version == 3
        assert payload.room_name == "test-broadcast-room-1"
        assert payload.updated_at == now
        assert len(payload.income) == 1

        broadcast_entry = payload.income[0]
        assert broadcast_entry.name == "Primary Salary"
        assert broadcast_entry.current.amount_paise == 5000000
        # Critical assertion: history list MUST be empty in broadcast payload
        assert broadcast_entry.history == []

    def test_dirty_flag_tracking(self):
        room_name = "test-dirty-flag-room"
        clear_room_dirty(room_name)
        assert is_room_dirty(room_name) is False

        mark_room_dirty(room_name)
        assert is_room_dirty(room_name) is True

        clear_room_dirty(room_name)
        assert is_room_dirty(room_name) is False


class TestPerTurnBatching:
    def test_state_mutation_sets_dirty_flag_and_increments_version(self):
        room_name = "test-mutation-dirty-room"
        get_or_create(room_name, date(2026, 9, 14))
        clear_room_dirty(room_name)

        args = AddIncomeArgs(
            name="Salary",
            amount_rupees=50000,
            date="2026-09-20",
            confidence="confirmed",
        )
        res = asyncio.run(add_income(room_name, args))

        assert res.status == "ok"
        assert is_room_dirty(room_name) is True

        async def _check_version():
            async with locked_state(room_name) as state:
                return state.state_version

        assert asyncio.run(_check_version()) == 1

    def test_turn_broadcast_processor_clears_dirty_flag(self):
        room_name = "test-turn-processor-room"
        get_or_create(room_name, date(2026, 9, 14))
        mark_room_dirty(room_name)
        assert is_room_dirty(room_name) is True

        processor = TurnBroadcastProcessor(room_name)
        frame = LLMFullResponseEndFrame()

        asyncio.run(processor.process_frame(frame, None))

        assert is_room_dirty(room_name) is False
