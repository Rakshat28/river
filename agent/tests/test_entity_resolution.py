"""Unit tests for agent/app/entity_resolution.py."""

import difflib
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure agent module is accessible when pytest is run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.entity_resolution import _normalize_name, find_near_duplicate
from app.state import Entry, FieldHistory


def _mock_entry(name: str, entry_id: str) -> Entry:
    """Helper to create a valid Entry object for testing."""
    history = FieldHistory(
        amount_paise=100000,
        confidence="confirmed",
        turn_index=0,
        timestamp=datetime.now(timezone.utc),
    )
    return Entry(id=entry_id, name=name, current=history)


class TestEntityResolution:
    def test_normalization_removes_filler_words_as_whole_words(self):
        assert _normalize_name("My monthly rent payment") == "rent"
        assert _normalize_name("The Netflix A") == "netflix"
        # Must not remove substrings (e.g., 'a' inside 'salary', 'the' inside 'other')
        assert _normalize_name("A salary") == "salary"
        assert _normalize_name("other payment") == "other"

    def test_rent_vs_house_rent(self):

        entries = [_mock_entry("House Rent", "entry_house")]

        # Verify the actual ratio logic documented above
        norm_new = _normalize_name("Rent")
        norm_exist = _normalize_name(entries[0].name)
        ratio = difflib.SequenceMatcher(None, norm_new, norm_exist).ratio()
        assert round(ratio, 3) == 0.571

        result = find_near_duplicate(entries, "Rent")
        assert result is None

    def test_netflix_vs_spotify(self):
        entries = [_mock_entry("Spotify subscription", "entry_spot")]

        norm_new = _normalize_name("Netflix subscription")
        norm_exist = _normalize_name(entries[0].name)
        ratio = difflib.SequenceMatcher(None, norm_new, norm_exist).ratio()
        # 'netflix' (7 chars) vs 'spotify' (7 chars), matches 't' and 'f' (2 chars)
        # Ratio = 2 * 2 / 14 = 0.286
        assert round(ratio, 2) == 0.29

        result = find_near_duplicate(entries, "Netflix subscription")
        assert result is None

    def test_credit_card_known_false_positive(self):
        # KNOWN FALSE-POSITIVE RISK:
        # Number-suffixed items that share a long common prefix will have extremely
        # high similarity ratios and trigger a false-positive duplicate detection.
        # This is an accepted trade-off of the heuristic per implementation-plan.md Section 13.3.
        entries = [_mock_entry("Credit card 2", "entry_cc2")]

        norm_new = _normalize_name("Credit card 1")
        norm_exist = _normalize_name(entries[0].name)
        ratio = difflib.SequenceMatcher(None, norm_new, norm_exist).ratio()
        # len('credit card 1') = 13, match is 'credit card ' (12)
        # Ratio = 2 * 12 / 26 = 0.923
        assert round(ratio, 3) == 0.923

        result = find_near_duplicate(entries, "Credit card 1")
        assert result == "entry_cc2"

    def test_filler_word_stripping_causes_exact_match(self):
        entries = [_mock_entry("Rent", "entry_rent")]

        norm_new = _normalize_name("My rent")
        norm_exist = _normalize_name(entries[0].name)
        ratio = difflib.SequenceMatcher(None, norm_new, norm_exist).ratio()

        assert ratio == 1.0  # Both normalize down to "rent"
        result = find_near_duplicate(entries, "My rent")
        assert result == "entry_rent"
