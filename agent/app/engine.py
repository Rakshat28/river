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
        Debt,
        SessionState,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )
except ImportError:  # pragma: no cover
    from app.state import (
        Entry,
        Debt,
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


def calculate_emi_paise(
    balance_paise: int,
    annual_rate_bps: int,
    duration_months: int,
) -> int:
    """Compute the standard reducing-balance EMI in paise.

    Uses the formula: EMI = P × r × (1+r)^n / ((1+r)^n - 1)
    where P = principal in paise, r = monthly rate (decimal), n = tenure in months.

    Edge cases:
    - If annual_rate_bps == 0 (zero-interest loan), EMI = P / n.
    - Duration must be >= 1 month.

    This is the canonical source for EMI computation in this project.
    No other module may implement its own EMI formula.
    """
    if duration_months <= 0:
        raise ValueError("duration_months must be >= 1")
    if balance_paise <= 0:
        raise ValueError("balance_paise must be > 0")

    if annual_rate_bps == 0:
        # Zero-interest loan: simple division
        return round(balance_paise / duration_months)

    monthly_rate = annual_rate_bps / (12 * 10_000)  # bps → decimal monthly rate
    factor = (1 + monthly_rate) ** duration_months
    emi = balance_paise * monthly_rate * factor / (factor - 1)
    return round(emi)


class PlanResult(BaseModel):
    """The output of the 30-day cash flow simulation engine."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["surplus", "solved_with_cuts", "unsolvable"]
    final_balance_paise: int
    cuts: list[Entry] = Field(default_factory=list)
    missed_obligations: list[MissedObligation] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    income: list[Entry] = Field(default_factory=list)
    essential_expenses: list[Entry] = Field(default_factory=list)
    optional_expenses: list[Entry] = Field(default_factory=list)
    debts: list[Debt] = Field(default_factory=list)
    disclaimer: str = Field(
        default="Please note: This assistant is an AI tool, not a SEBI-registered or government-certified financial advisor. These insights are mathematical projections, not professional financial advice."
    )


def _generate_insights(
    state: SessionState,
    status: Literal["surplus", "solved_with_cuts", "unsolvable"],
    final_balance_paise: int,
    cuts: list[Entry],
    missed_obligations: list[MissedObligation],
) -> list[str]:
    """Generate rich, quantified financial insights from the plan result.

    Every insight references real numbers from the user's state so the
    advisor output is specific to their situation, not generic advice.
    See implementation-plan.md §8.5 for the design rationale.
    """
    insights: list[str] = []

    total_income_paise = sum(e.current.amount_paise for e in state.income)
    total_essential_paise = sum(e.current.amount_paise for e in state.essential_expenses)
    total_optional_paise = sum(e.current.amount_paise for e in state.optional_expenses)
    total_debt_min_paise = sum(d.min_payment_paise for d in state.debts)
    total_obligations_paise = total_essential_paise + total_optional_paise + total_debt_min_paise

    def fmt(paise: int) -> str:
        """Format paise as a human-readable ₹ string."""
        rupees = abs(paise) // 100
        if rupees >= 100_000:
            return f"₹{rupees / 100_000:.1f}L"
        if rupees >= 1_000:
            return f"₹{rupees:,}"
        return f"₹{rupees}"

    # 1. Income vs. Obligations overview (always shown)
    insights.append(
        f"Your total monthly income is {fmt(total_income_paise)} against total obligations of "
        f"{fmt(total_obligations_paise)} "
        f"(essentials: {fmt(total_essential_paise)}, "
        f"optional: {fmt(total_optional_paise)}, "
        f"loan EMIs: {fmt(total_debt_min_paise)})."
    )

    # 2. Surplus / shortfall summary
    if status == "surplus":
        insights.append(
            f"After all payments, you are projected to have a surplus of {fmt(final_balance_paise)} at the end of 30 days. "
            f"Ensure you have an emergency fund covering 3–6 months of essential expenses "
            f"({fmt(total_essential_paise * 3)}–{fmt(total_essential_paise * 6)}) before directing this surplus elsewhere."
        )
    elif status == "solved_with_cuts":
        savings_from_cuts = sum(c.current.amount_paise for c in cuts)
        insights.append(
            f"You had a shortfall that was resolved by proposing cuts to {len(cuts)} optional "
            f"expense(s) totalling {fmt(savings_from_cuts)}. Your projected final balance after these cuts is {fmt(final_balance_paise)}."
        )
    elif status == "unsolvable":
        total_shortfall = sum(m.shortfall_paise for m in missed_obligations)
        insights.append(
            f"Your monthly deficit is {fmt(total_shortfall)}. Even after removing all optional expenses "
            f"({fmt(total_optional_paise)}), essential obligations still cannot be fully met. "
            f"Contact your lenders to request a loan restructuring or tenure extension to reduce your {fmt(total_debt_min_paise)} monthly debt burden."
        )

    # 3. EMI-to-income ratio warning (>40% is a standard red-flag threshold)
    if total_income_paise > 0:
        emi_ratio = total_debt_min_paise / total_income_paise
        if emi_ratio > 0.40:
            insights.append(
                f"Your loan EMIs consume {emi_ratio:.0%} of your income ({fmt(total_debt_min_paise)} of {fmt(total_income_paise)}). "
                f"A healthy ratio is below 40%. Consider requesting an EMI reduction or tenure extension from your bank."
            )
        elif emi_ratio > 0.25:
            insights.append(
                f"Your EMIs are {emi_ratio:.0%} of your income — manageable but worth monitoring. "
                f"Avoid taking on any new loans until this ratio drops below 25%."
            )

    # 4. High-interest debt advice with approximate monthly cost
    high_interest_debts = [
        d for d in state.debts
        if (d.interest_rate_bps is not None and d.interest_rate_bps >= 1800)
        or d.kind == "credit_card"
    ]
    if high_interest_debts:
        monthly_interest_paise = sum(
            (d.balance_paise * d.interest_rate_bps) // (12 * 10_000)
            for d in high_interest_debts
            if d.balance_paise and d.interest_rate_bps
        )
        if monthly_interest_paise > 0:
            insights.append(
                f"You are paying approximately {fmt(monthly_interest_paise)}/month in interest on your high-interest debt(s). "
                f"Consolidating with a personal loan at 10–15% p.a. could significantly lower this cost."
            )
        else:
            insights.append(
                "You have high-interest debt (credit card or 18%+ loan). Pay these off aggressively "
                "or consolidate them with a lower-rate personal loan — "
                "the interest compounds rapidly if you only pay the minimum each month."
            )

    # 5. Debt avalanche strategy (if multiple debts)
    if len(state.debts) > 1:
        debts_with_rate = [d for d in state.debts if d.interest_rate_bps]
        if debts_with_rate:
            highest = max(debts_with_rate, key=lambda d: d.interest_rate_bps or 0)
            rate_pct = (highest.interest_rate_bps or 0) / 100
            insights.append(
                f"Debt Avalanche: Pay minimums on all loans, then direct any extra cash to "
                f"'{highest.name}' ({rate_pct:.1f}% p.a.) first — this is your most expensive debt mathematically."
            )
        else:
            insights.append(
                "You have multiple loans. Use the Avalanche method: pay minimums on all and put "
                "extra cash toward your highest-interest debt first to minimise total interest paid."
            )

    # 6. Optional spend as % of income
    if total_income_paise > 0 and total_optional_paise > 0:
        opt_ratio = total_optional_paise / total_income_paise
        if opt_ratio > 0.20:
            insights.append(
                f"Optional expenses make up {opt_ratio:.0%} of your income ({fmt(total_optional_paise)}). "
                f"Reducing discretionary spending is the fastest lever to improve your monthly balance."
            )

    return insights


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
        else:  # an obligation
            req = (
                getattr(entry, "min_payment_paise", None) or entry.current.amount_paise
            )
            if balance >= req:
                balance -= req
            else:
                available = max(0, balance)
                missed.append(
                    MissedObligation(
                        entry_id=entry.id,
                        name=entry.name,
                        due_date=entry_date,
                        required_paise=req,
                        available_paise=available,
                        shortfall_paise=req - available,
                    )
                )
                # Mathematically subtract it anyway so the final balance accurately 
                # reflects the true cash-flow deficit.
                balance -= req
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

    disclaimer_text = (
        "Please note: This assistant is an AI tool, not a SEBI-registered or government-certified financial advisor. "
        "These insights are mathematical projections, not professional financial advice."
    )

    if not missed:
        insights = _generate_insights(state, "surplus", balance, [], [])
        return PlanResult(
            status="surplus",
            final_balance_paise=balance,
            cuts=[],
            missed_obligations=[],
            insights=insights,
            income=state.income,
            essential_expenses=state.essential_expenses,
            optional_expenses=state.optional_expenses,
            debts=state.debts,
            disclaimer=disclaimer_text,
        )

    cuts, missed, final_balance, final_ledger = _find_cuts(
        state, missed, balance, ledger
    )
    status: Literal["surplus", "solved_with_cuts", "unsolvable"] = (
        "solved_with_cuts" if not missed else "unsolvable"
    )
    insights = _generate_insights(state, status, final_balance, cuts, missed)
    return PlanResult(
        status=status,
        final_balance_paise=final_balance,
        cuts=cuts,
        missed_obligations=missed,
        insights=insights,
        income=state.income,
        essential_expenses=state.essential_expenses,
        optional_expenses=state.optional_expenses,
        debts=state.debts,
        disclaimer=disclaimer_text,
    )


__all__ = [
    "SessionState",
    "MissedObligation",
    "LedgerEntry",
    "PlanResult",
    "build_plan",
    "calculate_emi_paise",
    "compute_cash_position",
    "compute_missing_fields",
    "compute_blocking_issues",
]
