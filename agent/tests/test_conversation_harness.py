"""Conversation harness test suite simulating multi-turn user state mutations.

Tests:
- Plain happy path (adding income, essential expense, debt)
- Mid-conversation correction (updating an entry)
- Duplicate detection & resolution flow
- Conflicting restatement (>15% delta) & conflict resolution flow
"""

import asyncio
from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.session_store import get_or_create
from app.tools import (
    add_debt,
    add_expense,
    add_income,
    resolve_conflict,
    resolve_duplicate,
    update_entry,
)
from app.validation import (
    AddDebtArgs,
    AddExpenseArgs,
    AddIncomeArgs,
    ResolveConflictArgs,
    ResolveDuplicateArgs,
    UpdateEntryArgs,
)


def test_conversation_harness_happy_path():
    room_name = "harness-happy-path-room"
    today = date(2026, 9, 14)
    session = get_or_create(room_name, today)

    # Turn 1: Add income
    result1 = asyncio.run(
        add_income(
            room_name,
            AddIncomeArgs(
                name="Primary Salary",
                amount_rupees=50000.0,
                date="2026-09-20",
                confidence="confirmed",
            ),
        )
    )
    assert result1.status == "ok"
    assert len(session.state.income) == 1
    assert session.state.income[0].current.amount_paise == 5000000

    # Turn 2: Add essential expense
    result2 = asyncio.run(
        add_expense(
            room_name,
            AddExpenseArgs(
                name="House Rent",
                amount_rupees=15000.0,
                category="essential",
                date="2026-09-21",
                confidence="confirmed",
            ),
        )
    )
    assert result2.status == "ok"
    assert len(session.state.essential_expenses) == 1

    # Turn 3: Add debt
    result3 = asyncio.run(
        add_debt(
            room_name,
            AddDebtArgs(
                name="HDFC Credit Card",
                min_payment_rupees=3000.0,
                date="2026-09-14",
                due_date="2026-09-25",
                kind="credit_card",
                confidence="confirmed",
            ),
        )
    )
    assert result3.status == "ok"
    assert len(session.state.debts) == 1


def test_conversation_harness_mid_conversation_correction():
    room_name = "harness-correction-room"
    today = date(2026, 9, 14)
    session = get_or_create(room_name, today)

    # Turn 1: Initial income
    result1 = asyncio.run(
        add_income(
            room_name,
            AddIncomeArgs(
                name="Freelance",
                amount_rupees=20000.0,
                date="2026-09-20",
                confidence="estimated",
            ),
        )
    )
    entry_id = result1.data["entry_id"]

    # Turn 2: User corrects estimated income to confirmed 22,000 (10% change, estimated bypasses threshold)
    result2 = asyncio.run(
        update_entry(
            room_name,
            UpdateEntryArgs(
                entry_id=entry_id,
                new_amount_rupees=22000.0,
                confidence="confirmed",
            ),
        )
    )
    assert result2.status == "ok"
    assert session.state.income[0].current.amount_paise == 2200000
    assert session.state.income[0].current.confidence == "confirmed"
    assert len(session.state.income[0].history) == 1


def test_conversation_harness_conflicting_restatement():
    room_name = "harness-conflict-room"
    today = date(2026, 9, 14)
    session = get_or_create(room_name, today)

    # Turn 1: Confirmed income ₹50,000
    result1 = asyncio.run(
        add_income(
            room_name,
            AddIncomeArgs(
                name="Salary",
                amount_rupees=50000.0,
                date="2026-09-20",
                confidence="confirmed",
            ),
        )
    )
    entry_id = result1.data["entry_id"]

    # Turn 2: Restatement to ₹70,000 (40% increase > 15% threshold) triggers conflict
    result2 = asyncio.run(
        update_entry(
            room_name,
            UpdateEntryArgs(
                entry_id=entry_id,
                new_amount_rupees=70000.0,
                confidence="confirmed",
            ),
        )
    )
    assert result2.status == "warning"
    assert len(session.state.conflicts) == 1
    conflict_id = session.state.conflicts[0].id

    # Turn 3: User resolves conflict in favor of new value
    result3 = asyncio.run(
        resolve_conflict(
            room_name,
            ResolveConflictArgs(
                conflict_id=conflict_id,
                chosen_amount_rupees=70000.0,
            ),
        )
    )
    assert result3.status == "ok"
    assert session.state.conflicts[0].resolved is True
    assert session.state.income[0].current.amount_paise == 7000000


def test_conversation_harness_duplicate_detection():
    room_name = "harness-duplicate-room"
    today = date(2026, 9, 14)
    session = get_or_create(room_name, today)

    # Turn 1: Add rent ₹15,000
    res1 = asyncio.run(
        add_expense(
            room_name,
            AddExpenseArgs(
                name="Apartment Rent",
                amount_rupees=15000.0,
                category="essential",
                date="2026-09-20",
                confidence="confirmed",
            ),
        )
    )
    first_id = res1.data["entry_id"]

    # Turn 2: User says "Apartment Rent ₹15,000" again (same name & amount)
    result2 = asyncio.run(
        add_expense(
            room_name,
            AddExpenseArgs(
                name="Apartment Rent",
                amount_rupees=15000.0,
                category="essential",
                date="2026-09-20",
                confidence="confirmed",
            ),
        )
    )
    assert result2.status == "warning"
    dup_id = result2.data["entry_id"]

    # Turn 3: Resolve duplicate as duplicate (drops the second entry)
    result3 = asyncio.run(
        resolve_duplicate(
            room_name,
            ResolveDuplicateArgs(
                entry_id=dup_id,
                is_same_as_existing=True,
                existing_entry_id=first_id,
            ),
        )
    )
    assert result3.status == "ok"
    assert len(session.state.essential_expenses) == 1
