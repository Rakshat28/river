"""Unit tests for focus derivation priority rules."""

import sys
from datetime import date, datetime, timezone
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.focus import ToolCallRecord, derive_focus
from app.state import SessionState


@pytest.fixture
def empty_state():
    return SessionState(
        room_name="test-focus-room",
        today=date(2026, 9, 14),
        updated_at=datetime.now(timezone.utc),
    )


def test_turn_zero_empty_calls_defaults_to_idle(empty_state):
    empty_state.turn_index = 0
    assert derive_focus("idle", [], empty_state) == "idle"


def test_empty_calls_preserves_previous_focus(empty_state):
    empty_state.turn_index = 2
    assert derive_focus("income", [], empty_state) == "income"


def test_finalize_plan_takes_highest_priority(empty_state):
    calls = [
        ToolCallRecord(tool_name="add_income", status="ok", target_list="income"),
        ToolCallRecord(tool_name="finalize_plan", status="ok"),
    ]
    assert derive_focus("income", calls, empty_state) == "plan"


def test_conflict_warning_takes_rank_2(empty_state):
    calls = [
        ToolCallRecord(tool_name="add_debt", status="ok", target_list="debts"),
        ToolCallRecord(tool_name="update_entry", status="warning"),
    ]
    assert derive_focus("income", calls, empty_state) == "conflict"


def test_duplicate_warning_takes_rank_3(empty_state):
    calls = [
        ToolCallRecord(tool_name="add_income", status="warning", target_list="income"),
        ToolCallRecord(
            tool_name="add_expense", status="ok", target_list="essential_expenses"
        ),
    ]
    assert derive_focus("income", calls, empty_state) == "duplicate"


def test_debt_call_beats_essential_expenses(empty_state):
    calls = [
        ToolCallRecord(
            tool_name="add_expense", status="ok", target_list="essential_expenses"
        ),
        ToolCallRecord(tool_name="add_debt", status="ok", target_list="debts"),
    ]
    assert derive_focus("income", calls, empty_state) == "debts"
