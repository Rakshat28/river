"""Entity resolution and duplicate detection logic."""

import difflib
import re
from typing import Optional

from app.state import Entry

# Filler words to be removed as whole words (not substrings).
_FILLER_WORDS_PATTERN = re.compile(
    r"\b(my|the|a|monthly|payment|subscription|subscriptions)\b", re.IGNORECASE
)


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison by lowercasing, stripping filler words,
    and collapsing extra whitespace.
    """
    name = name.lower()
    name = _FILLER_WORDS_PATTERN.sub("", name)
    return re.sub(r"\s+", " ", name).strip()


def find_near_duplicate(existing_entries: list[Entry], new_name: str) -> Optional[str]:
    """Find a near-duplicate entry by comparing normalized names using SequenceMatcher.

    Returns the ID of the highest-matching existing entry if its similarity ratio
    is >= 0.75. Ties are broken by the order of entries in the list (earliest created).
    """
    normalized_new = _normalize_name(new_name)
    best_match_id = None
    highest_ratio = -1.0

    threshold = 0.75

    for entry in existing_entries:
        normalized_existing = _normalize_name(entry.name)
        ratio = difflib.SequenceMatcher(
            None, normalized_new, normalized_existing
        ).ratio()

        # > highest_ratio ensures ties are broken by the earliest entry evaluated
        if ratio >= threshold and ratio > highest_ratio:
            highest_ratio = ratio
            best_match_id = entry.id

    return best_match_id
