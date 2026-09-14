"""SessionState and related models"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

Confidence = Literal["confirmed", "estimated"]

RecurrenceUnit = Literal["day", "week", "month"]

DebtKind = Literal[
    "personal_loan",
    "credit_card",
    "education_loan",
    "vehicle_loan",
    "home_loan",
    "gold_loan",
    "bnpl",
    "informal",
    "other",
]


def _generate_entry_id() -> str:
    """Generate an Entry id in the 'entry_' + 8 hex chars format."""
    return f"entry_{uuid.uuid4().hex[:8]}"


class Recurrence(BaseModel):
    """How often a recurring Entry occurs: `count` time(s) every `interval`
    `unit`(s), with an optional calendar anchor for *which* day it lands on.

    - unit='month', interval=1, count=1, day_of_month=6   -> EMI due the 6th
    - unit='month', interval=1, count=1, day_of_month=23  -> EMI due the 23rd
    - unit='month', interval=3, count=1                   -> quarterly, no fixed day
    - unit='week',  interval=1, count=2                   -> twice a week (no single anchor)
    - unit='day',   interval=14, count=1                  -> fortnightly

    Two debts due on the 6th and the 23rd are simply two `Debt` entries each
    with their own `Recurrence` (and their own `due_date` giving the next
    concrete occurrence) — nothing here needs to represent both dates at once.

    `day_of_month`/`day_of_week` are anchors for `count == 1` cadences only:
    once something happens more than once per unit ('twice a week'), a
    single anchor day can't describe the pattern, so both are left unset
    there rather than silently picked. `day_of_month` values above 28 are
    allowed as stated (e.g. "due on the 31st") — clamping that into a
    shorter month (February) is calendar arithmetic for engine.py's
    normalization logic, not something this model resolves.
    """

    model_config = ConfigDict(extra="forbid")

    unit: RecurrenceUnit
    interval: StrictInt = Field(ge=1)
    count: StrictInt = Field(ge=1, default=1)
    day_of_month: StrictInt | None = Field(default=None, ge=1, le=31)
    # 0=Monday .. 6=Sunday, matching stdlib date.weekday().
    day_of_week: StrictInt | None = Field(default=None, ge=0, le=6)

    @model_validator(mode="after")
    def _anchor_is_consistent(self) -> Recurrence:
        if self.day_of_month is not None and self.unit != "month":
            raise ValueError("day_of_month only applies when unit is 'month'")
        if self.day_of_week is not None and self.unit != "week":
            raise ValueError("day_of_week only applies when unit is 'week'")
        if self.count != 1 and (
            self.day_of_month is not None or self.day_of_week is not None
        ):
            raise ValueError("a single day anchor requires count == 1")
        return self


def _default_recurrence() -> Recurrence:
    return Recurrence(unit="month", interval=1, count=1)


class FieldHistory(BaseModel):
    """One point-in-time value for a monetary field, with provenance."""

    model_config = ConfigDict(extra="forbid")

    amount_paise: StrictInt = Field(gt=0)
    confidence: Confidence
    turn_index: int
    timestamp: datetime


class Entry(BaseModel):
    """A single income or expense line item."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=_generate_entry_id)
    name: str
    current: FieldHistory
    history: list[FieldHistory] = Field(default_factory=list)
    # 'one_time' for a windfall/one-off bill that shouldn't be projected
    # into future months; a Recurrence for anything that repeats, including
    # cadences plain 'monthly' can't express (every 3 months, twice a week).
    recurrence: Literal["one_time"] | Recurrence = Field(
        default_factory=_default_recurrence
    )
    possible_duplicate: bool = False
    duplicate_of: str | None = None


class Debt(Entry):
    """An `Entry` specialization for loans and credit cards.

    `current`/`history` (inherited from Entry) track `min_payment_paise`
    over time, not `balance_paise` — the min payment is what changes turn
    to turn as the user restates it, and needs the same confidence/history
    audit trail as an income or expense figure. `balance_paise` is a
    simple point-in-time snapshot, not independently versioned, since the
    engine only ever needs its current value for shortfall math.
    """

    kind: DebtKind
    kind_label: str | None = None
    due_date: date
    min_payment_paise: StrictInt = Field(gt=0)
    balance_paise: StrictInt | None = None
    interest_rate_bps: StrictInt | None = None
    is_secured: bool | None = None

    @model_validator(mode="after")
    def _other_kind_requires_label(self) -> Debt:
        # An 'other' debt with no label is financially useless data — the
        # engine and any human reading the plan can't reason about a debt
        # it can't name. Every other kind is self-describing and doesn't
        # need one, though a label is still allowed for extra color (e.g.
        # kind='vehicle_loan', kind_label='Activa loan, Bajaj Finance').
        if self.kind == "other" and not (self.kind_label and self.kind_label.strip()):
            raise ValueError("kind_label is required when kind is 'other'")
        return self


class Conflict(BaseModel):
    """A detected disagreement between an entry's current value and a newly
    stated value for the same field, awaiting resolution."""

    model_config = ConfigDict(extra="forbid")

    id: str
    entry_id: str
    field_name: str
    old_amount_paise: StrictInt
    new_amount_paise: StrictInt
    resolved: bool = False
    created_at: datetime


class SessionState(BaseModel):
    """The single source of truth for one voice-assistant session."""

    model_config = ConfigDict(extra="forbid")

    room_name: str
    today: date
    income: list[Entry] = Field(default_factory=list)
    essential_expenses: list[Entry] = Field(default_factory=list)
    optional_expenses: list[Entry] = Field(default_factory=list)
    debts: list[Debt] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    plan: Any | None = None
    turn_index: int = 0
    state_version: int = 0
    updated_at: datetime


def compute_missing_fields(state: SessionState) -> list[str]:
    """Return which minimum-viability fields are missing from `state`."""
    missing: list[str] = []
    if not state.income:
        missing.append("income")
    if not state.essential_expenses and not state.debts:
        missing.append("obligations")
    return missing


def compute_blocking_issues(state: SessionState) -> list[str]:
    """Return all conditions preventing plan finalization: missing fields,
    unresolved conflicts, or unresolved possible duplicates.

    This is the sole guard checked by `finalize_plan`.
    """
    issues = compute_missing_fields(state)
    if any(not conflict.resolved for conflict in state.conflicts):
        issues.append("unresolved_conflict")

    all_entries = (
        state.income + state.essential_expenses + state.optional_expenses + state.debts
    )
    if any(entry.possible_duplicate for entry in all_entries):
        issues.append("unresolved_duplicate")

    return issues


def compute_cash_position(state: SessionState) -> int:
    """Return a rough confirmed-only cash position, in paise.

    NOT the final plan calculation. This is a placeholder pre-engine
    number — confirmed income minus confirmed essential expenses, nothing
    else. It excludes debts and optional_expenses entirely, and excludes
    any entry with confidence == 'estimated' completely (no partial
    weight, no discount) rather than guessing at how much of an
    unconfirmed figure to trust. The real 30-day simulation, which does
    account for all of that, is Phase 7's `build_plan`.
    """
    confirmed_income = sum(
        entry.current.amount_paise
        for entry in state.income
        if entry.current.confidence == "confirmed"
    )
    confirmed_essential_expenses = sum(
        entry.current.amount_paise
        for entry in state.essential_expenses
        if entry.current.confidence == "confirmed"
    )
    return confirmed_income - confirmed_essential_expenses
