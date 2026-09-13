"""Helpers for creating Daily rooms and meeting tokens.

These functions intentionally isolate the REST API calls so the rest of the agent
can consume typed models without wiring raw HTTP directly into higher-level code.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from urllib import request

from pydantic import BaseModel, ConfigDict


class DailyRoom(BaseModel):
    """Typed Daily room payload returned by the room-creation REST endpoint."""

    name: str
    url: str | None = None
    created_at: datetime | None = None
    config: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


def _daily_api_key() -> str:
    """Return the configured Daily API key or raise a clear runtime error."""
    api_key = os.getenv("DAILY_API_KEY")
    if not api_key:
        raise RuntimeError("DAILY_API_KEY is not set.")
    return api_key


def _request_json(
    method: str, url: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Send a JSON request to the Daily REST API and decode the response."""
    headers = {
        "Authorization": f"Bearer {_daily_api_key()}",
        "Content-Type": "application/json",
    }
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers=headers, method=method)

    try:
        with request.urlopen(req, timeout=30) as response:
            raw_body = response.read()
    except Exception as exc:  # pragma: no cover - exercised via mocked HTTP in tests
        raise RuntimeError(f"Daily API request failed for {url}: {exc}") from exc

    if not raw_body:
        return {}

    decoded = raw_body.decode("utf-8")
    parsed = json.loads(decoded)
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("Daily API response was not a JSON object.")


async def create_room() -> DailyRoom:
    """Create a Daily room and return the typed room metadata."""
    payload = {
        "properties": {
            "enable_chat": True,
            "enable_recording": False,
            "start_video_off": True,
            "start_audio_off": False,
        }
    }
    response = _request_json("POST", "https://api.daily.co/v1/rooms", payload)

    room_name = response.get("name")
    if not room_name:
        raise ValueError("Daily room creation response did not include a room name.")

    created_at_value = response.get("created_at")
    created_at: datetime | None = None
    if isinstance(created_at_value, str):
        created_at = datetime.fromisoformat(created_at_value.replace("Z", "+00:00"))

    return DailyRoom(
        name=str(room_name),
        url=response.get("url"),
        created_at=created_at,
        config=(
            response.get("config") if isinstance(response.get("config"), dict) else None
        ),
        **{
            key: value
            for key, value in response.items()
            if key not in {"name", "url", "created_at", "config"}
        },
    )


async def create_meeting_token(room_name: str, is_owner: bool = False) -> str:
    """Create a Daily meeting token for a specific room and role."""
    payload = {
        "properties": {
            "room_name": room_name,
            "is_owner": is_owner,
            "enable_recording": False,
        }
    }
    response = _request_json("POST", "https://api.daily.co/v1/meeting-tokens", payload)

    token = response.get("token")
    if not isinstance(token, str) or not token:
        raise ValueError("Daily token response did not include a valid token.")
    return token
