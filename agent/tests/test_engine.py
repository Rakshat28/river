"""Unit tests for agent/app/engine.py functions."""

from datetime import date, datetime, timezone
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from agent.app.engine import (
        SessionState,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )
    from agent.app.state import Entry, FieldHistory
except ImportError:
    from app.engine import (
        SessionState,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )
    from app.state import Entry, FieldHistory


def _make_state() -> SessionState:
    return SessionState(
        room_name="test-engine-room",
        today=date(2026, 9, 14),
        updated_at=datetime.now(timezone.utc),
    )


class TestEngineCalculations:
    def test_compute_cash_position_surplus(self):
        state = _make_state()
        history_inc = FieldHistory(
            amount_paise=5000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        history_exp = FieldHistory(
            amount_paise=2000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.income.append(Entry(name="Salary", current=history_inc))
        state.essential_expenses.append(Entry(name="Rent", current=history_exp))

        assert compute_cash_position(state) == 3000000

    def test_compute_cash_position_exact_break_even(self):
        state = _make_state()
        history = FieldHistory(
            amount_paise=5000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.income.append(Entry(name="Salary", current=history))
        state.essential_expenses.append(Entry(name="Rent", current=history))

        assert compute_cash_position(state) == 0

    def test_compute_cash_position_shortfall(self):
        state = _make_state()
        history_inc = FieldHistory(
            amount_paise=2000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        history_exp = FieldHistory(
            amount_paise=5000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.income.append(Entry(name="Salary", current=history_inc))
        state.essential_expenses.append(Entry(name="Rent", current=history_exp))

        assert compute_cash_position(state) == -3000000

    def test_compute_cash_position_zero_or_missing_income(self):
        state = _make_state()
        history_exp = FieldHistory(
            amount_paise=2000000,
            confidence="confirmed",
            turn_index=1,
            timestamp=datetime.now(timezone.utc),
        )
        state.essential_expenses.append(Entry(name="Rent", current=history_exp))

        assert compute_cash_position(state) == -2000000

    def test_compute_missing_fields_and_blocking_issues(self):
        state = _make_state()
        assert compute_missing_fields(state) == ["income", "obligations"]
        assert compute_blocking_issues(state) == ["income", "obligations"]
