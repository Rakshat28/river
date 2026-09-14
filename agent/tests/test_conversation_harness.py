"""Lightweight Evaluation Harness (Track B) test suite.

Simulates multi-turn conversations directly against the LLM + Tools execution layer
bypassing WebRTC/STT/TTS transport for deterministic, audit-verifiable testing.

Golden Transcripts:
1. Happy-path intake flow
2. Mid-conversation correction flow
3. Ambiguous reference / coreference flow
4. Conflicting restatement (>15% delta) flow
5. Malformed input / validation error flow
"""

import asyncio
from datetime import date
import sys
from pathlib import Path
from typing import Any, Callable
from pydantic import BaseModel, ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.session_store import get_or_create
from app.state import SessionState
from app.tools import (
    ToolResult,
    add_debt,
    add_expense,
    add_income,
    confirm_user_understood,
    finalize_plan,
    remove_entry,
    resolve_conflict,
    resolve_duplicate,
    update_entry,
)
from app.validation import (
    AddDebtArgs,
    AddExpenseArgs,
    AddIncomeArgs,
    ConfirmUserUnderstoodArgs,
    FinalizePlanArgs,
    RemoveEntryArgs,
    ResolveConflictArgs,
    ResolveDuplicateArgs,
    UpdateEntryArgs,
)

TOOL_MAP: dict[str, tuple[type[BaseModel], Callable[..., Any]]] = {
    "add_income": (AddIncomeArgs, add_income),
    "add_expense": (AddExpenseArgs, add_expense),
    "add_debt": (AddDebtArgs, add_debt),
    "update_entry": (UpdateEntryArgs, update_entry),
    "remove_entry": (RemoveEntryArgs, remove_entry),
    "resolve_duplicate": (ResolveDuplicateArgs, resolve_duplicate),
    "resolve_conflict": (ResolveConflictArgs, resolve_conflict),
    "finalize_plan": (FinalizePlanArgs, finalize_plan),
    "confirm_user_understood": (ConfirmUserUnderstoodArgs, confirm_user_understood),
}


async def run_harness_turn(
    room_name: str, tool_name: str, args_dict: dict
) -> ToolResult:
    """Run a single scripted tool turn directly against the room's SessionState, catching validation errors."""
    pydantic_cls, handler_func = TOOL_MAP[tool_name]
    try:
        validated = pydantic_cls(**args_dict)
        return await handler_func(room_name, validated)
    except ValidationError as ve:
        return ToolResult.error(f"Invalid tool arguments: {ve}")


def run_harness_conversation(
    room_name: str,
    turns: list[tuple[str, dict]],
    today: date = date(2026, 9, 14),
) -> tuple[SessionState, list[ToolResult]]:
    """Run a sequence of scripted turns through the evaluation harness."""
    session = get_or_create(room_name, today)
    results = []
    for tool_name, args_dict in turns:
        res = asyncio.run(run_harness_turn(room_name, tool_name, args_dict))
        results.append(res)
    return session.state, results


def test_golden_happy_path_intake():
    """Golden Transcript 1: Plain happy-path intake flow."""
    turns = [
        (
            "add_income",
            {
                "name": "Primary Salary",
                "amount_rupees": 50000.0,
                "date": "2026-09-14",
                "confidence": "confirmed",
            },
        ),
        (
            "add_expense",
            {
                "name": "House Rent",
                "amount_rupees": 15000.0,
                "category": "essential",
                "date": "2026-09-18",
                "confidence": "confirmed",
            },
        ),
        (
            "add_debt",
            {
                "name": "Vehicle Loan",
                "min_payment_rupees": 5000.0,
                "date": "2026-09-14",
                "due_date": "2026-09-20",
                "kind": "vehicle_loan",
                "confidence": "confirmed",
            },
        ),
        ("finalize_plan", {}),
    ]

    state, results = run_harness_conversation("golden-happy-path", turns)

    assert results[0].status == "ok"
    assert results[1].status == "ok"
    assert results[2].status == "ok"
    assert results[3].status == "ok"

    assert len(state.income) == 1
    assert len(state.essential_expenses) == 1
    assert len(state.debts) == 1
    assert state.plan is not None
    assert state.plan.status == "surplus"
    assert state.plan.final_balance_paise == 3000000


def test_golden_mid_conversation_correction():
    """Golden Transcript 2: Mid-conversation correction flow."""
    turns_t1 = [
        (
            "add_income",
            {
                "name": "Freelance Gig",
                "amount_rupees": 20000.0,
                "date": "2026-09-20",
                "confidence": "estimated",
            },
        ),
    ]
    state, results_t1 = run_harness_conversation("golden-correction", turns_t1)
    entry_id = results_t1[0].data["entry_id"]

    # Turn 2: User corrects estimated income to confirmed ₹25,000
    turns_t2 = [
        (
            "update_entry",
            {
                "entry_id": entry_id,
                "new_amount_rupees": 25000.0,
                "confidence": "confirmed",
            },
        ),
    ]
    state, results_t2 = run_harness_conversation("golden-correction", turns_t2)

    assert results_t2[0].status == "ok"
    assert state.income[0].current.amount_paise == 2500000
    assert state.income[0].current.confidence == "confirmed"
    assert len(state.income[0].history) == 1
    assert state.income[0].history[0].amount_paise == 2000000


def test_golden_ambiguous_reference_coreference():
    """Golden Transcript 3: Ambiguous reference coreference flow ('the other loan')."""
    turns_t1 = [
        (
            "add_debt",
            {
                "name": "Car Loan",
                "min_payment_rupees": 4000.0,
                "date": "2026-09-14",
                "due_date": "2026-09-20",
                "kind": "vehicle_loan",
                "confidence": "confirmed",
            },
        ),
        (
            "add_debt",
            {
                "name": "Personal Loan",
                "min_payment_rupees": 6000.0,
                "date": "2026-09-14",
                "due_date": "2026-09-22",
                "kind": "personal_loan",
                "confidence": "confirmed",
            },
        ),
    ]
    state, results_t1 = run_harness_conversation("golden-ambiguous-ref", turns_t1)
    _ = results_t1[0].data["entry_id"]
    personal_loan_id = results_t1[1].data["entry_id"]

    # User says: "Actually, update the other loan (Personal Loan) to ₹6,500" (8.33% increase < 15% conflict threshold)
    turns_t2 = [
        (
            "update_entry",
            {
                "entry_id": personal_loan_id,
                "new_amount_rupees": 6500.0,
                "confidence": "confirmed",
            },
        ),
    ]
    state, results_t2 = run_harness_conversation("golden-ambiguous-ref", turns_t2)

    assert results_t2[0].status == "ok"
    # Personal loan updated to 6,500
    assert state.debts[1].current.amount_paise == 650000
    # Car loan remains unchanged at 4,000
    assert state.debts[0].current.amount_paise == 400000


def test_golden_conflicting_restatement_flow():
    """Golden Transcript 4: Conflicting restatement (>15% delta) flow."""
    turns_t1 = [
        (
            "add_income",
            {
                "name": "Salary",
                "amount_rupees": 50000.0,
                "date": "2026-09-14",
                "confidence": "confirmed",
            },
        ),
    ]
    state, results_t1 = run_harness_conversation("golden-conflict", turns_t1)
    entry_id = results_t1[0].data["entry_id"]

    # Turn 2: User restates salary to ₹80,000 (60% increase > 15% threshold)
    turns_t2 = [
        (
            "update_entry",
            {
                "entry_id": entry_id,
                "new_amount_rupees": 80000.0,
                "confidence": "confirmed",
            },
        ),
    ]
    state, results_t2 = run_harness_conversation("golden-conflict", turns_t2)

    assert results_t2[0].status == "warning"
    assert len(state.conflicts) == 1
    conflict_id = state.conflicts[0].id

    # Turn 3: User resolves conflict in favor of ₹80,000
    turns_t3 = [
        (
            "resolve_conflict",
            {
                "conflict_id": conflict_id,
                "chosen_amount_rupees": 80000.0,
            },
        ),
    ]
    state, results_t3 = run_harness_conversation("golden-conflict", turns_t3)

    assert results_t3[0].status == "ok"
    assert state.conflicts[0].resolved is True
    assert state.income[0].current.amount_paise == 8000000


def test_golden_malformed_input_validation_error_path():
    """Golden Transcript 5: Malformed/nonsensical input validation error path."""
    turns = [
        (
            "add_income",
            {
                "name": "Salary",
                "amount_rupees": -5000.0,  # Invalid negative amount
                "date": "2026-09-14",
                "confidence": "confirmed",
            },
        ),
    ]

    state, results = run_harness_conversation("golden-malformed", turns)

    assert results[0].status == "error"
    assert "Invalid tool arguments" in results[0].message
    assert len(state.income) == 0  # SessionState left clean and uncorrupted
