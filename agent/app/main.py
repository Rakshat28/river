"""Minimal FastAPI host for the agent service.

This keeps the backend entrypoint thin while the rest of the agent is built out.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from agent.app.daily_client import create_meeting_token, create_room
except ImportError:  # pragma: no cover - package layout varies by launch context
    from app.daily_client import create_meeting_token, create_room


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://127.0.0.1:3000"],
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


@app.post("/api/session", response_model=SessionResponse)
async def create_session() -> SessionResponse:
    """Create a Daily room and meeting token."""
    try:
        room = await create_room()
        token = await create_meeting_token(room.name, is_owner=True)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Daily room creation failed: {exc}",
        ) from exc

    if room.url is None:
        raise HTTPException(status_code=500, detail="Daily room URL missing")

    return SessionResponse(room_url=room.url, token=token)
