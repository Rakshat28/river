"""Pipecat pipeline construction and wiring.

This module sets up the real-time voice loop using Daily for WebRTC transport,
Deepgram for STT, an LLM provider (OpenAI / Google), and Cartesia for TTS.
"""

from datetime import date, timedelta
import logging
import os
from typing import Any, Callable

from pydantic import BaseModel, ValidationError

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.frames.frames import LLMFullResponseStartFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.llm_service import FunctionCallParams
from pipecat.services.tts_service import TextAggregationMode
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.workers.runner import WorkerRunner

try:
    from agent.app.broadcast import (
        TurnBroadcastProcessor,
        register_room_transport,
        unregister_room_transport,
    )
    from agent.app.focus import record_tool_call
    from agent.app.prompt import SYSTEM_PROMPT
    from agent.app.session_store import get_or_create, locked_state
    from agent.app.currency import convert_to_inr, normalise_currency
    from agent.app.tools import (
        TOOL_SCHEMAS,
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
    from agent.app.validation import (
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
except ImportError:
    from app.broadcast import (
        TurnBroadcastProcessor,
        register_room_transport,
        unregister_room_transport,
    )
    from app.focus import record_tool_call
    from app.prompt import SYSTEM_PROMPT
    from app.session_store import get_or_create, locked_state
    from app.currency import convert_to_inr, normalise_currency
    from app.tools import (
        TOOL_SCHEMAS,
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

logger = logging.getLogger(__name__)

REGISTERED_TOOLS: list[tuple[str, type[BaseModel], Callable[..., Any]]] = [
    ("add_income", AddIncomeArgs, add_income),
    ("add_expense", AddExpenseArgs, add_expense),
    ("add_debt", AddDebtArgs, add_debt),
    ("update_entry", UpdateEntryArgs, update_entry),
    ("remove_entry", RemoveEntryArgs, remove_entry),
    ("resolve_duplicate", ResolveDuplicateArgs, resolve_duplicate),
    ("resolve_conflict", ResolveConflictArgs, resolve_conflict),
    ("finalize_plan", FinalizePlanArgs, finalize_plan),
    ("confirm_user_understood", ConfirmUserUnderstoodArgs, confirm_user_understood),
]


def _create_pipecat_handler(
    room_name: str,
    pydantic_cls: type[BaseModel],
    handler_func: Callable[..., Any],
) -> Callable[[FunctionCallParams], Any]:
    """Wrap a tool handler to validate LLM arguments and return a ToolResult envelope."""

    async def handler(params: FunctionCallParams) -> None:
        try:
            raw_args = params.arguments if isinstance(params.arguments, dict) else {}

            # -------------------------------------------------------------------
            # Currency pre-processing: if the LLM provided a non-INR currency,
            # fetch today's exchange rate and multiply every *_rupees field so
            # that all downstream validation and state storage sees INR values.
            # This is the single conversion point — no other module does this.
            # -------------------------------------------------------------------
            raw_currency = raw_args.pop("currency", None)
            if raw_currency:
                iso = normalise_currency(str(raw_currency))
                if iso != "INR":
                    try:
                        rate = await convert_to_inr(1.0, iso)  # rate = INR per 1 unit
                        rupee_fields = [
                            k for k, v in raw_args.items()
                            if k.endswith("_rupees") and isinstance(v, (int, float))
                        ]
                        for field in rupee_fields:
                            raw_args[field] = round(raw_args[field] * rate, 2)
                        logger.info(
                            f"Converted {len(rupee_fields)} field(s) from {iso} to INR "
                            f"at rate {rate:.4f} for tool '{params.function_name}'"
                        )
                    except Exception as fx_err:
                        err = ToolResult.error(
                            f"Currency conversion failed for '{iso}': {fx_err}. "
                            "Please ask the user for the value in Indian Rupees instead."
                        )
                        await params.result_callback(err.model_dump())
                        return

            validated_args = pydantic_cls(**raw_args)
            result: ToolResult = await handler_func(room_name, validated_args)
            target_list = None
            if params.function_name == "add_income":
                target_list = "income"
            elif params.function_name == "add_expense":
                cat = raw_args.get("category", "")
                target_list = (
                    "essential_expenses" if cat == "essential" else "optional_expenses"
                )
            elif params.function_name == "add_debt":
                target_list = "debts"
            elif params.function_name == "update_entry" and result.status == "ok":
                # Determine which list contains the updated entry so focus
                # routing can land on the correct card (see focus.py).
                entry_id = raw_args.get("entry_id", "")
                async with locked_state(room_name) as _state:
                    for _list_name, _entries in (
                        ("income", _state.income),
                        ("essential_expenses", _state.essential_expenses),
                        ("optional_expenses", _state.optional_expenses),
                        ("debts", _state.debts),
                    ):
                        if any(e.id == entry_id for e in _entries):
                            target_list = _list_name
                            break

            record_tool_call(
                room_name, params.function_name, result.status, target_list
            )
            logger.info(
                f"Tool call [{params.function_name}] for room {room_name} -> status={result.status}"
            )
            await params.result_callback(result.model_dump())
        except ValidationError as ve:
            logger.warning(
                f"Tool call [{params.function_name}] validation failure: {ve}"
            )
            err = ToolResult.error(f"Invalid tool arguments: {ve}")
            await params.result_callback(err.model_dump())
        except Exception as exc:
            logger.error(
                f"Tool call [{params.function_name}] unhandled exception: {exc}",
                exc_info=True,
            )
            err = ToolResult.error(f"Internal tool execution error: {exc}")
            await params.result_callback(err.model_dump())

    return handler


async def run_bot(room_url: str, token: str) -> None:
    """Construct and run the Pipecat voice pipeline for a session."""
    try:
        room_name = room_url.rstrip("/").split("/")[-1]
        get_or_create(room_name, date.today())

        transport = DailyTransport(
            room_url,
            token,
            "Riverline Agent",
            DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                camera_out_enabled=False,
            ),
        )

        stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))
        tts = CartesiaTTSService(
            api_key=os.getenv("CARTESIA_API_KEY"),
            text_aggregation_mode=TextAggregationMode.TOKEN,
            settings=CartesiaTTSService.Settings(
                voice="f8f5f1b2-f02d-4d8e-a40d-fd850a487b3d",
            ),
        )

        today = date.today()
        today_str = today.isoformat()
        max_date_str = (today + timedelta(days=29)).isoformat()
        dynamic_system_instruction = (
            f"{SYSTEM_PROMPT}\n\n"
            f"### CURRENT DATE & 30-DAY WINDOW\n"
            f"- Today's date is {today_str}.\n"
            f"- All tool `date` parameters MUST be YYYY-MM-DD between {today_str} and {max_date_str} (inclusive).\n"
            f"- If the user specifies a day of the month (e.g. 'the 2nd' or 'the 6th'), pick the date YYYY-MM-DD for that day falling between {today_str} and {max_date_str}."
        )

        provider = os.getenv("LLM_PROVIDER", "openai").lower()
        if provider == "google":
            try:
                from pipecat.services.google.llm import GoogleLLMService

                google_model = os.getenv("LLM_MODEL", "gemini-3.6-flash")
                if "gemini-2.5" in google_model:
                    google_model = "gemini-3.6-flash"

                llm = GoogleLLMService(
                    api_key=os.getenv("GOOGLE_API_KEY"),
                    settings=GoogleLLMService.Settings(
                        model=google_model,
                        system_instruction=dynamic_system_instruction,
                    ),
                )
            except Exception as exc:
                logger.warning(
                    f"Failed to initialize GoogleLLMService ({exc}); falling back to OpenAILLMService."
                )
                from pipecat.services.openai.llm import OpenAILLMService

                openai_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
                llm = OpenAILLMService(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    settings=OpenAILLMService.Settings(
                        model=openai_model,
                        system_instruction=dynamic_system_instruction,
                    ),
                )
        else:
            from pipecat.services.openai.llm import OpenAILLMService

            openai_model = os.getenv("LLM_MODEL", "gpt-4o-mini")
            llm = OpenAILLMService(
                api_key=os.getenv("OPENAI_API_KEY"),
                settings=OpenAILLMService.Settings(
                    model=openai_model,
                    system_instruction=dynamic_system_instruction,
                ),
            )

        function_schemas = [
            FunctionSchema(
                name=item["function"]["name"],
                description=item["function"].get("description", ""),
                properties=item["function"].get("parameters", {}).get("properties", {}),
                required=item["function"].get("parameters", {}).get("required", []),
            )
            for item in TOOL_SCHEMAS
        ]

        context = LLMContext(
            messages=[],
            tools=function_schemas,
        )
        context_aggregator = LLMContextAggregatorPair(context)

        for name, pydantic_cls, handler_func in REGISTERED_TOOLS:
            llm.register_function(
                name,
                _create_pipecat_handler(room_name, pydantic_cls, handler_func),
            )

        register_room_transport(room_name, transport)
        turn_broadcaster = TurnBroadcastProcessor(room_name)

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                context_aggregator.user(),
                llm,
                turn_broadcaster,
                tts,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        worker = PipelineWorker(
            pipeline,
            setup_timeout_secs=60.0,
            start_timeout_secs=60.0,
        )

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport_service, participant):
            await transport_service.capture_participant_transcription(participant["id"])
            context.add_message(
                {
                    "role": "user",
                    "content": "Hello, I have joined the call. Please start the conversation and introduce yourself as Riverline.",
                }
            )
            await pipeline.push_frame(LLMFullResponseStartFrame())

        runner = WorkerRunner()
        await runner.run(worker)

    except Exception as exc:
        logger.error(f"Bot session failed for room {room_url}: {exc}", exc_info=True)
    finally:
        unregister_room_transport(room_name)
