"""Unit tests for agent/app/tools.py."""

import asyncio
import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure agent module is accessible when pytest is run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.session_store import get_or_create, locked_state
from app.validation import (
    AddDebtArgs,
    AddExpenseArgs,
    AddIncomeArgs,
    ResolveDuplicateArgs,
    UpdateEntryArgs,
)
from app.state import SessionState
from app.tools import (
    ToolResult,
    state_mutation,
    add_debt,
    add_expense,
    add_income,
    resolve_duplicate,
    update_entry,
)


class TestToolResult:
    def test_ok_constructor(self):
        result = ToolResult.ok(entry_id="entry_123", amount=500)
        assert result.status == "ok"
        assert result.message is None
        assert result.data == {"entry_id": "entry_123", "amount": 500}

    def test_warning_constructor(self):
        result = ToolResult.warning("possible duplicate found", entry_id="entry_abc")
        assert result.status == "warning"
        assert result.message == "possible duplicate found"
        assert result.data == {"entry_id": "entry_abc"}

    def test_error_constructor(self):
        result = ToolResult.error("missing required field")
        assert result.status == "error"
        assert result.message == "missing required field"
        assert result.data == {}

    def test_invalid_status_rejected_by_literal(self):
        with pytest.raises(ValidationError):
            ToolResult(status="pending")  # type: ignore[arg-type]

    def test_extra_fields_rejected(self):
        with pytest.raises(ValidationError):
            ToolResult(status="ok", unexpected="field")


class TestStateMutationDecorator:
    def test_increments_version_and_returns_result_on_success(self):
        room_name = "test-decorator-success-room"
        get_or_create(room_name, date(2026, 9, 14))

        @state_mutation
        async def dummy_handler(
            room_name: str, state: SessionState = None
        ) -> ToolResult:
            return ToolResult.ok(did_work=True)

        async def _run():
            result = await dummy_handler(room_name)
            async with locked_state(room_name) as state:
                return result, state

        result, final_state = asyncio.run(_run())

        assert result.status == "ok"
        assert result.data == {"did_work": True}
        assert final_state.state_version == 1

    def test_does_not_increment_on_error(self):
        room_name = "test-decorator-error-room"
        get_or_create(room_name, date(2026, 9, 14))

        @state_mutation
        async def error_handler(
            room_name: str, state: SessionState = None
        ) -> ToolResult:
            return ToolResult.error("validation failed")

        async def _run():
            result = await error_handler(room_name)
            async with locked_state(room_name) as state:
                return result, state

        result, final_state = asyncio.run(_run())

        assert result.status == "error"
        assert final_state.state_version == 0  # Did not increment

    def test_lock_is_released_even_if_handler_raises_exception(self):
        room_name = "test-decorator-exception-room"
        get_or_create(room_name, date(2026, 9, 14))

        @state_mutation
        async def failing_handler(
            room_name: str, state: SessionState = None
        ) -> ToolResult:
            raise ValueError("Unexpected bug in handler!")

        async def _run():
            try:
                await failing_handler(room_name)
            except ValueError:
                pass  # Catch the expected exception

            # If the lock wasn't released, this next block would hang indefinitely.
            # We use wait_for so the test fails fast instead of timing out silently.
            async def _check_lock():
                async with locked_state(room_name) as state:
                    return state.state_version

            return await asyncio.wait_for(_check_lock(), timeout=1.0)

        version = asyncio.run(_run())
        assert version == 0


async def _get_state_helper(room_name: str) -> SessionState:
    async with locked_state(room_name) as state:
        return state


class TestAddIncome:
    def test_add_income_happy_path(self):
        room_name = "test-add-income-happy"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        args = AddIncomeArgs(
            name="Salary", amount_rupees=5000, date="2026-09-20", confidence="confirmed"
        )

        result = asyncio.run(add_income(room_name, args))

        assert result.status == "ok"
        assert "entry_id" in result.data

        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.income) == 1
        assert state.income[0].id == result.data["entry_id"]
        assert state.income[0].current.amount_paise == 500000
        assert state.income[0].current.confidence == "confirmed"
        assert state.state_version == 1

    def test_add_income_date_out_of_range(self):
        room_name = "test-add-income-date"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        # 31 days out
        args = AddIncomeArgs(
            name="Salary", amount_rupees=5000, date="2026-10-16", confidence="confirmed"
        )

        result = asyncio.run(add_income(room_name, args))

        assert result.status == "error"
        assert result.message == "date must be within the next 30 days"

        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.income) == 0
        assert state.state_version == 0


class TestAddExpense:
    def test_add_expense_essential_and_optional(self):
        room_name = "test-add-expense-happy"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        args_essential = AddExpenseArgs(
            category="essential",
            name="Rent",
            amount_rupees=15000,
            date="2026-09-20",
            confidence="confirmed",
        )
        args_optional = AddExpenseArgs(
            category="optional",
            name="Netflix",
            amount_rupees=500,
            date="2026-09-21",
            confidence="estimated",
        )

        res_ess = asyncio.run(add_expense(room_name, args_essential))
        res_opt = asyncio.run(add_expense(room_name, args_optional))

        assert res_ess.status == "ok"
        assert res_opt.status == "ok"

        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.essential_expenses) == 1
        assert len(state.optional_expenses) == 1
        assert state.essential_expenses[0].name == "Rent"
        assert state.optional_expenses[0].name == "Netflix"
        assert state.state_version == 2

    def test_add_expense_date_out_of_range(self):
        room_name = "test-add-expense-date"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        args = AddExpenseArgs(
            category="essential",
            name="Rent",
            amount_rupees=15000,
            date="2025-01-01",
            confidence="confirmed",  # Past date
        )
        result = asyncio.run(add_expense(room_name, args))

        assert result.status == "error"

        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.essential_expenses) == 0


class TestAddDebt:
    def test_add_debt_all_fields_present(self):
        room_name = "test-add-debt-all-fields"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        args = AddDebtArgs(
            name="Home Loan",
            kind="home_loan",
            min_payment_rupees=20000,
            date="2026-09-20",
            confidence="confirmed",
            balance_rupees=1500000,
            interest_rate_percent=8.5,
        )
        result = asyncio.run(add_debt(room_name, args))

        assert result.status == "ok"

        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.debts) == 1
        debt = state.debts[0]
        assert debt.kind == "home_loan"
        assert debt.min_payment_paise == 2000000
        assert debt.balance_paise == 150000000
        assert debt.interest_rate_bps == 850
        assert debt.current.amount_paise == 2000000

    def test_add_debt_optional_fields_absent(self):
        room_name = "test-add-debt-optional"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        args = AddDebtArgs(
            name="Credit Card",
            kind="credit_card",
            min_payment_rupees=5000,
            date="2026-09-20",
            confidence="estimated",
        )
        asyncio.run(add_debt(room_name, args))

        state = asyncio.run(_get_state_helper(room_name))
        assert state.debts[0].balance_paise is None
        assert state.debts[0].interest_rate_bps is None

    def test_add_debt_date_out_of_range(self):
        room_name = "test-add-debt-date"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        args = AddDebtArgs(
            name="Loan",
            kind="personal_loan",
            min_payment_rupees=5000,
            date="2026-10-16",
            confidence="confirmed",
        )
        result = asyncio.run(add_debt(room_name, args))

        assert result.status == "error"
        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.debts) == 0


class TestDuplicateResolutionFlow:
    def test_duplicate_flagging_and_resolution(self):
        room_name = "test-duplicate-flow"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        # 1. Add baseline rent
        args1 = AddExpenseArgs(
            category="essential",
            name="Rent",
            amount_rupees=15000,
            date="2026-09-20",
            confidence="confirmed",
        )
        res1 = asyncio.run(add_expense(room_name, args1))
        assert res1.status == "ok"
        original_id = res1.data["entry_id"]

        # 2. Add "My Rent" (Note: "House Rent" ratio is 0.57 mathematically,
        # so we use "My Rent" to guarantee a 1.0 ratio and trigger the >=0.75 duplicate check)
        args2 = AddExpenseArgs(
            category="essential",
            name="My Rent",
            amount_rupees=18000,
            date="2026-09-20",
            confidence="confirmed",
        )
        res2 = asyncio.run(add_expense(room_name, args2))

        # Verify it was flagged as a warning but still added
        assert res2.status == "warning"
        assert "possible duplicate" in res2.message
        flagged_id = res2.data["entry_id"]

        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.essential_expenses) == 2
        assert state.essential_expenses[1].possible_duplicate is True
        assert state.essential_expenses[1].duplicate_of == original_id

        # 3. Resolve by merging (is_same_as_existing=True)
        resolve_args = ResolveDuplicateArgs(
            entry_id=flagged_id, is_same_as_existing=True, existing_entry_id=original_id
        )
        res3 = asyncio.run(resolve_duplicate(room_name, resolve_args))
        assert res3.status == "ok"

        # Verify lists merged correctly (flagged entry removed, original updated)
        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.essential_expenses) == 1
        assert state.essential_expenses[0].id == original_id
        assert (
            state.essential_expenses[0].current.amount_paise == 1800000
        )  # Updated to newer amount
        assert (
            len(state.essential_expenses[0].history) == 1
        )  # Original amount pushed to history

    def test_duplicate_kept_separate(self):
        room_name = "test-duplicate-separate"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        # 1. Add baseline income
        args1 = AddIncomeArgs(
            name="Freelance",
            amount_rupees=5000,
            date="2026-09-20",
            confidence="confirmed",
        )
        asyncio.run(add_income(room_name, args1))

        # 2. Add second similar income
        args2 = AddIncomeArgs(
            name="My Freelance",
            amount_rupees=3000,
            date="2026-09-25",
            confidence="confirmed",
        )
        res2 = asyncio.run(add_income(room_name, args2))
        flagged_id = res2.data["entry_id"]

        # 3. Resolve by keeping separate (is_same_as_existing=False)
        resolve_args = ResolveDuplicateArgs(
            entry_id=flagged_id, is_same_as_existing=False
        )
        asyncio.run(resolve_duplicate(room_name, resolve_args))

        # Verify both exist and flags are cleared
        state = asyncio.run(_get_state_helper(room_name))
        assert len(state.income) == 2
        assert state.income[1].possible_duplicate is False
        assert state.income[1].duplicate_of is None


class TestUpdateEntryConflictDetection:
    def test_update_below_threshold_auto_applies(self):
        room_name = "test-update-below-thresh"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        # Baseline: 10,000 rupees (1,000,000 paise)
        args1 = AddIncomeArgs(
            name="Salary",
            amount_rupees=10000,
            date="2026-09-20",
            confidence="confirmed",
        )
        res1 = asyncio.run(add_income(room_name, args1))
        entry_id = res1.data["entry_id"]

        # Update to 11,000 rupees (1,100,000 paise) - 10% delta
        args2 = UpdateEntryArgs(
            entry_id=entry_id, new_amount_rupees=11000, confidence="confirmed"
        )
        res2 = asyncio.run(update_entry(room_name, args2))
        assert res2.status == "ok"

        state = asyncio.run(_get_state_helper(room_name))
        entry = state.income[0]
        assert entry.current.amount_paise == 1100000
        assert len(entry.history) == 1
        assert entry.history[0].amount_paise == 1000000
        assert len(state.conflicts) == 0

    def test_update_above_threshold_triggers_conflict(self):
        room_name = "test-update-above-thresh"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        # Baseline: 10,000 rupees (1,000,000 paise)
        args1 = AddIncomeArgs(
            name="Salary",
            amount_rupees=10000,
            date="2026-09-20",
            confidence="confirmed",
        )
        res1 = asyncio.run(add_income(room_name, args1))
        entry_id = res1.data["entry_id"]

        # Update to 12,000 rupees (1,200,000 paise) - 20% delta
        args2 = UpdateEntryArgs(
            entry_id=entry_id, new_amount_rupees=12000, confidence="confirmed"
        )
        res2 = asyncio.run(update_entry(room_name, args2))
        assert res2.status == "warning"
        assert "conflict_id" in res2.data

        state = asyncio.run(_get_state_helper(room_name))
        entry = state.income[0]

        # Current amount MUST remain unchanged because conflict was triggered
        assert entry.current.amount_paise == 1000000
        assert len(entry.history) == 0
        assert len(state.conflicts) == 1
        assert state.conflicts[0].new_amount_paise == 1200000

    def test_update_estimated_bypasses_threshold(self):
        room_name = "test-update-estimated"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        # Baseline: 10,000 rupees (ESTIMATED)
        args1 = AddIncomeArgs(
            name="Salary",
            amount_rupees=10000,
            date="2026-09-20",
            confidence="estimated",
        )
        res1 = asyncio.run(add_income(room_name, args1))
        entry_id = res1.data["entry_id"]

        # Update to 15,000 rupees (1,500,000 paise) - 50% delta
        args2 = UpdateEntryArgs(
            entry_id=entry_id, new_amount_rupees=15000, confidence="confirmed"
        )
        res2 = asyncio.run(update_entry(room_name, args2))
        assert res2.status == "ok"

        state = asyncio.run(_get_state_helper(room_name))
        assert state.income[0].current.amount_paise == 1500000

    def test_update_exact_15_percent_delta_auto_applies(self):
        room_name = "test-update-exact-thresh"
        today = date(2026, 9, 14)
        get_or_create(room_name, today)

        # Baseline: 10,000 rupees (1,000,000 paise)
        args1 = AddIncomeArgs(
            name="Salary",
            amount_rupees=10000,
            date="2026-09-20",
            confidence="confirmed",
        )
        res1 = asyncio.run(add_income(room_name, args1))
        entry_id = res1.data["entry_id"]

        # Update to 11,500 rupees (1,150,000 paise) - EXACTLY 15%
        args2 = UpdateEntryArgs(
            entry_id=entry_id, new_amount_rupees=11500, confidence="confirmed"
        )
        res2 = asyncio.run(update_entry(room_name, args2))
        assert res2.status == "ok"  # Verified > logic, not >=

        state = asyncio.run(_get_state_helper(room_name))
        assert state.income[0].current.amount_paise == 1150000
