"""Exhaustive unit tests for agent/app/money.py.

These are the highest-priority tests for this module: every money bug in
the rest of the codebase (rounding drift, precision loss, Decimal/float
escaping into places that expect a plain int) is supposed to be impossible
because this module is the only place that ever touches Decimal, and it is
tested exhaustively here.
"""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

# agent/app is a namespace package (no __init__.py) rooted at agent/, which
# isn't necessarily on sys.path when pytest is invoked from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.money import (  # noqa: E402
    paise_to_rupees_display,
    paise_to_rupees_float,
    rupees_to_paise,
)


class TestRupeesToPaiseFromString:
    def test_plain_integer_string(self):
        assert rupees_to_paise("15000") == 1500000

    def test_comma_separated_string(self):
        assert rupees_to_paise("15,000.50") == 1500050

    def test_zero_string(self):
        assert rupees_to_paise("0") == 0

    def test_rounds_up_at_exact_half_paisa(self):
        # 15000.505 rupees -> 1500050.5 paise -> rounds up (ROUND_HALF_UP)
        assert rupees_to_paise("15,000.505") == 1500051

    def test_rounds_down_below_half_paisa(self):
        # 15000.504 rupees -> 1500050.4 paise -> rounds down
        assert rupees_to_paise("15,000.504") == 1500050

    def test_indian_style_multi_comma_grouping(self):
        # '1,00,000' (Indian grouping) should parse the same as '100000'
        assert rupees_to_paise("1,00,000") == 10000000

    def test_leading_and_trailing_whitespace(self):
        assert rupees_to_paise("  15000  ") == 1500000

    def test_single_decimal_digit(self):
        assert rupees_to_paise("15000.5") == 1500050

    def test_negative_string(self):
        assert rupees_to_paise("-500") == -50000

    def test_small_fraction_string(self):
        assert rupees_to_paise("0.01") == 1

    def test_sub_paisa_fraction_rounds(self):
        # 0.004 rupees = 0.4 paise -> rounds down to 0
        assert rupees_to_paise("0.004") == 0
        # 0.005 rupees = 0.5 paise -> rounds up (half-up) to 1
        assert rupees_to_paise("0.005") == 1

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            rupees_to_paise("")

    def test_whitespace_only_string_raises(self):
        with pytest.raises(ValueError):
            rupees_to_paise("   ")

    def test_garbage_string_raises(self):
        with pytest.raises(ValueError):
            rupees_to_paise("not a number")

    def test_multiple_decimal_points_raises(self):
        with pytest.raises(ValueError):
            rupees_to_paise("15.00.50")

    def test_currency_symbol_raises(self):
        with pytest.raises(ValueError):
            rupees_to_paise("₹15000")


class TestRupeesToPaiseFromFloat:
    def test_whole_number_float(self):
        assert rupees_to_paise(15000.0) == 1500000

    def test_half_rupee_float(self):
        assert rupees_to_paise(15000.5) == 1500050

    def test_zero_float(self):
        assert rupees_to_paise(0.0) == 0

    def test_negative_float(self):
        assert rupees_to_paise(-500.25) == -50025

    def test_float_binary_imprecision_does_not_leak(self):
        # 0.1 + 0.2 == 0.30000000000000004 in binary float; str(float)
        # round-tripping through Decimal must not let that leak through.
        assert rupees_to_paise(0.1 + 0.2) == 30

    def test_nan_float_raises(self):
        with pytest.raises(ValueError):
            rupees_to_paise(float("nan"))

    def test_infinite_float_raises(self):
        with pytest.raises(ValueError):
            rupees_to_paise(float("inf"))


class TestRupeesToPaiseTypeErrors:
    def test_int_input_raises_type_error(self):
        # Deliberately not accepted: forces callers to be explicit about
        # str vs float rather than relying on implicit int->float coercion.
        with pytest.raises(TypeError):
            rupees_to_paise(15000)  # type: ignore[arg-type]

    def test_bool_input_raises_type_error(self):
        with pytest.raises(TypeError):
            rupees_to_paise(True)  # type: ignore[arg-type]

    def test_none_input_raises_type_error(self):
        with pytest.raises(TypeError):
            rupees_to_paise(None)  # type: ignore[arg-type]


class TestRupeesToPaiseReturnType:
    def test_return_type_is_plain_int_not_decimal(self):
        result = rupees_to_paise("15000")
        assert type(result) is int
        assert not isinstance(result, Decimal)


class TestPaiseToRupeesDisplay:
    def test_whole_rupees_no_decimals(self):
        assert paise_to_rupees_display(1500000) == "\u20b915,000"

    def test_fractional_paise_two_decimals(self):
        assert paise_to_rupees_display(1500050) == "\u20b915,000.50"

    def test_zero(self):
        assert paise_to_rupees_display(0) == "\u20b90"

    def test_single_digit_paise_is_zero_padded(self):
        assert paise_to_rupees_display(1500005) == "\u20b915,000.05"

    def test_small_amount_no_grouping_needed(self):
        assert paise_to_rupees_display(500) == "\u20b95"

    def test_hundreds_no_comma(self):
        assert paise_to_rupees_display(90000) == "\u20b9900"

    def test_lakh_uses_indian_grouping(self):
        assert paise_to_rupees_display(10000000) == "\u20b91,00,000"

    def test_crore_uses_indian_grouping(self):
        assert paise_to_rupees_display(1000000000) == "\u20b91,00,00,000"

    def test_negative_amount(self):
        assert paise_to_rupees_display(-1500000) == "-\u20b915,000"

    def test_return_type_is_str(self):
        assert isinstance(paise_to_rupees_display(1500000), str)

    def test_non_int_raises_type_error(self):
        with pytest.raises(TypeError):
            paise_to_rupees_display(15000.0)  # type: ignore[arg-type]

    def test_bool_raises_type_error(self):
        with pytest.raises(TypeError):
            paise_to_rupees_display(True)  # type: ignore[arg-type]


class TestPaiseToRupeesFloat:
    def test_whole_rupees(self):
        assert paise_to_rupees_float(1500000) == 15000.0

    def test_fractional_rupees(self):
        assert paise_to_rupees_float(1500050) == 15000.5

    def test_zero(self):
        assert paise_to_rupees_float(0) == 0.0

    def test_negative(self):
        assert paise_to_rupees_float(-50025) == -500.25

    def test_return_type_is_plain_float(self):
        result = paise_to_rupees_float(1500000)
        assert type(result) is float

    def test_non_int_raises_type_error(self):
        with pytest.raises(TypeError):
            paise_to_rupees_float("1500000")  # type: ignore[arg-type]

    def test_bool_raises_type_error(self):
        with pytest.raises(TypeError):
            paise_to_rupees_float(False)  # type: ignore[arg-type]


class TestRoundTrip:
    def test_string_round_trip_whole_rupees(self):
        paise = rupees_to_paise("15000")
        assert paise_to_rupees_display(paise) == "\u20b915,000"

    def test_string_round_trip_with_paise(self):
        paise = rupees_to_paise("15000.50")
        assert paise_to_rupees_display(paise) == "\u20b915,000.50"