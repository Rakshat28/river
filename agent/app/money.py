"""Money handling"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

_PAISE_PER_RUPEE = Decimal(100)
_ONE = Decimal("1")

# Strips thousands separators (commas) and any surrounding/interior
# whitespace out of a user-typed rupee string before parsing.
_STRIP_PATTERN = re.compile(r"[,\s]")


def rupees_to_paise(rupees: str | float) -> int:
    """Convert a rupee amount to an integer number of paise.

    Accepts a string (comma-separated thousands allowed, e.g. '15,000.50')
    or a float. Rounds to the nearest paisa using ROUND_HALF_UP. `Decimal`
    is used internally only — it never escapes this function; the return
    value is always a plain `int`.

    Raises:
        ValueError: the input is a string/float that isn't a valid number.
        TypeError: the input isn't a str or float at all.
    """
    if isinstance(rupees, bool):
        # bool is a subclass of int; neither str nor float, so reject it
        # explicitly rather than silently treating True as 1.
        raise TypeError(f"rupees must be str or float, got {type(rupees).__name__}")

    if isinstance(rupees, str):
        cleaned = _STRIP_PATTERN.sub("", rupees.strip())
        if cleaned == "":
            raise ValueError("invalid rupee amount: empty string")
        source = cleaned
    elif isinstance(rupees, float):
        # str(float) round-trips to the shortest decimal that reproduces
        # the float exactly, avoiding binary-float artifacts (e.g. the
        # 0.1 -> 0.1000000000000000055... problem) leaking into Decimal.
        source = str(rupees)
    else:
        raise TypeError(f"rupees must be str or float, got {type(rupees).__name__}")

    try:
        decimal_rupees = Decimal(source)
    except InvalidOperation as exc:
        raise ValueError(f"invalid rupee amount: {rupees!r}") from exc

    if not decimal_rupees.is_finite():
        raise ValueError(f"invalid rupee amount: {rupees!r}")

    paise = (decimal_rupees * _PAISE_PER_RUPEE).quantize(_ONE, rounding=ROUND_HALF_UP)
    return int(paise)


def _group_indian_digits(digits: str) -> str:
    """Comma-group a non-negative digit string using the Indian numbering
    system (last 3 digits, then groups of 2: '1234567' -> '12,34,567')."""
    if len(digits) <= 3:
        return digits
    head, tail = digits[:-3], digits[-3:]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def paise_to_rupees_display(paise: int) -> str:
    """Render a paise amount as a human-readable rupee string for the UI.

    Whole-rupee amounts show no decimal places ('₹15,000'); anything with a
    fractional paise component shows exactly two ('₹15,000.50'). Uses Indian
    digit grouping (lakh/crore), not Western thousands grouping.
    """
    if not isinstance(paise, int) or isinstance(paise, bool):
        raise TypeError(f"paise must be an int, got {type(paise).__name__}")

    sign = "-" if paise < 0 else ""
    whole_rupees, remainder_paise = divmod(abs(paise), 100)
    grouped = _group_indian_digits(str(whole_rupees))

    if remainder_paise == 0:
        return f"{sign}\u20b9{grouped}"
    return f"{sign}\u20b9{grouped}.{remainder_paise:02d}"


def paise_to_rupees_float(paise: int) -> float:
    """Convert paise to a rupee float, for display-only contexts (e.g. a
    charting library's y-axis) that cannot accept an int/Decimal.

    WARNING: never use this value for arithmetic, comparisons, storage, or
    re-derivation of any financial fact. Floats lose precision and can
    silently drift over repeated operations; all money math elsewhere in
    the codebase must stay in integer paise (see AGENTS.md Section 1,
    invariant 1). This function exists solely to hand a number to code that
    is not ours and only understands float, at the moment of rendering.
    """
    if not isinstance(paise, int) or isinstance(paise, bool):
        raise TypeError(f"paise must be an int, got {type(paise).__name__}")
    return paise / 100
