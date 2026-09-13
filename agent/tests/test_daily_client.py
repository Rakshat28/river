import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from agent.app.daily_client import DailyRoom, create_meeting_token, create_room


@patch.dict("os.environ", {"DAILY_API_KEY": "test-key"}, clear=False)
@patch("agent.app.daily_client.request.urlopen")
def test_create_room_returns_typed_room(mock_urlopen):
    inner_response = MagicMock()
    inner_response.read.return_value = json.dumps(
        {
            "name": "room-123",
            "url": "https://example.daily.co/room-123",
            "created_at": "2026-09-13T12:00:00Z",
            "config": {"enable_chat": True},
            "privacy": "private",
        }
    ).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = inner_response

    room = asyncio.run(create_room())

    assert isinstance(room, DailyRoom)
    assert room.name == "room-123"
    assert room.url == "https://example.daily.co/room-123"
    assert room.config == {"enable_chat": True}
    assert room.privacy == "private"

    request_obj = mock_urlopen.call_args.args[0]
    assert request_obj.full_url == "https://api.daily.co/v1/rooms"
    assert request_obj.headers["Authorization"] == "Bearer test-key"
    assert request_obj.headers.get("Content-type") == "application/json"


@patch.dict("os.environ", {"DAILY_API_KEY": "test-key"}, clear=False)
@patch("agent.app.daily_client.request.urlopen")
def test_create_meeting_token_returns_token(mock_urlopen):
    inner_response = MagicMock()
    inner_response.read.return_value = json.dumps({"token": "token-abc"}).encode(
        "utf-8"
    )
    mock_urlopen.return_value.__enter__.return_value = inner_response

    token = asyncio.run(create_meeting_token("room-123", is_owner=True))

    assert token == "token-abc"
    request_obj = mock_urlopen.call_args.args[0]
    assert request_obj.full_url == "https://api.daily.co/v1/meeting-tokens"
    assert request_obj.headers["Authorization"] == "Bearer test-key"


@patch.dict("os.environ", {}, clear=True)
def test_create_room_requires_api_key():
    with pytest.raises(RuntimeError, match="DAILY_API_KEY"):
        asyncio.run(create_room())
