"""Deterministic finance engine module.

Contains pure functions for state calculations, financial position evaluation,
missing field checks, blocking issue calculations, and 30-day plan simulation.
Zero imports from Pipecat, FastAPI, or LLM SDKs.
"""

from datetime import date, timedelta
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

try:
    from agent.app.state import (
        Entry,
        SessionState,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )
except ImportError:  # pragma: no cover
    from app.state import (
        Entry,
        SessionState,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )


class MissedObligation(BaseModel):
    """Details of a single financial obligation that could not be met."""

    model_config = ConfigDict(extra="forbid")

    entry_id: str
    name: str
    due_date: date
    required_paise: int
    available_paise: int
    shortfall_paise: int


class LedgerEntry(BaseModel):
    """Single entry in the daily simulation ledger balance log."""

    model_config = ConfigDict(extra="forbid")

    day_offset: int
    balance_paise: int


class PlanResult(BaseModel):
    """The output of the 30-day cash flow simulation engine."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["surplus", "solved_with_cuts", "unsolvable"]
    final_balance_paise: int
    cuts: list[Entry] = Field(default_factory=list)
    missed_obligations: list[MissedObligation] = Field(default_factory=list)
    ledger: list[LedgerEntry] = Field(default_factory=list)


def resolve_entry_date(entry: Any, today: date) -> date:
    """Resolve the concrete date within the 30-day window [today, today + 29 days] for an Entry or Debt."""
    if hasattr(entry, "due_date") and getattr(entry, "due_date") is not None:
        return getattr(entry, "due_date")

    recurrence = getattr(entry, "recurrence", None)
    if recurrence and hasattr(recurrence, "day_of_month") and recurrence.day_of_month:
        day = recurrence.day_of_month
        try:
            candidate = date(today.year, today.month, day)
        except ValueError:
            candidate = date(today.year, today.month + 1, 1) - timedelta(days=1)

        if candidate >= today:
            return candidate

        year = today.year + (1 if today.month == 12 else 0)
        month = 1 if today.month == 12 else today.month + 1
        try:
            return date(year, month, day)
        except ValueError:
            next_month = date(
                year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1
            )
            return next_month - timedelta(days=1)

    return today


def _simulate(
    income: list[Entry],
    essential_expenses: list[Entry],
    debts: list[Any],
    today: date,
    optional_expenses: list[Entry] | None = None,
):
    balance = 0
    missed: list[MissedObligation] = []
    events: list[tuple[int, int, int | None, Any, date]] = []

    for e in income:
        e_date = resolve_entry_date(e, today)
        day_off = (e_date - today).days
        events.append((day_off, 0, None, e, e_date))

    for e in essential_expenses:
        e_date = resolve_entry_date(e, today)
        day_off = (e_date - today).days
        events.append((day_off, 1, -e.current.amount_paise, e, e_date))

    for d in debts:
        d_date = resolve_entry_date(d, today)
        day_off = (d_date - today).days
        kind = getattr(d, "kind", None)
        rank = 3 if kind == "credit_card" else 2
        amt = getattr(d, "min_payment_paise", d.current.amount_paise)
        events.append((day_off, rank, -amt, d, d_date))

    if optional_expenses:
        for e in optional_expenses:
            e_date = resolve_entry_date(e, today)
            day_off = (e_date - today).days
            events.append((day_off, 4, -e.current.amount_paise, e, e_date))

    # sort by day, then by priority_rank ascending, then by amount descending (via the negative), then by entry id ascending for full determinism
    events.sort(
        key=lambda ev: (ev[0], ev[1], ev[2] if ev[2] is not None else 0, ev[3].id)
    )

    ledger: list[LedgerEntry] = []
    for day_offset_val, priority_rank, _, entry, entry_date in events:
        if priority_rank == 0:  # income: always applied
            balance += entry.current.amount_paise
        else:  # an obligation: pay in full only if funds suffice
            req = (
                getattr(entry, "min_payment_paise", None) or entry.current.amount_paise
            )
            if balance >= req:
                balance -= req
            else:
                missed.append(
                    MissedObligation(
                        entry_id=entry.id,
                        name=entry.name,
                        due_date=entry_date,
                        required_paise=req,
                        available_paise=balance,
                        shortfall_paise=req - balance,
                    )
                )
        ledger.append(LedgerEntry(day_offset=day_offset_val, balance_paise=balance))
    return balance, missed, ledger


def _find_cuts(
    state: SessionState,
    initial_missed: list[MissedObligation],
    initial_balance: int,
    initial_ledger: list[LedgerEntry],
) -> tuple[list[Entry], list[MissedObligation], int, list[LedgerEntry]]:
    """Search for optional expense cuts using a greedy heuristic (largest amount cut first).

    Trade-off & Optimality:
    Sorts optional expenses by `amount_paise` descending and greedily cuts the largest optional
    expenses first until all obligations are met or all optional expenses are cut. This is a
    deliberate, simple greedy heuristic and does NOT guarantee finding the minimum number of cuts
    (an optimal subset-sum / 0-1 knapsack search is out of scope for this timeline).
    """
    sorted_optionals = sorted(
        state.optional_expenses,
        key=lambda e: (-e.current.amount_paise, e.id),
    )

    cuts: list[Entry] = []
    last_balance = initial_balance
    last_missed = initial_missed
    last_ledger = initial_ledger

    for expense in sorted_optionals:
        cuts.append(expense)
        remaining_optionals = [e for e in sorted_optionals if e not in cuts]
        balance, missed, ledger = _simulate(
            state.income,
            state.essential_expenses,
            state.debts,
            state.today,
            optional_expenses=remaining_optionals,
        )
        last_balance = balance
        last_missed = missed
        last_ledger = ledger
        if not missed:
            return cuts, [], balance, ledger

    return cuts, last_missed, last_balance, last_ledger


def build_plan(state: SessionState) -> PlanResult:
    """Build a 30-day cash flow plan from SessionState.

    Simulates day-by-day cash flows over 30 days starting from `state.today`.
    """
    balance, missed, ledger = _simulate(
        state.income,
        state.essential_expenses,
        state.debts,
        state.today,
        optional_expenses=state.optional_expenses,
    )

    if not missed:
        return PlanResult(
            status="surplus",
            final_balance_paise=balance,
            cuts=[],
            missed_obligations=[],
            ledger=ledger,
        )

    cuts, missed, final_balance, final_ledger = _find_cuts(
        state, missed, balance, ledger
    )
    status: Literal["surplus", "solved_with_cuts", "unsolvable"] = (
        "solved_with_cuts" if not missed else "unsolvable"
    )
    return PlanResult(
        status=status,
        final_balance_paise=final_balance,
        cuts=cuts,
        missed_obligations=missed,
        ledger=final_ledger,
    )


__all__ = [
    "SessionState",
    "MissedObligation",
    "LedgerEntry",
    "PlanResult",
    "build_plan",
    "compute_cash_position",
    "compute_missing_fields",
    "compute_blocking_issues",
]
