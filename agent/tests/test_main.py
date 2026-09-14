"""Unit tests for agent/app/main.py REST API endpoints."""

import sys
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from agent.app.main import app
    from agent.app.session_store import get_or_create
    from agent.app.state import Entry, FieldHistory
except ImportError:
    from app.main import app
    from app.session_store import get_or_create
    from app.state import Entry, FieldHistory


class TestStateRESTEndpoint:
    def test_get_state_returns_404_for_nonexistent_room(self):
        """Step 5.3 Acceptance check: Nonexistent room returns 404 with JSON error body."""
        client = TestClient(app)
        response = client.get("/api/state/room-that-does-not-exist-xyz")
        assert response.status_code == 404
        json_data = response.json()
        assert "detail" in json_data
        assert "error" in json_data["detail"]

    def test_get_state_returns_full_session_state_including_history(self):
        """Step 5.3 Acceptance check: Returns full SessionState snapshot including history."""
        room_name = "test-rest-state-room-1"
        room_session = get_or_create(room_name, date(2026, 9, 14))

        history_item = FieldHistory(
            amount_paise=1000000,
            confidence="confirmed",
            turn_index=0,
            timestamp="2026-09-14T12:00:00Z",
        )
        current_item = FieldHistory(
            amount_paise=1200000,
            confidence="confirmed",
            turn_index=1,
            timestamp="2026-09-14T12:05:00Z",
        )

        entry = Entry(
            name="Salary",
            current=current_item,
            history=[history_item],
        )
        room_session.state.income.append(entry)

        client = TestClient(app)
        response = client.get(f"/api/state/{room_name}")

        assert response.status_code == 200
        data = response.json()
        assert data["room_name"] == room_name
        assert len(data["income"]) == 1

        fetched_entry = data["income"][0]
        assert fetched_entry["name"] == "Salary"
        assert fetched_entry["current"]["amount_paise"] == 1200000
        # Critical assertion: REST snapshot MUST include history
        assert len(fetched_entry["history"]) == 1
        assert fetched_entry["history"][0]["amount_paise"] == 1000000
