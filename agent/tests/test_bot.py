"""Unit tests for bot.py prompt definition, tool registration, and Pipecat handler dispatch."""

import asyncio
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bot import REGISTERED_TOOLS, _create_pipecat_handler
from app.prompt import SYSTEM_PROMPT
from app.session_store import get_or_create, locked_state
from app.state import SessionState
from app.tools import TOOL_SCHEMAS, add_income
from app.validation import AddIncomeArgs


class TestBotSystemPrompt:
    def test_system_prompt_contains_required_directives(self):
        prompt_lower = SYSTEM_PROMPT.lower()
        assert "30-day" in prompt_lower
        assert "financial" in prompt_lower
        assert "natural" in prompt_lower
        assert (
            "never perform financial math" in prompt_lower
            or "arithmetic" in prompt_lower
        )
        assert "warning" in prompt_lower
        assert "resolve_duplicate" in prompt_lower
        assert "resolve_conflict" in prompt_lower


class TestBotToolRegistration:
    def test_all_tool_schemas_are_registered(self):
        schema_names = {item["function"]["name"] for item in TOOL_SCHEMAS}
        registered_names = {name for name, _, _ in REGISTERED_TOOLS}
        assert schema_names == registered_names


class TestPipecatHandlerDispatch:
    def test_handler_dispatches_add_income_and_mutates_state(self):
        room_name = "test-bot-room-1"
        get_or_create(room_name, date(2026, 9, 14))

        received_results = []

        async def _mock_result_callback(result_dict):
            received_results.append(result_dict)

        class MockFunctionCallParams:
            def __init__(self, function_name, arguments, result_callback):
                self.function_name = function_name
                self.arguments = arguments
                self.result_callback = result_callback

        handler = _create_pipecat_handler(room_name, AddIncomeArgs, add_income)
        params = MockFunctionCallParams(
            function_name="add_income",
            arguments={
                "name": "Primary Salary",
                "amount_rupees": 50000,
                "date": "2026-09-20",
                "confidence": "confirmed",
            },
            result_callback=_mock_result_callback,
        )

        asyncio.run(handler(params))

        assert len(received_results) == 1
        res = received_results[0]
        assert res["status"] == "ok"
        assert "entry_id" in res["data"]

        async def _check_state() -> SessionState:
            async with locked_state(room_name) as state:
                return state

        state = asyncio.run(_check_state())
        assert len(state.income) == 1
        entry = state.income[0]
        assert entry.name == "Primary Salary"
        assert entry.current.amount_paise == 5_000_000

    def test_handler_returns_error_on_validation_failure(self):
        room_name = "test-bot-room-2"
        get_or_create(room_name, date(2026, 9, 14))

        received_results = []

        async def _mock_result_callback(result_dict):
            received_results.append(result_dict)

        class MockFunctionCallParams:
            def __init__(self, function_name, arguments, result_callback):
                self.function_name = function_name
                self.arguments = arguments
                self.result_callback = result_callback

        handler = _create_pipecat_handler(room_name, AddIncomeArgs, add_income)
        # Invalid amount (negative)
        params = MockFunctionCallParams(
            function_name="add_income",
            arguments={
                "name": "Salary",
                "amount_rupees": -500,
                "date": "2026-09-20",
                "confidence": "confirmed",
            },
            result_callback=_mock_result_callback,
        )

        asyncio.run(handler(params))

        assert len(received_results) == 1
        res = received_results[0]
        assert res["status"] == "error"
        assert "Invalid tool arguments" in res["message"]

    def test_handler_returns_warning_on_possible_duplicate(self):
        room_name = "test-bot-room-3"
        get_or_create(room_name, date(2026, 9, 14))

        received_results = []

        async def _mock_result_callback(result_dict):
            received_results.append(result_dict)

        class MockFunctionCallParams:
            def __init__(self, function_name, arguments, result_callback):
                self.function_name = function_name
                self.arguments = arguments
                self.result_callback = result_callback

        handler = _create_pipecat_handler(room_name, AddIncomeArgs, add_income)
        params1 = MockFunctionCallParams(
            function_name="add_income",
            arguments={
                "name": "Salary",
                "amount_rupees": 50000,
                "date": "2026-09-20",
                "confidence": "confirmed",
            },
            result_callback=_mock_result_callback,
        )
        asyncio.run(handler(params1))

        # Add second income with near-duplicate name
        params2 = MockFunctionCallParams(
            function_name="add_income",
            arguments={
                "name": "Salary",
                "amount_rupees": 50000,
                "date": "2026-09-25",
                "confidence": "confirmed",
            },
            result_callback=_mock_result_callback,
        )
        asyncio.run(handler(params2))

        assert len(received_results) == 2
        first_res = received_results[0]
        second_res = received_results[1]

        assert first_res["status"] == "ok"
        assert second_res["status"] == "warning"
        assert "possible duplicate" in second_res["message"]
