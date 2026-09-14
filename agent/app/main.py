"""Minimal FastAPI host for the agent service.

This keeps the backend entrypoint thin while the rest of the agent is built out.
"""

import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

try:
    from agent.app.daily_client import create_meeting_token, create_room
    from agent.app.bot import run_bot
    from agent.app.session_store import locked_state
    from agent.app.state import SessionState
except ImportError:  # pragma: no cover - package layout varies by launch context
    from app.daily_client import create_meeting_token, create_room
    from app.bot import run_bot
    from app.session_store import locked_state
    from app.state import SessionState


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SessionResponse(BaseModel):
    """Response payload returned after creating a Daily room and token."""

    room_url: str
    token: str


@app.get("/health")
def health() -> dict[str, str]:
    """Return a simple liveness response for the agent process."""
    return {"status": "ok"}


active_bot_tasks = set()


@app.post("/api/session", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    """Create a Daily room and meeting token."""
    try:
        room = await create_room()
        user_token = await create_meeting_token(room.name, is_owner=True)
        bot_token = await create_meeting_token(room.name, is_owner=True)
    except (RuntimeError, ValueError) as exc:
        logger.error(f"Failed to create Daily resources : {exc}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Daily room creation failed: {exc}",
        ) from exc

    if room.url is None:
        raise HTTPException(status_code=500, detail="Daily room URL missing")

    async def _bot_task_wrapper(url: str, token: str) -> None:
        """Wrap the bot execution to prevent silent backround task crashes"""
        try:
            logger.info(f"Spawning bot task for room: {url}")
            await run_bot(url, token)
        except Exception as exc:
            logger.error(f"Bot background task crashed for {url}: {exc}", exc_info=True)

    task = asyncio.create_task(_bot_task_wrapper(room.url, bot_token))
    active_bot_tasks.add(task)
    task.add_done_callback(active_bot_tasks.discard)
    return SessionResponse(room_url=room.url, token=user_token)


@app.get("/api/state/{room_name}", response_model=SessionState)
async def get_state(room_name: str) -> SessionState:
    """Return the FULL current SessionState snapshot for a room (including history)."""
    try:
        async with locked_state(room_name) as state:
            return state
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Room '{room_name}' not found"},
        ) from exc
