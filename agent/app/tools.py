"""Function-calling tool schemas for the LLM."""

import functools
import uuid
from typing import Any, Literal, Callable, Coroutine
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timedelta, timezone

from app.session_store import locked_state
from app.state import (
    SessionState,
    Debt,
    Entry,
    FieldHistory,
    Recurrence,
    Conflict,
    compute_blocking_issues,
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
from app.entity_resolution import find_near_duplicate

try:
    from agent.app.engine import build_plan
except ImportError:
    from app.engine import build_plan

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "add_income",
            "description": (
                "Register a completely new, previously unmentioned income source (e.g., a salary, a freelance gig, or a cash gift). "
                "CRITICAL: Do NOT call this tool to correct, update, or append information to an income source that has already been registered. "
                "If the user is correcting an amount for an existing income, you MUST use 'update_entry' instead. "
                "Only call this when the user introduces a distinct, new stream of money coming in."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "A short, clear noun phrase naming the income source (e.g., 'Primary Salary', 'Uber Driving', 'Dividend').",
                    },
                    "amount_rupees": {
                        "type": "number",
                        "description": "The exact numeric amount in Indian Rupees (INR). Strip all currency symbols and commas.",
                    },
                    "date": {
                        "type": "string",
                        "description": "The exact or approximate date the money will be received, strictly in ISO 8601 format (YYYY-MM-DD). If the user says 'the 5th of next month', calculate the correct YYYY-MM-DD.",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["confirmed", "estimated"],
                        "description": "Set to 'confirmed' if the user stated an exact, known figure. Set to 'estimated' if the user used words like 'around', 'about', 'maybe', or gave a rough range.",
                    },
                },
                "required": ["name", "amount_rupees", "date", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": (
                "Register a completely new, previously unmentioned expense. "
                "CRITICAL: Do NOT call this tool to correct or update an existing expense. Use 'update_entry' for corrections. "
                "Do NOT use this for loans, EMIs, or credit cards; use 'add_debt' for those. "
                "Use this only for standard outflow like rent, utilities, groceries, subscriptions, or dining out."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["essential", "optional"],
                        "description": "Strictly classify as 'essential' if the expense is required for basic survival or legal compliance (rent, groceries, electricity). Classify as 'optional' if it is a lifestyle choice that could theoretically be cut to save money (Netflix, dining out, hobbies).",
                    },
                    "name": {
                        "type": "string",
                        "description": "A concise name for the expense (e.g., 'Apartment Rent', 'Spotify Subscription').",
                    },
                    "amount_rupees": {
                        "type": "number",
                        "description": "The outflow amount in Indian Rupees (INR).",
                    },
                    "date": {
                        "type": "string",
                        "description": "The due date or expected date of the expense, strictly in ISO 8601 format (YYYY-MM-DD).",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["confirmed", "estimated"],
                        "description": "Set to 'confirmed' for exact bills. Set to 'estimated' for variable expenses like groceries or utilities where the user is guessing.",
                    },
                },
                "required": ["category", "name", "amount_rupees", "date", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_debt",
            "description": (
                "Register a new, previously unmentioned debt obligation, such as a bank loan, EMI, credit card, or informal borrowing. "
                "CRITICAL: Do NOT call this to update an existing debt. Use 'update_entry' for corrections. "
                "This tool requires the minimum payment due. Total balance and interest rate are optional but highly encouraged if the user mentions them."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the lender or the specific debt (e.g., 'HDFC Credit Card', 'SBI Home Loan', 'Money owed to Rahul').",
                    },
                    "kind": {
                        "type": "string",
                        "enum": [
                            "personal_loan",
                            "credit_card",
                            "education_loan",
                            "vehicle_loan",
                            "home_loan",
                            "gold_loan",
                            "bnpl",
                            "informal",
                            "other",
                        ],
                        "description": "Categorize the debt into the closest matching strict type. Use 'informal' for money owed to friends/family. Use 'other' only if absolutely nothing else fits.",
                    },
                    "kind_label": {
                        "type": "string",
                        "description": "A specific description of the debt. REQUIRED if kind is 'other'.",
                    },
                    "min_payment_rupees": {
                        "type": "number",
                        "description": "The mandatory minimum payment or EMI due for this specific period, in INR.",
                    },
                    "date": {
                        "type": "string",
                        "description": "The exact due date for the minimum payment, strictly in ISO 8601 format (YYYY-MM-DD).",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["confirmed", "estimated"],
                        "description": "Set to 'confirmed' if the EMI/minimum payment is exactly known, 'estimated' if the user is guessing.",
                    },
                    "balance_rupees": {
                        "type": "number",
                        "description": "The total outstanding principal balance left to pay off, in INR. Omit if the user does not state it.",
                    },
                    "interest_rate_percent": {
                        "type": "number",
                        "description": "The annualized interest rate as a percentage (e.g., 12.5 for 12.5%). Omit if unknown.",
                    },
                },
                "required": [
                    "name",
                    "kind",
                    "min_payment_rupees",
                    "date",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_entry",
            "description": (
                "Correct or update the monetary amount of an existing entry (income, expense, or debt). "
                "CRITICAL: You must look at the provided context history to find the exact 'entry_id' (e.g., 'entry_a1b2c3d4') that corresponds to what the user is correcting. "
                "Do NOT guess the entry_id. If you cannot find a matching entry_id in your context, you must ask the user for clarification instead of calling this tool."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "The exact internal string ID of the entry being modified, retrieved from your context.",
                    },
                    "new_amount_rupees": {
                        "type": "number",
                        "description": "The new, corrected monetary amount in INR.",
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["confirmed", "estimated"],
                        "description": "Whether the user is certain of this new corrected amount.",
                    },
                    "new_balance_rupees": {
                        "type": "number",
                        "description": "For debts: the corrected total balance in INR.",
                    },
                    "new_interest_rate_percent": {
                        "type": "number",
                        "description": "For debts: the corrected interest rate percentage.",
                    },
                },
                "required": ["entry_id", "new_amount_rupees", "confidence"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_entry",
            "description": (
                "Delete an entry completely. "
                "Call this when the user explicitly cancels, voids, or says to ignore an item they previously mentioned. "
                "Requires the exact 'entry_id' from your context history."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "The exact internal string ID of the entry to remove.",
                    }
                },
                "required": ["entry_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_duplicate",
            "description": (
                "Resolve a 'possible_duplicate' warning generated by the system backend. "
                "When you attempt to add an item, the system may reject it and ask you to confirm if it is a duplicate of an existing item. "
                "Call this tool ONLY after you have explicitly asked the user if the item is a duplicate, and they have answered."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "entry_id": {
                        "type": "string",
                        "description": "The ID of the new entry that was flagged by the system as a potential duplicate.",
                    },
                    "is_same_as_existing": {
                        "type": "boolean",
                        "description": "Set to True if the user confirmed it is the same obligation. Set to False if the user confirmed they are two separate, distinct obligations.",
                    },
                    "existing_entry_id": {
                        "type": "string",
                        "description": "The exact ID of the older, existing entry that this duplicates. This MUST be provided if 'is_same_as_existing' is True.",
                    },
                },
                "required": ["entry_id", "is_same_as_existing"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_conflict",
            "description": (
                "Resolve a data conflict flagged by the system backend. "
                "If a user corrects a confirmed value by a massive margin, the system will block the update and generate a conflict ID. "
                "Call this tool ONLY after you have asked the user to verify the discrepancy and they have chosen the correct final amount."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "conflict_id": {
                        "type": "string",
                        "description": "The exact conflict ID provided to you by the system backend.",
                    },
                    "chosen_amount_rupees": {
                        "type": "number",
                        "description": "The final, verified correct amount in INR chosen by the user to resolve the conflict.",
                    },
                },
                "required": ["conflict_id", "chosen_amount_rupees"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finalize_plan",
            "description": (
                "Trigger the deterministic 30-day financial engine to calculate surplus, shortfall, and cuts. "
                "CRITICAL RULES FOR CALLING: "
                "1. You MUST NOT call this if there are still items listed in the 'missing_fields' context. "
                "2. You MUST NOT call this if there are unresolved conflicts or unverified duplicates. "
                "3. Before calling this, you must explicitly ask the user if they have any other expenses or obligations to add."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "confirm_user_understood",
            "description": (
                "Log the user's comprehension of the final financial plan. "
                "Call this ONLY after 'finalize_plan' has been successfully run, you have narrated the results to the user, "
                "and you have explicitly asked them 'Does this plan make sense to you?'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "understood": {
                        "type": "boolean",
                        "description": "True if the user explicitly confirmed they understand the plan and how to execute it; False if they are confused or rejected it.",
                    }
                },
                "required": ["understood"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolResult(BaseModel):
    """Canonical return envelope for all tool handlers.

    Ensures the LLM-facing dispatch layer always receives a predictable JSON
    shape, preventing divergent error-handling logic across different tools.
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "warning", "error"]
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, **data: Any) -> "ToolResult":
        """Return a successful result with arbitrary data."""
        return cls(status="ok", data=data)

    @classmethod
    def warning(cls, message: str, **data: Any) -> "ToolResult":
        """Return a success-but-flagged result (e.g., possible duplicate)."""
        return cls(status="warning", message=message, data=data)

    @classmethod
    def error(cls, message: str) -> "ToolResult":
        """Return a business-rule or validation failure."""
        return cls(status="error", message=message)


try:
    from app.broadcast import mark_room_dirty
except ImportError:
    from agent.app.broadcast import mark_room_dirty


def state_mutation(func: Callable[..., Coroutine[Any, Any, ToolResult]]):
    """Decorator to wrap tool handlers with concurrency safety.

    1. Acquires the room's lock via `locked_state`.
    2. Runs the handler body, injecting the locked `SessionState` as a kwarg.
    3. Increments `state_version` and marks room dirty if the result was not an error.
    4. Automatically releases the lock.
    """

    @functools.wraps(func)
    async def wrapper(room_name: str, *args: Any, **kwargs: Any) -> ToolResult:
        async with locked_state(room_name) as state:
            # Inject the locked state into the handler
            kwargs["state"] = state

            result = await func(room_name, *args, **kwargs)

            # If the handler succeeded (or warned), it mutated state.
            # Bump the version and mark the room dirty.
            # Batching per-turn, rather than per-tool-call, avoids a rapid burst of out-of-order messages when several facts are extracted from one utterance at once.
            if result.status in ("ok", "warning"):
                state.state_version += 1
                mark_room_dirty(room_name)

            return result

    return wrapper


@state_mutation
async def add_income(
    room_name: str, args: AddIncomeArgs, state: SessionState = None
) -> ToolResult:
    if not (state.today <= args.date <= state.today + timedelta(days=29)):
        return ToolResult.error("date must be within the next 30 days")

    existing_id = find_near_duplicate(state.income, args.name)

    history = FieldHistory(
        amount_paise=args.amount_paise,
        confidence=args.confidence,
        turn_index=state.turn_index,
        timestamp=datetime.now(timezone.utc),
    )

    entry = Entry(
        name=args.name,
        current=history,
        history=[],
        recurrence=Recurrence(
            unit="month", interval=1, count=1, day_of_month=args.date.day
        ),
        possible_duplicate=bool(existing_id),
        duplicate_of=existing_id,
    )

    state.income.append(entry)

    if existing_id:
        return ToolResult.warning(
            "possible duplicate of an existing entry, please confirm with the user whether this is the same item or a genuinely separate one",
            entry_id=entry.id,
            duplicate_of=existing_id,
        )
    return ToolResult.ok(entry_id=entry.id)


@state_mutation
async def add_expense(
    room_name: str, args: AddExpenseArgs, state: SessionState = None
) -> ToolResult:
    if not (state.today <= args.date <= state.today + timedelta(days=29)):
        return ToolResult.error("date must be within the next 30 days")

    target_list = (
        state.essential_expenses
        if args.category == "essential"
        else state.optional_expenses
    )
    existing_id = find_near_duplicate(target_list, args.name)

    history = FieldHistory(
        amount_paise=args.amount_paise,
        confidence=args.confidence,
        turn_index=state.turn_index,
        timestamp=datetime.now(timezone.utc),
    )

    entry = Entry(
        name=args.name,
        current=history,
        history=[],
        recurrence=Recurrence(
            unit="month", interval=1, count=1, day_of_month=args.date.day
        ),
        possible_duplicate=bool(existing_id),
        duplicate_of=existing_id,
    )
    target_list.append(entry)

    if existing_id:
        return ToolResult.warning(
            "possible duplicate of an existing entry, please confirm with the user whether this is the same item or a genuinely separate one",
            entry_id=entry.id,
            duplicate_of=existing_id,
        )

    return ToolResult.ok(entry_id=entry.id)


@state_mutation
async def add_debt(
    room_name: str, args: AddDebtArgs, state: SessionState = None
) -> ToolResult:
    if not (state.today <= args.date <= state.today + timedelta(days=29)):
        return ToolResult.error("date must be within the next 30 days")

    existing_id = find_near_duplicate(state.debts, args.name)

    history = FieldHistory(
        amount_paise=args.min_payment_paise,
        confidence=args.confidence,
        turn_index=state.turn_index,
        timestamp=datetime.now(timezone.utc),
    )

    debt = Debt(
        name=args.name,
        kind=args.kind,
        kind_label=args.kind_label,
        due_date=args.date,
        min_payment_paise=args.min_payment_paise,
        balance_paise=args.balance_paise,
        interest_rate_bps=args.interest_rate_bps,
        current=history,
        history=[],
        possible_duplicate=bool(existing_id),
        duplicate_of=existing_id,
    )

    state.debts.append(debt)
    if existing_id:
        return ToolResult.warning(
            "possible duplicate of an existing entry, please confirm with the user whether this is the same item or a genuinely separate one",
            entry_id=debt.id,
            duplicate_of=existing_id,
        )

    return ToolResult.ok(entry_id=debt.id)


@state_mutation
async def resolve_duplicate(
    room_name: str, args: ResolveDuplicateArgs, state: SessionState = None
) -> ToolResult:
    target_entry = None
    target_list = None

    # 1. Locate the flagged entry
    for category_list in [
        state.income,
        state.essential_expenses,
        state.optional_expenses,
        state.debts,
    ]:
        for entry in category_list:
            if entry.id == args.entry_id:
                target_entry = entry
                target_list = category_list
                break
        if target_entry:
            break

    if not target_entry:
        return ToolResult.error(f"Flagged entry {args.entry_id} not found")

    if args.is_same_as_existing:
        # 2. Locate the existing entry it duplicates
        existing_entry = None
        for entry in target_list:
            if entry.id == args.existing_entry_id:
                existing_entry = entry
                break

        if not existing_entry:
            return ToolResult.error(
                f"Existing entry {args.existing_entry_id} not found"
            )

        # 3. Merge: Treat the new entry's values as corrections to the older entry
        existing_entry.history.append(existing_entry.current)
        existing_entry.current = target_entry.current

        # Merge optional debt fields if applicable
        if isinstance(existing_entry, Debt) and isinstance(target_entry, Debt):
            if target_entry.balance_paise is not None:
                existing_entry.balance_paise = target_entry.balance_paise
            if target_entry.interest_rate_bps is not None:
                existing_entry.interest_rate_bps = target_entry.interest_rate_bps

        # Remove the flagged duplicate
        target_list.remove(target_entry)
        return ToolResult.ok(resolved_status="merged", kept_id=existing_entry.id)
    else:
        # 4. Independent items: Unflag and keep both
        target_entry.possible_duplicate = False
        target_entry.duplicate_of = None
        return ToolResult.ok(resolved_status="kept_separate", entry_id=target_entry.id)


@state_mutation
async def update_entry(
    room_name: str, args: UpdateEntryArgs, state: SessionState = None
) -> ToolResult:
    """Update entry with Step 4.10 15% threshold conflict detection."""
    target = None
    for category_list in [
        state.income,
        state.essential_expenses,
        state.optional_expenses,
        state.debts,
    ]:
        for entry in category_list:
            if entry.id == args.entry_id:
                target = entry
                break
        if target:
            break

    if not target:
        return ToolResult.error(f"Entry {args.entry_id} not found")

    if args.new_amount_paise is not None:
        old_amount = target.current.amount_paise
        old_conf = target.current.confidence
        new_conf = args.confidence or "confirmed"

        delta_ratio = abs(args.new_amount_paise - old_amount) / float(old_amount)
        if delta_ratio > 0.15 and old_conf == "confirmed" and new_conf == "confirmed":
            conflict_id = f"conflict_{uuid.uuid4().hex[:8]}"
            conflict = Conflict(
                id=conflict_id,
                entry_id=target.id,
                field_name="amount_paise",
                old_amount_paise=old_amount,
                new_amount_paise=args.new_amount_paise,
                resolved=False,
                created_at=datetime.now(timezone.utc),
            )
            state.conflicts.append(conflict)
            return ToolResult.warning(
                "significant change detected (above 15% threshold), conflict recorded awaiting user confirmation",
                conflict_id=conflict.id,
                entry_id=target.id,
            )

        target.history.append(target.current)
        target.current = FieldHistory(
            amount_paise=args.new_amount_paise,
            confidence=new_conf,
            turn_index=state.turn_index,
            timestamp=datetime.now(timezone.utc),
        )

    if isinstance(target, Debt):
        if args.new_balance_paise is not None:
            target.balance_paise = args.new_balance_paise
        if args.new_interest_rate_bps is not None:
            target.interest_rate_bps = args.new_interest_rate_bps

    return ToolResult.ok(updated_id=target.id)


@state_mutation
async def resolve_conflict(
    room_name: str, args: ResolveConflictArgs, state: SessionState = None
) -> ToolResult:
    """Mark a conflict as resolved and update the entry with the chosen amount."""
    target_conflict = None
    for conflict in state.conflicts:
        if conflict.id == args.conflict_id:
            target_conflict = conflict
            break

    if not target_conflict:
        return ToolResult.error(f"Conflict {args.conflict_id} not found")

    target_entry = None
    for category_list in [
        state.income,
        state.essential_expenses,
        state.optional_expenses,
        state.debts,
    ]:
        for entry in category_list:
            if entry.id == target_conflict.entry_id:
                target_entry = entry
                break
        if target_entry:
            break

    if not target_entry:
        return ToolResult.error(
            f"Entry {target_conflict.entry_id} associated with conflict not found"
        )

    target_entry.history.append(target_entry.current)
    target_entry.current = FieldHistory(
        amount_paise=args.chosen_amount_paise,
        confidence="confirmed",
        turn_index=state.turn_index,
        timestamp=datetime.now(timezone.utc),
    )
    target_conflict.resolved = True
    return ToolResult.ok(
        resolved_conflict_id=target_conflict.id, entry_id=target_entry.id
    )


@state_mutation
async def remove_entry(
    room_name: str, args: RemoveEntryArgs, state: SessionState = None
) -> ToolResult:
    """Remove an entry by ID from session state."""
    for category_list in [
        state.income,
        state.essential_expenses,
        state.optional_expenses,
        state.debts,
    ]:
        for entry in category_list:
            if entry.id == args.entry_id:
                category_list.remove(entry)
                return ToolResult.ok(removed_id=args.entry_id)
    return ToolResult.error(f"Entry {args.entry_id} not found")


@state_mutation
async def finalize_plan(
    room_name: str, args: FinalizePlanArgs = None, state: SessionState = None
) -> ToolResult:
    """Guard plan finalization using compute_blocking_issues and generate the 30-day cash flow plan."""
    blocking = compute_blocking_issues(state)
    if blocking:
        return ToolResult.error(
            f"Cannot finalize plan. The following blocking issues must be resolved first: {', '.join(blocking)}"
        )
    plan_result = build_plan(state)
    state.plan = plan_result
    return ToolResult.ok(
        message="Plan criteria met and 30-day plan generated successfully.",
        status=plan_result.status,
        final_balance_paise=plan_result.final_balance_paise,
        cuts=[c.model_dump() for c in plan_result.cuts],
        missed_obligations=[m.model_dump() for m in plan_result.missed_obligations],
    )


@state_mutation
async def confirm_user_understood(
    room_name: str, args: ConfirmUserUnderstoodArgs, state: SessionState = None
) -> ToolResult:
    """Record user's comprehension of the finalized plan."""
    return ToolResult.ok(understood=args.understood)
