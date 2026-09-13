"""Unit tests for agent/app/state.py."""
import asyncio
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

# agent/app is a namespace package (no __init__.py) rooted at agent/, which
# isn't necessarily on sys.path when pytest is invoked from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.session_store import get_or_create, locked_state
from app.state import (  # noqa: E402
    Conflict,
    Debt,
    Entry,
    FieldHistory,
    Recurrence,
    SessionState,
    compute_cash_position,
    compute_missing_fields,
)


def _field_history(amount_paise=100000, **overrides) -> FieldHistory:
    defaults = dict(
        amount_paise=amount_paise,
        confidence="confirmed",
        turn_index=0,
        timestamp=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return FieldHistory(**defaults)


def _entry(name: str = "Salary", amount_paise=100000, **overrides) -> Entry:
    defaults = dict(name=name, current=_field_history(amount_paise=amount_paise))
    defaults.update(overrides)
    return Entry(**defaults)


def _debt(**overrides) -> Debt:
    defaults = dict(
        name="Car Loan",
        current=_field_history(amount_paise=500000),
        kind="personal_loan",
        due_date=date(2026, 10, 1),
        min_payment_paise=500000,
    )
    defaults.update(overrides)
    return Debt(**defaults)


def _session_state(**overrides) -> SessionState:
    defaults = dict(
        room_name="room-1",
        today=date(2026, 9, 13),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SessionState(**defaults)


class TestFieldHistory:
    def test_valid_construction(self):
        fh = _field_history(amount_paise=1500000)
        assert fh.amount_paise == 1500000
        assert fh.confidence == "confirmed"

    def test_fractional_float_amount_raises(self):
        with pytest.raises(ValidationError):
            _field_history(amount_paise=1.5)

    def test_whole_number_float_amount_still_raises(self):
        # Strict mode: even a whole-number float (2.0) must be rejected,
        # not silently coerced to the int 2 — a float here means a caller
        # skipped money.py, and that must fail loudly.
        with pytest.raises(ValidationError):
            _field_history(amount_paise=2.0)

    def test_zero_amount_raises(self):
        with pytest.raises(ValidationError):
            _field_history(amount_paise=0)

    def test_negative_amount_raises(self):
        with pytest.raises(ValidationError):
            _field_history(amount_paise=-100)

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValidationError):
            _field_history(confidence="guessed")

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            _field_history(unexpected_field="nope")


class TestRecurrence:
    def test_count_defaults_to_one(self):
        rec = Recurrence(unit="month", interval=1)
        assert rec.count == 1

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Recurrence(unit="month", interval=1, count=1, unexpected_field="nope")

    def test_day_of_month_anchor(self):
        rec = Recurrence(unit="month", interval=1, count=1, day_of_month=6)
        assert rec.day_of_month == 6

    def test_two_different_day_of_month_anchors_are_independent(self):
        # The 6th-of-the-month EMI and the 23rd-of-the-month EMI are two
        # separate Recurrence (and Debt) instances, each with its own anchor.
        first = Recurrence(unit="month", interval=1, count=1, day_of_month=6)
        second = Recurrence(unit="month", interval=1, count=1, day_of_month=23)
        assert first.day_of_month == 6
        assert second.day_of_month == 23

    def test_day_of_week_anchor(self):
        rec = Recurrence(unit="week", interval=1, count=1, day_of_week=0)
        assert rec.day_of_week == 0

    def test_day_of_month_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            Recurrence(unit="month", interval=1, count=1, day_of_month=32)

    def test_day_of_month_zero_raises(self):
        with pytest.raises(ValidationError):
            Recurrence(unit="month", interval=1, count=1, day_of_month=0)

    def test_day_of_week_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            Recurrence(unit="week", interval=1, count=1, day_of_week=7)

    def test_day_of_month_on_non_month_unit_raises(self):
        with pytest.raises(ValidationError):
            Recurrence(unit="week", interval=1, count=1, day_of_month=6)

    def test_day_of_week_on_non_week_unit_raises(self):
        with pytest.raises(ValidationError):
            Recurrence(unit="month", interval=1, count=1, day_of_week=0)

    def test_day_of_month_with_count_above_one_raises(self):
        # A single anchor day can't describe "twice a month".
        with pytest.raises(ValidationError):
            Recurrence(unit="month", interval=1, count=2, day_of_month=6)

    def test_day_of_month_allows_31(self):
        # Allowed as stated even though not every month has a 31st —
        # clamping into shorter months is engine.py's job, not this model's.
        rec = Recurrence(unit="month", interval=1, count=1, day_of_month=31)
        assert rec.day_of_month == 31

    def test_quarterly_without_anchor_is_valid(self):
        rec = Recurrence(unit="month", interval=3, count=1)
        assert rec.day_of_month is None

    def test_twice_a_week_without_anchor_is_valid(self):
        rec = Recurrence(unit="week", interval=1, count=2)
        assert rec.day_of_week is None


class TestEntry:
    def test_default_id_format(self):
        entry = _entry()
        assert entry.id.startswith("entry_")
        assert len(entry.id) == len("entry_") + 8
        int(entry.id.removeprefix("entry_"), 16)  # must be valid hex

    def test_ids_are_unique(self):
        assert _entry().id != _entry().id

    def test_history_defaults_to_empty_list(self):
        assert _entry().history == []

    def test_history_is_a_separate_list_per_instance(self):
        # Guards against a mutable-default-argument-style bug where every
        # Entry would share the same underlying history list.
        a, b = _entry(), _entry()
        a_updated = a.model_copy(update={"history": [a.current]})
        assert a_updated.history == [a.current]
        assert b.history == []

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Entry(name="Salary", current=_field_history(), unexpected_field="nope")

    def test_duplicate_flags_default_false_and_none(self):
        entry = _entry()
        assert entry.possible_duplicate is False
        assert entry.duplicate_of is None

    def test_recurrence_defaults_to_monthly(self):
        rec = _entry().recurrence
        assert rec.unit == "month"
        assert rec.interval == 1
        assert rec.count == 1

    def test_recurrence_accepts_one_time(self):
        entry = _entry(recurrence="one_time")
        assert entry.recurrence == "one_time"

    def test_recurrence_accepts_every_n_months(self):
        # e.g. a quarterly insurance premium
        entry = _entry(recurrence={"unit": "month", "interval": 3, "count": 1})
        assert entry.recurrence.unit == "month"
        assert entry.recurrence.interval == 3

    def test_recurrence_accepts_multiple_times_per_week(self):
        # e.g. a tutor paid twice a week
        entry = _entry(recurrence={"unit": "week", "interval": 1, "count": 2})
        assert entry.recurrence.count == 2

    def test_recurrence_accepts_fortnightly_via_day_interval(self):
        entry = _entry(recurrence={"unit": "day", "interval": 14, "count": 1})
        assert entry.recurrence.unit == "day"
        assert entry.recurrence.interval == 14

    def test_recurrence_rejects_invalid_literal_string(self):
        with pytest.raises(ValidationError):
            _entry(recurrence="weekly")

    def test_recurrence_rejects_zero_interval(self):
        with pytest.raises(ValidationError):
            _entry(recurrence={"unit": "month", "interval": 0, "count": 1})

    def test_recurrence_rejects_zero_count(self):
        with pytest.raises(ValidationError):
            _entry(recurrence={"unit": "week", "interval": 1, "count": 0})

    def test_recurrence_rejects_unknown_unit(self):
        with pytest.raises(ValidationError):
            _entry(recurrence={"unit": "year", "interval": 1, "count": 1})

    def test_recurrence_rejects_float_interval(self):
        with pytest.raises(ValidationError):
            _entry(recurrence={"unit": "month", "interval": 1.5, "count": 1})


class TestDebt:
    def test_valid_construction(self):
        debt = _debt()
        assert debt.kind == "personal_loan"
        assert debt.min_payment_paise == 500000
        assert debt.balance_paise is None
        assert debt.interest_rate_bps is None

    def test_min_payment_zero_raises(self):
        with pytest.raises(ValidationError):
            _debt(min_payment_paise=0)

    def test_min_payment_negative_raises(self):
        with pytest.raises(ValidationError):
            _debt(min_payment_paise=-5000)

    def test_min_payment_float_raises(self):
        with pytest.raises(ValidationError):
            _debt(min_payment_paise=5000.0)

    def test_invalid_kind_raises(self):
        with pytest.raises(ValidationError):
            _debt(kind="mortgage")

    def test_interest_rate_bps_accepts_int(self):
        debt = _debt(interest_rate_bps=1250)
        assert debt.interest_rate_bps == 1250

    def test_interest_rate_bps_rejects_float(self):
        with pytest.raises(ValidationError):
            _debt(interest_rate_bps=12.5)

    def test_balance_paise_rejects_float(self):
        with pytest.raises(ValidationError):
            _debt(balance_paise=100000.0)

    def test_due_date_is_a_date_not_datetime(self):
        debt = _debt()
        assert type(debt.due_date) is date

    def test_default_recurrence_is_monthly(self):
        rec = _debt().recurrence
        assert rec.unit == "month" and rec.interval == 1

    @pytest.mark.parametrize(
        "kind",
        [
            "personal_loan",
            "credit_card",
            "education_loan",
            "vehicle_loan",
            "home_loan",
            "gold_loan",
            "bnpl",
            "informal",
        ],
    )
    def test_each_non_other_kind_is_valid_without_a_label(self, kind):
        debt = _debt(kind=kind)
        assert debt.kind == kind
        assert debt.kind_label is None

    def test_other_kind_without_label_raises(self):
        with pytest.raises(ValidationError):
            _debt(kind="other")

    def test_other_kind_with_blank_label_raises(self):
        with pytest.raises(ValidationError):
            _debt(kind="other", kind_label="   ")

    def test_other_kind_with_label_is_valid(self):
        debt = _debt(kind="other", kind_label="Chit fund contribution")
        assert debt.kind_label == "Chit fund contribution"

    def test_non_other_kind_may_still_carry_a_label(self):
        debt = _debt(kind="vehicle_loan", kind_label="Activa loan, Bajaj Finance")
        assert debt.kind_label == "Activa loan, Bajaj Finance"

    def test_is_secured_defaults_to_none(self):
        assert _debt().is_secured is None

    def test_two_emis_on_different_days_of_month_are_independent_debts(self):
        emi_6th = _debt(
            name="Car Loan",
            due_date=date(2026, 10, 6),
            recurrence={"unit": "month", "interval": 1, "count": 1, "day_of_month": 6},
        )
        emi_23rd = _debt(
            name="Home Loan",
            kind="home_loan",
            due_date=date(2026, 10, 23),
            recurrence={"unit": "month", "interval": 1, "count": 1, "day_of_month": 23},
        )
        assert emi_6th.due_date.day == 6
        assert emi_23rd.due_date.day == 23
        assert emi_6th.recurrence.day_of_month == 6
        assert emi_23rd.recurrence.day_of_month == 23
        assert emi_6th.id != emi_23rd.id


class TestConflict:
    def test_valid_construction(self):
        conflict = Conflict(
            id="conflict_1",
            entry_id="entry_abcd1234",
            field_name="amount_paise",
            old_amount_paise=100000,
            new_amount_paise=150000,
            created_at=datetime.now(timezone.utc),
        )
        assert conflict.resolved is False

    def test_float_amounts_raise(self):
        with pytest.raises(ValidationError):
            Conflict(
                id="conflict_1",
                entry_id="entry_abcd1234",
                field_name="amount_paise",
                old_amount_paise=100000.0,
                new_amount_paise=150000,
                created_at=datetime.now(timezone.utc),
            )

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            Conflict(
                id="conflict_1",
                entry_id="entry_abcd1234",
                field_name="amount_paise",
                old_amount_paise=100000,
                new_amount_paise=150000,
                created_at=datetime.now(timezone.utc),
                unexpected_field="nope",
            )


class TestSessionState:
    def test_valid_construction_with_defaults(self):
        state = _session_state()
        assert state.income == []
        assert state.essential_expenses == []
        assert state.optional_expenses == []
        assert state.debts == []
        assert state.conflicts == []
        assert state.turn_index == 0
        assert state.state_version == 0
        assert state.plan is None

    def test_today_is_a_date_not_datetime(self):
        state = _session_state()
        assert type(state.today) is date

    def test_extra_field_rejected(self):
        with pytest.raises(ValidationError):
            _session_state(unexpected_field="nope")

    def test_list_fields_are_independent_per_instance(self):
        a = _session_state()
        b = _session_state(income=[_entry()])
        assert a.income == []
        assert len(b.income) == 1


class TestComputeCashPosition:
    def test_worked_example_from_prompt(self):
        # income: ₹50,000 confirmed + ₹10,000 estimated
        # essential expenses: ₹15,000 confirmed
        # expected: (5,000,000) - (1,500,000) = 3,500,000 paise
        state = _session_state(
            income=[
                _entry(
                    name="Salary",
                    current=_field_history(amount_paise=5000000, confidence="confirmed"),
                ),
                _entry(
                    name="Freelance",
                    current=_field_history(amount_paise=1000000, confidence="estimated"),
                ),
            ],
            essential_expenses=[
                _entry(
                    name="Rent",
                    current=_field_history(amount_paise=1500000, confidence="confirmed"),
                )
            ],
        )
        assert compute_cash_position(state) == 3_500_000

    def test_estimated_entries_contribute_nothing_not_a_discount(self):
        state = _session_state(
            income=[
                _entry(
                    name="Bonus",
                    current=_field_history(amount_paise=2000000, confidence="estimated"),
                )
            ]
        )
        # Not partial credit at some discounted weight — exactly zero.
        assert compute_cash_position(state) == 0

    def test_debts_and_optional_expenses_are_ignored(self):
        state = _session_state(
            income=[
                _entry(
                    name="Salary",
                    current=_field_history(amount_paise=5000000, confidence="confirmed"),
                )
            ],
            optional_expenses=[
                _entry(
                    name="Netflix",
                    current=_field_history(amount_paise=50000, confidence="confirmed"),
                )
            ],
            debts=[_debt()],
        )
        # Only confirmed income minus confirmed essential expenses; debts
        # and optional_expenses must not move this number at all.
        assert compute_cash_position(state) == 5_000_000

    def test_empty_state_returns_zero(self):
        assert compute_cash_position(_session_state()) == 0

    def test_return_type_is_plain_int(self):
        state = _session_state(
            income=[
                _entry(
                    name="Salary",
                    current=_field_history(amount_paise=5000000, confidence="confirmed"),
                )
            ]
        )
        assert type(compute_cash_position(state)) is int

    def test_negative_cash_position_when_expenses_exceed_income(self):
        state = _session_state(
            income=[
                _entry(
                    name="Salary",
                    current=_field_history(amount_paise=1000000, confidence="confirmed"),
                )
            ],
            essential_expenses=[
                _entry(
                    name="Rent",
                    current=_field_history(amount_paise=1500000, confidence="confirmed"),
                )
            ],
        )
        assert compute_cash_position(state) == -500000
    def test_empty_state_missing_both(self):
        state = _session_state()
        assert compute_missing_fields(state) == ["income", "obligations"]

    def test_income_only_missing_obligations(self):
        state = _session_state(income=[_entry()])
        assert compute_missing_fields(state) == ["obligations"]

    def test_income_and_essential_expense_missing_nothing(self):
        state = _session_state(
            income=[_entry()],
            essential_expenses=[_entry(name="Rent", amount_paise=2000000)],
        )
        assert compute_missing_fields(state) == []

    def test_income_and_debt_no_essential_missing_nothing(self):
        state = _session_state(income=[_entry()], debts=[_debt()])
        assert compute_missing_fields(state) == []

    def test_income_and_optional_expense_only_still_missing_obligations(self):
        # optional_expenses must not count toward satisfying 'obligations'.
        state = _session_state(
            income=[_entry()],
            optional_expenses=[_entry(name="Netflix", amount_paise=50000)],
        )
        assert compute_missing_fields(state) == ["obligations"]

    def test_no_income_but_has_obligations(self):
        state = _session_state(essential_expenses=[_entry(name="Rent")])
        assert compute_missing_fields(state) == ["income"]

    def test_fully_populated_state_missing_nothing(self):
        state = _session_state(
            income=[_entry()],
            essential_expenses=[_entry(name="Rent", amount_paise=2000000)],
            optional_expenses=[_entry(name="Netflix", amount_paise=50000)],
            debts=[_debt()],
        )
        assert compute_missing_fields(state) == []

class TestLockedStateConcurrency:
    """Step 3.5's acceptance check: `agent/app/session_store.py`'s per-room
    `asyncio.Lock` must stop two tool calls resolved within the same LLM
    turn (parallel function calling) from racing on the same `SessionState`
    object (implementation-plan.md Section 13.7). Uses `asyncio.run(...)`
    inside a plain `def test_...` rather than `pytest.mark.asyncio`, matching
    the convention already used for async code in `test_daily_client.py` —
    `pytest-asyncio` isn't a project dependency and adding one is an
    "ask first" item (AGENTS.md Section 9).
    """
 
    def test_two_concurrent_mutations_are_both_preserved(self):
        room_name = "concurrency-test-room"
 
        async def _add_income(name: str) -> None:
            async with locked_state(room_name) as state:
                # Force an interleaving point in the middle of the
                # read-modify-write: without the per-room lock, this yield
                # is exactly where the other coroutine's mutation could
                # race in and get silently clobbered by this one's write.
                await asyncio.sleep(0)
                state.income.append(_entry(name=name))
                state.state_version += 1
 
        async def _run() -> SessionState:
            get_or_create(room_name, date(2026, 9, 13))
            await asyncio.gather(_add_income("Salary"), _add_income("Freelance"))
            async with locked_state(room_name) as state:
                return state
 
        state = asyncio.run(_run())
 
        # Both mutations present -> neither was lost to the race.
        assert {entry.name for entry in state.income} == {"Salary", "Freelance"}
        assert len(state.income) == 2
        # Incremented by exactly 2, not 1 -> confirms serialization, not
        # just "both entries happened to survive by luck".
        assert state.state_version == 2
 
    def test_get_or_create_returns_the_same_room_session_on_repeat_calls(self):
        room_name = "get-or-create-idempotency-room"
        first = get_or_create(room_name, date(2026, 9, 13))
        # A different `today` on the second call must not reset or replace
        # the already-created session.
        second = get_or_create(room_name, date(2099, 1, 1))
        assert first is second
        assert second.state.today == date(2026, 9, 13)
 
    def test_locked_state_raises_for_unknown_room(self):
        async def _run() -> None:
            async with locked_state("room-that-was-never-created"):
                pass  # pragma: no cover - should never reach the body
 
        with pytest.raises(KeyError):
            asyncio.run(_run())