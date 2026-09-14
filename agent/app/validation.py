"""Validation schemas for LLM tool calls.

This layer enforces business constraints and executes unit conversions
(rupees -> paise, percent -> bps) so downstream handlers receive clean,
deterministic data types matching `SessionState`.
"""

import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from app.money import rupees_to_paise
from app.state import Confidence, DebtKind


def _validate_rupees(v: Any) -> int:
    if v is None:
        raise ValueError("amount cannot be null")

    if type(v) is int and not isinstance(v, bool):
        v = float(v)

    try:
        paise = rupees_to_paise(v)
    except Exception as e:
        raise ValueError(str(e)) from e

    if paise <= 0:
        raise ValueError("amount must be greater than zero")
    return paise


def _validate_optional_rupees(v: Any) -> int | None:
    if v is None:
        return None
    return _validate_rupees(v)


def _validate_percent(v: Any) -> int | None:
    if v is None:
        return None
    try:
        val = float(v)
    except (TypeError, ValueError):
        raise ValueError("interest rate must be a number")
    if not (0 <= val <= 100):
        raise ValueError("interest rate must be between 0 and 100")
    return int(round(val * 100))


RupeesToPaise = Annotated[int, BeforeValidator(_validate_rupees)]
OptionalRupeesToPaise = Annotated[
    int | None, BeforeValidator(_validate_optional_rupees)
]
PercentToBps = Annotated[int | None, BeforeValidator(_validate_percent)]
IdString = Annotated[str, Field(pattern=r"^(entry|conflict)_[0-9a-f]{8}$")]


class AddIncomeArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    amount_paise: RupeesToPaise = Field(alias="amount_rupees")
    date: datetime.date
    confidence: Confidence


class AddExpenseArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    category: Literal["essential", "optional"]
    name: str
    amount_paise: RupeesToPaise = Field(alias="amount_rupees")
    date: datetime.date
    confidence: Confidence


class ResolveDuplicateArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    entry_id: IdString
    is_same_as_existing: bool
    existing_entry_id: IdString | None = None

    @model_validator(mode="after")
    def _check_existing_id(self) -> "ResolveDuplicateArgs":
        if self.is_same_as_existing and not self.existing_entry_id:
            raise ValueError(
                "existing_entry_id is required when is_same_as_existing is true"
            )
        return self


class ResolveConflictArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    conflict_id: IdString
    chosen_amount_paise: RupeesToPaise = Field(alias="chosen_amount_rupees")


class FinalizePlanArgs(BaseModel):
    pass


class ConfirmUserUnderstoodArgs(BaseModel):
    understood: bool


class AddDebtArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    kind: DebtKind
    kind_label: str | None = None
    min_payment_paise: OptionalRupeesToPaise = Field(default=None, alias="min_payment_rupees")
    date: datetime.date | None = None
    confidence: Confidence
    balance_paise: OptionalRupeesToPaise = Field(default=None, alias="balance_rupees")
    interest_rate_bps: PercentToBps = Field(default=None, alias="interest_rate_percent")
    duration_months: int | None = Field(default=None, ge=1, le=600)

    @model_validator(mode="after")
    def _other_kind_requires_label(self) -> "AddDebtArgs":
        if self.kind == "other" and not (self.kind_label and self.kind_label.strip()):
            raise ValueError("kind_label is required when kind is 'other'")
        return self

    @model_validator(mode="after")
    def _emi_or_loan_details_required(self) -> "AddDebtArgs":
        """Require either an explicit EMI or the full loan details to compute one.

        The backend will compute the EMI from (balance, rate, duration) if no
        min_payment is given — but only when all three are present. Without any
        of these the debt cannot be meaningfully recorded.
        """
        has_emi = self.min_payment_paise is not None
        can_compute = (
            self.balance_paise is not None
            and self.interest_rate_bps is not None
            and self.duration_months is not None
        )
        if not has_emi and not can_compute:
            raise ValueError(
                "Either min_payment_rupees OR all three of (balance_rupees, "
                "interest_rate_percent, duration_months) must be provided so the "
                "EMI can be calculated."
            )
        return self


class UpdateEntryArgs(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    entry_id: IdString
    new_amount_paise: OptionalRupeesToPaise = Field(
        default=None, alias="new_amount_rupees"
    )
    confidence: Confidence | None = None
    new_balance_paise: OptionalRupeesToPaise = Field(
        default=None, alias="new_balance_rupees"
    )
    new_interest_rate_bps: PercentToBps = Field(
        default=None, alias="new_interest_rate_percent"
    )

    @model_validator(mode="after")
    def _check_update_fields(self) -> "UpdateEntryArgs":
        if all(
            v is None
            for v in [
                self.new_amount_paise,
                self.new_balance_paise,
                self.new_interest_rate_bps,
            ]
        ):
            raise ValueError("At least one field to update must be provided")
        if self.new_amount_paise is not None and self.confidence is None:
            raise ValueError("confidence is required when updating the amount")
        return self


class RemoveEntryArgs(BaseModel):
    """New model to allow the LLM to delete mistated or canceled items."""

    model_config = ConfigDict(populate_by_name=True)
    entry_id: IdString
