"""Pipecat pipeline construction and wiring.

This module sets up the real-time voice loop using Daily for WebRTC transport,
Deepgram for STT, OpenAI for the LLM, and Cartesia for TTS.
"""

import logging
import os

from pipecat.pipeline.pipeline import Pipeline
from pipecat.workers.runner import WorkerRunner
from pipecat.pipeline.worker import PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.tts_service import TextAggregationMode
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.google.llm import GoogleLLMService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

logger = logging.getLogger(__name__)


async def run_bot(room_url: str, token: str) -> None:
    """Construct and run the minimal Pipecat voice pipeline for testing."""
    try:
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
            settings=CartesiaTTSService.Settings(
                voice="f8f5f1b2-f02d-4d8e-a40d-fd850a487b3d", #using Kiara's voice cause why not
                text_aggregation_mode=TextAggregationMode.TOKEN,
            )
        )
        llm = GoogleLLMService(
            api_key=os.getenv("GOOGLE_API_KEY"), 
            settings=GoogleLLMService.Settings(
                model="gemini-3.6-flash",
                system_instruction="You are a test assistant. Briefly acknowledge what the user just said, nothing else."
            )
        )

        context = LLMContext(
            messages=[
                {
                    "role": "system",
                    "content": "You are a test assistant. Briefly acknowledge what the user just said, nothing else.",
                }
            ]
        )
        context_aggregator = LLMContextAggregatorPair(context)

        pipeline = Pipeline(
            [
                transport.input(),
                stt,
                context_aggregator.user(),
                llm,
                tts,
                transport.output(),
                context_aggregator.assistant(),
            ]
        )

        worker = PipelineWorker(pipeline)

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport_service, participant):
           await transport_service.capture_participant_transcription(participant["id"])

        runner = WorkerRunner()
        await runner.run(worker)

    except Exception as exc:
        logger.error(f"Bot session failed for room {room_url}: {exc}", exc_info=True)