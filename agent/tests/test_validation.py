"""Unit tests for agent/app/validation.py."""

import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

# Ensure agent module is accessible when pytest is run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.validation import (
    AddDebtArgs,
    AddExpenseArgs,
    AddIncomeArgs,
    ResolveConflictArgs,
    ResolveDuplicateArgs,
    UpdateEntryArgs,
)


class TestValidationConstraints:
    def test_rupees_conversion_and_positive_constraint(self):
        # Valid case: Converts 15000.50 rupees (float) to 1500050 paise
        args_float = AddIncomeArgs(
            name="Salary",
            amount_rupees=15000.50,
            date="2026-09-13",
            confidence="confirmed",
        )
        assert args_float.amount_paise == 1500050

        # Valid case: LLM JSON outputs `15000` (int), coerced to float internally
        args_int = AddIncomeArgs(
            name="Salary",
            amount_rupees=15000,
            date="2026-09-13",
            confidence="confirmed",
        )
        assert args_int.amount_paise == 1500000

        # Invalid case: Zero
        with pytest.raises(ValidationError) as exc:
            AddIncomeArgs(
                name="Salary",
                amount_rupees=0,
                date="2026-09-13",
                confidence="confirmed",
            )
        assert "amount must be greater than zero" in str(exc.value)

        # Invalid case: Negative
        with pytest.raises(ValidationError) as exc:
            AddIncomeArgs(
                name="Salary",
                amount_rupees=-500,
                date="2026-09-13",
                confidence="confirmed",
            )
        assert "amount must be greater than zero" in str(exc.value)

    def test_date_iso_parsing(self):
        # Valid case: standard ISO format
        args = AddExpenseArgs(
            category="essential",
            name="Rent",
            amount_rupees=15000,
            date="2026-10-01",
            confidence="confirmed",
        )
        assert args.date == date(2026, 10, 1)

        # Invalid case: DD-MM-YYYY
        with pytest.raises(ValidationError) as exc:
            AddExpenseArgs(
                category="essential",
                name="Rent",
                amount_rupees=15000,
                date="01-10-2026",
                confidence="confirmed",
            )
        assert "date" in str(exc.value).lower()

    def test_confidence_literal(self):
        # Invalid case (Valid case handled in previous tests)
        with pytest.raises(ValidationError) as exc:
            AddIncomeArgs(
                name="Salary",
                amount_rupees=15000,
                date="2026-09-13",
                confidence="guessed",
            )
        assert "Input should be 'confirmed' or 'estimated'" in str(exc.value)

    def test_debt_kind_literal(self):
        # Valid case (Ensuring compliance with the 9 specific DebtKind values)
        args = AddDebtArgs(
            name="Home",
            kind="home_loan",
            min_payment_rupees=5000,
            date="2026-09-13",
            confidence="confirmed",
        )
        assert args.kind == "home_loan"

        # Invalid case
        with pytest.raises(ValidationError) as exc:
            AddDebtArgs(
                name="Home",
                kind="not_a_loan",
                min_payment_rupees=5000,
                date="2026-09-13",
                confidence="confirmed",
            )
        assert "Input should be" in str(exc.value)

    def test_interest_rate_bounds(self):
        # Valid case: 12.5% converts to 1250 bps
        args = AddDebtArgs(
            name="Card",
            kind="credit_card",
            min_payment_rupees=5000,
            date="2026-09-13",
            confidence="confirmed",
            interest_rate_percent=12.5,
        )
        assert args.interest_rate_bps == 1250

        # Invalid case: > 100
        with pytest.raises(ValidationError) as exc:
            AddDebtArgs(
                name="Card",
                kind="credit_card",
                min_payment_rupees=5000,
                date="2026-09-13",
                confidence="confirmed",
                interest_rate_percent=150,
            )
        assert "interest rate must be between 0 and 100" in str(exc.value)

        # Invalid case: < 0
        with pytest.raises(ValidationError) as exc:
            AddDebtArgs(
                name="Card",
                kind="credit_card",
                min_payment_rupees=5000,
                date="2026-09-13",
                confidence="confirmed",
                interest_rate_percent=-5,
            )
        assert "interest rate must be between 0 and 100" in str(exc.value)

    def test_id_regex_pattern(self):
        # Valid case: entry pattern
        args = UpdateEntryArgs(
            entry_id="entry_a1b2c3d4", new_amount_rupees=5000, confidence="confirmed"
        )
        assert args.entry_id == "entry_a1b2c3d4"

        # Valid case: conflict pattern
        args_conflict = ResolveConflictArgs(
            conflict_id="conflict_1234abcd", chosen_amount_rupees=5000
        )
        assert args_conflict.conflict_id == "conflict_1234abcd"

        # Invalid case: bad prefix
        with pytest.raises(ValidationError) as exc:
            UpdateEntryArgs(
                entry_id="item_a1b2c3d4", new_amount_rupees=5000, confidence="confirmed"
            )
        assert "String should match pattern" in str(exc.value)

        # Invalid case: hex string too short
        with pytest.raises(ValidationError) as exc:
            ResolveConflictArgs(conflict_id="conflict_abc", chosen_amount_rupees=5000)
        assert "String should match pattern" in str(exc.value)

    def test_resolve_duplicate_conditional_logic(self):
        # Valid case: false, no existing id
        args = ResolveDuplicateArgs(
            entry_id="entry_a1b2c3d4", is_same_as_existing=False
        )
        assert args.is_same_as_existing is False

        # Valid case: true, has existing id
        args = ResolveDuplicateArgs(
            entry_id="entry_a1b2c3d4",
            is_same_as_existing=True,
            existing_entry_id="entry_99999999",
        )
        assert args.existing_entry_id == "entry_99999999"

        # Invalid case: true, missing existing id
        with pytest.raises(ValidationError) as exc:
            ResolveDuplicateArgs(entry_id="entry_a1b2c3d4", is_same_as_existing=True)
        assert "existing_entry_id is required" in str(exc.value)

    def test_add_debt_other_requires_label(self):
        # Invalid: 'other' missing kind_label
        with pytest.raises(ValidationError) as exc:
            AddDebtArgs(
                name="Friend",
                kind="other",
                min_payment_rupees=5000,
                date="2026-09-13",
                confidence="confirmed",
            )
        assert "kind_label is required when kind is 'other'" in str(exc.value)

        # Valid: 'other' with kind_label
        args = AddDebtArgs(
            name="Friend",
            kind="other",
            kind_label="Owe Rahul",
            min_payment_rupees=5000,
            date="2026-09-13",
            confidence="confirmed",
        )
        assert args.kind_label == "Owe Rahul"

    def test_update_entry_validation_matrix(self):
        # Valid: Update just amount (requires confidence)
        args1 = UpdateEntryArgs(
            entry_id="entry_12345678", new_amount_rupees=5000, confidence="confirmed"
        )
        assert args1.new_amount_paise == 500000

        # Valid: Update just balance (no confidence needed)
        args2 = UpdateEntryArgs(entry_id="entry_12345678", new_balance_rupees=10000)
        assert args2.new_balance_paise == 1000000

        # Invalid: Amount without confidence
        with pytest.raises(ValidationError) as exc:
            UpdateEntryArgs(entry_id="entry_12345678", new_amount_rupees=5000)
        assert "confidence is required when updating the amount" in str(exc.value)

        # Invalid: No update fields provided
        with pytest.raises(ValidationError) as exc:
            UpdateEntryArgs(entry_id="entry_12345678")
        assert "At least one field to update must be provided" in str(exc.value)
