"""Focus derivation logic for Voice-First UI routing.

Computes current_focus deterministically from executed tool calls and result statuses.
"""

from dataclasses import dataclass
from typing import Literal

try:
    from agent.app.state import SessionState
except ImportError:
    from app.state import SessionState

FocusTarget = Literal[
    "idle",
    "income",
    "essential_expenses",
    "optional_expenses",
    "debts",
    "conflict",
    "duplicate",
    "missing_info",
    "plan",
]


@dataclass
class ToolCallRecord:
    tool_name: str
    status: Literal["ok", "warning", "error"]
    target_list: str | None = None


_room_records: dict[str, list[ToolCallRecord]] = {}
_room_focus: dict[str, FocusTarget] = {}


def record_tool_call(
    room_name: str,
    tool_name: str,
    status: Literal["ok", "warning", "error"],
    target_list: str | None = None,
) -> None:
    """Record an executed tool call for the current turn's focus calculation."""
    if room_name not in _room_records:
        _room_records[room_name] = []
    _room_records[room_name].append(
        ToolCallRecord(tool_name=tool_name, status=status, target_list=target_list)
    )


def get_and_clear_tool_records(room_name: str) -> list[ToolCallRecord]:
    """Retrieve and clear tool call records for the completed turn."""
    records = _room_records.pop(room_name, [])
    return records


def get_room_focus(room_name: str) -> FocusTarget:
    """Get the current FocusTarget for a room."""
    return _room_focus.get(room_name, "idle")


def set_room_focus(room_name: str, focus: FocusTarget) -> None:
    """Update the active FocusTarget for a room."""
    _room_focus[room_name] = focus


def clear_room_focus(room_name: str) -> None:
    """Clear focus state when a room session ends."""
    _room_records.pop(room_name, None)
    _room_focus.pop(room_name, None)


def _fallback_focus(state: SessionState) -> FocusTarget:
    if state.plan is not None:
        return "plan"
    if state.debts:
        return "debts"
    if state.essential_expenses:
        return "essential_expenses"
    if state.optional_expenses:
        return "optional_expenses"
    if state.income:
        return "income"
    return "missing_info"


def derive_focus(
    previous_focus: FocusTarget,
    tool_calls_this_turn: list[ToolCallRecord],
    state: SessionState,
) -> FocusTarget:
    """Derive focus target deterministically using exact priority rules."""
    if not tool_calls_this_turn:
        if previous_focus == "conflict" and not any(
            not c.resolved for c in state.conflicts
        ):
            return _fallback_focus(state)
        all_e = (
            state.income
            + state.essential_expenses
            + state.optional_expenses
            + state.debts
        )
        if previous_focus == "duplicate" and not any(
            e.possible_duplicate for e in all_e
        ):
            return _fallback_focus(state)
        if previous_focus == "idle" and state.turn_index == 0:
            return "idle"
        return previous_focus

    best_rank = 999
    chosen_focus: FocusTarget = previous_focus

    for call in tool_calls_this_turn:
        rank = 999
        target: FocusTarget | None = None

        if call.tool_name == "finalize_plan" and call.status == "ok":
            rank = 1
            target = "plan"
        elif call.tool_name == "update_entry" and call.status == "warning":
            rank = 2
            target = "conflict"
        elif (
            call.tool_name in ("add_income", "add_expense", "add_debt")
            and call.status == "warning"
        ):
            rank = 3
            target = "duplicate"
        elif call.status == "ok":
            if call.tool_name == "resolve_conflict":
                rank = 4
                target = _fallback_focus(state)
            elif call.tool_name == "resolve_duplicate":
                rank = 4
                target = _fallback_focus(state)
            elif call.tool_name == "update_entry":
                # Route to the list that contains the updated entry so the
                # correct card is visible after the update.
                if call.target_list in (
                    "income",
                    "essential_expenses",
                    "optional_expenses",
                    "debts",
                ):
                    rank = 4
                    target = call.target_list  # type: ignore[assignment]
                else:
                    # Fallback: keep previous focus so we don't blindly hide
                    # the current card if we can't determine the list.
                    rank = 999
            elif call.tool_name == "add_debt" or call.target_list == "debts":
                rank = 5
                target = "debts"
            elif (
                call.tool_name == "add_expense"
                and call.target_list == "essential_expenses"
            ):
                rank = 6
                target = "essential_expenses"
            elif (
                call.tool_name == "add_expense"
                and call.target_list == "optional_expenses"
            ):
                rank = 7
                target = "optional_expenses"
            elif call.tool_name == "add_income" or call.target_list == "income":
                rank = 8
                target = "income"

        if target is not None and rank < best_rank:
            best_rank = rank
            chosen_focus = target

    # Guard: if focus was inherited from previous_focus (no new rank matched) but no conflicts/duplicates remain unresolved, reset to fallback
    if best_rank == 999:
        if chosen_focus == "conflict" and not any(
            not c.resolved for c in state.conflicts
        ):
            chosen_focus = _fallback_focus(state)

        all_entries = (
            state.income
            + state.essential_expenses
            + state.optional_expenses
            + state.debts
        )
        if chosen_focus == "duplicate" and not any(
            e.possible_duplicate for e in all_entries
        ):
            chosen_focus = _fallback_focus(state)

    return chosen_focus
