"""
Behaviour tests for cleaner.validate_and_clean: the single-number normaliser that
every contact row passes through before it goes into the WhatsApp upload file.

All numbers are made up: sequential "123 4567" / "98765 43210" patterns and the
US fictional 555-01xx range.
"""

import math

import pytest

from cleaner import validate_and_clean


# ---------- Normalisation into WhatsApp format ----------

def test_international_number_becomes_digits_only_without_plus():
    """A +<country code> number is output as plain digits, no '+' or spaces (WhatsApp format)."""
    assert validate_and_clean("+971 50 123 4567", None) == "971501234567"


@pytest.mark.parametrize("raw", [
    "+971 (50) 123-4567",
    "+971-50-123-4567",
    "+971.50.123.4567",
])
def test_brackets_dashes_and_dots_are_stripped(raw):
    """Common punctuation (brackets, dashes, dots) does not stop a number from being cleaned."""
    assert validate_and_clean(raw, None) == "971501234567"


def test_leading_zero_national_number_gets_country_code_from_hint():
    """A local number with a trunk '0' is converted to international form using the Country hint."""
    assert validate_and_clean("050 123 4567", "AE") == "971501234567"


def test_national_number_without_leading_zero_uses_country_hint():
    """A local number typed without the trunk '0' still gets the hinted country code."""
    assert validate_and_clean("501234567", "AE") == "971501234567"


def test_us_bracketed_area_code_with_us_hint():
    """US-style '(202) 555-0143' with a US hint becomes 1 + 10 digits."""
    assert validate_and_clean("(202) 555-0143", "US") == "12025550143"


def test_international_digits_without_plus_are_auto_detected():
    """With no Country column, digits that start with a country code are auto-detected."""
    assert validate_and_clean("971501234567", None) == "971501234567"


def test_explicit_plus_prefix_wins_over_wrong_country_hint():
    """If the Country column is wrong but the number has '+<code>', the number's own code is kept."""
    assert validate_and_clean("+971 50 123 4567", "GB") == "971501234567"


def test_numeric_cell_from_spreadsheet_is_accepted():
    """A number read from Excel as an integer (no '+') is cleaned like its string form."""
    assert validate_and_clean(971501234567, None) == "971501234567"


def test_country_code_digits_do_not_trigger_repeated_pair_rejection():
    """Repeated-digit checks look at the subscriber part only, so '+91 91…' is not seen as '9191' junk."""
    assert validate_and_clean("+91 91234 56789", None) == "919123456789"


# ---------- Rejections ----------

@pytest.mark.parametrize("raw", ["", "   ", None, math.nan])
def test_blank_or_missing_values_are_rejected(raw):
    """Empty, whitespace-only, None and NaN cells produce no number."""
    assert validate_and_clean(raw, "AE") is None


def test_non_numeric_text_is_rejected():
    """Free text such as 'n/a' is not a phone number."""
    assert validate_and_clean("n/a", None) is None


def test_local_number_without_country_hint_is_rejected():
    """A local '0…' number cannot be guessed without a Country, so it is rejected rather than mis-assigned."""
    assert validate_and_clean("050 123 4567", None) is None


def test_too_short_number_is_rejected():
    """A number missing digits for its country is rejected."""
    assert validate_and_clean("+971 50 123", None) is None


def test_run_of_five_identical_digits_is_rejected_as_junk():
    """Subscriber numbers containing 5+ identical digits in a row (e.g. 55555) are treated as fake."""
    assert validate_and_clean("+971 50 555 5555", None) is None


def test_repeated_digit_pair_is_rejected_as_junk():
    """Subscriber numbers with a repeating 2-digit block (e.g. 121212) are treated as fake."""
    assert validate_and_clean("+971 50 121 2121", None) is None


# ---------- Suspected bug ----------

@pytest.mark.xfail(
    strict=True,
    reason="'00' international dialling prefix is not recognised without a Country hint: "
           "'00971…' becomes '+00971…' and fails to parse.",
)
def test_double_zero_international_prefix_is_auto_detected():
    """'00<country code>…' is a standard international format and should be cleaned without a Country hint."""
    assert validate_and_clean("00971501234567", None) == "971501234567"
