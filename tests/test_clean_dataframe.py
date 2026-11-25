"""
Behaviour tests for cleaner.clean_dataframe: the whole-file step that turns a
contact sheet into the WhatsApp upload list, a rejected-rows log and run stats.

All numbers are made up: sequential patterns such as "+971 50 123 4567",
"+971 55 987 6543" and "+971 4 234 5678".
"""

import math

import pandas as pd
import pytest

from cleaner import clean_dataframe


def _reasons(rejected_df):
    return list(rejected_df["Rejection_Reason"])


# ---------- Output shape ----------

def test_output_keeps_every_input_column_in_original_order():
    """The cleaned file mirrors the input columns (names and order); only Mobile is rewritten."""
    df = pd.DataFrame({
        "FirstName": ["Test"], "LastName": ["User"], "Mobile": ["+971 50 123 4567"],
        "JobTitle": ["Tester"], "Country": ["UAE"], "ContactID": ["C-001"],
    })
    cleaned, _, _ = clean_dataframe(df)
    assert list(cleaned.columns) == list(df.columns)
    row = cleaned.iloc[0]
    assert row["Mobile"] == "971501234567"
    assert (row["FirstName"], row["LastName"], row["JobTitle"], row["Country"], row["ContactID"]) == \
        ("Test", "User", "Tester", "UAE", "C-001")


def test_headers_are_matched_case_insensitively():
    """'mobile' / 'COUNTRY' headers are recognised the same as 'Mobile' / 'Country'."""
    df = pd.DataFrame({"mobile": ["050 123 4567"], "COUNTRY": ["UAE"]})
    cleaned, rejected, _ = clean_dataframe(df)
    assert rejected.empty
    assert list(cleaned["mobile"]) == ["971501234567"]


def test_single_column_file_is_treated_as_the_phone_column():
    """A one-column file is cleaned as phone numbers whatever its header says."""
    df = pd.DataFrame({"Numbers to send": ["+971 50 123 4567"]})
    cleaned, rejected, _ = clean_dataframe(df)
    assert rejected.empty
    assert list(cleaned["Numbers to send"]) == ["971501234567"]


# ---------- Mobile vs Phone preference ----------

def test_mobile_is_preferred_when_mobile_and_phone_are_both_valid():
    """When both columns hold valid numbers, the Mobile number is the one sent to WhatsApp."""
    df = pd.DataFrame({"Mobile": ["+971 50 123 4567"], "Phone": ["+971 4 234 5678"]})
    cleaned, _, _ = clean_dataframe(df)
    assert list(cleaned["Mobile"]) == ["971501234567"]


def test_falls_back_to_phone_when_mobile_is_invalid_and_writes_it_to_mobile_column():
    """If Mobile is unusable but Phone is valid, the cleaned Phone number goes into the Mobile column."""
    df = pd.DataFrame({"Mobile": ["n/a"], "Phone": ["+971 4 234 5678"]})
    cleaned, rejected, _ = clean_dataframe(df)
    assert rejected.empty
    assert list(cleaned["Mobile"]) == ["97142345678"]


def test_country_column_is_applied_per_row():
    """Each row's own Country value is used to add the right country code to local numbers."""
    df = pd.DataFrame({
        "Mobile": ["050 123 4567", "(202) 555-0143"],
        "Country": ["United Arab Emirates", "USA"],
    })
    cleaned, rejected, _ = clean_dataframe(df)
    assert rejected.empty
    assert list(cleaned["Mobile"]) == ["971501234567", "12025550143"]


# ---------- Duplicates ----------

def test_numbers_that_are_the_same_after_cleaning_are_deduplicated_keeping_first():
    """Different spellings of one number collapse to a single row; the first occurrence is kept."""
    df = pd.DataFrame({
        "Name": ["first", "second", "third"],
        "Mobile": ["+971 50 123 4567", "00971501234567", "+971 55 987 6543"],
    })
    cleaned, _, stats = clean_dataframe(df)
    assert list(cleaned["Name"]) == ["first", "third"]
    assert stats["duplicates_removed"] == 1


# ---------- Rejection reasons ----------

@pytest.mark.parametrize("mobile", ["", "   ", None, math.nan])
def test_blank_mobile_and_phone_is_rejected_as_blank(mobile):
    """A row with nothing in Mobile or Phone is logged as 'Blank/null phone and mobile'."""
    df = pd.DataFrame({"Mobile": [mobile], "Phone": [""]})
    _, rejected, _ = clean_dataframe(df)
    assert _reasons(rejected) == ["Blank/null phone and mobile"]


@pytest.mark.parametrize("mobile, country, expected_reason", [
    ("n/a", "", "Non-numeric / empty after cleaning"),
    ("+971 50 555 5555", "", "Invalid pattern (repeated digits / sequences / all zeros)"),
    ("12345", "", "Too short to be a valid number"),
    ("+971 50 123", "UAE", "Not a valid phone number for AE"),
    ("050 123 4567", "",
     "Not a valid international phone number (check country code prefix and length)"),
])
def test_rejected_rows_explain_why(mobile, country, expected_reason):
    """Each rejected row carries a human-readable reason matching what was wrong with it."""
    df = pd.DataFrame({"Mobile": [mobile], "Country": [country]})
    cleaned, rejected, _ = clean_dataframe(df)
    assert cleaned.empty
    assert _reasons(rejected) == [expected_reason]


def test_rejected_rows_keep_the_original_raw_values():
    """The rejected log shows the number exactly as it was supplied, plus all other columns."""
    df = pd.DataFrame({"ContactID": ["C-042"], "Mobile": ["12345"], "Country": ["UAE"]})
    _, rejected, _ = clean_dataframe(df)
    row = rejected.iloc[0]
    assert (row["ContactID"], row["Mobile"], row["Country"]) == ("C-042", "12345", "UAE")


# ---------- Summary stats ----------

def test_stats_account_for_every_input_row():
    """input_rows = cleaned + rejected + duplicates removed, and the breakdown counts each reason."""
    df = pd.DataFrame({"Mobile": [
        "+971 50 123 4567",   # cleaned
        "+971 50 123 4567",   # duplicate
        "+971 55 987 6543",   # cleaned
        "",                   # blank
        "12345",              # too short
        "n/a",                # non-numeric
    ]})
    _, _, stats = clean_dataframe(df)
    assert stats["input_rows"] == 6
    assert stats["cleaned_rows"] == 2
    assert stats["rejected_rows"] == 3
    assert stats["duplicates_removed"] == 1
    assert stats["input_rows"] == stats["cleaned_rows"] + stats["rejected_rows"] + stats["duplicates_removed"]
    assert stats["rejection_breakdown"] == {
        "Blank/null phone and mobile": 1,
        "Too short to be a valid number": 1,
        "Non-numeric / empty after cleaning": 1,
    }


def test_clean_file_has_no_rejection_breakdown_or_unknown_countries():
    """When every row is good, stats contain no rejection breakdown and no unknown-country list."""
    df = pd.DataFrame({"Mobile": ["+971 50 123 4567"], "Country": ["UAE"]})
    _, rejected, stats = clean_dataframe(df)
    assert rejected.empty
    assert "rejection_breakdown" not in stats
    assert "unknown_countries" not in stats


def test_unrecognised_country_names_are_reported_once_sorted():
    """Country names missing from COUNTRY_MAP are listed (deduplicated, sorted) so they can be added."""
    df = pd.DataFrame({
        "Mobile": ["+971 50 123 4567", "+971 55 987 6543", "+971 4 234 5678"],
        "Country": ["Atlantis", "El Dorado", "Atlantis"],
    })
    _, _, stats = clean_dataframe(df)
    assert stats["unknown_countries"] == ["Atlantis", "El Dorado"]


@pytest.mark.xfail(reason="An empty (NaN) Country cell is truthy, so 'nan' is reported as an unknown country")
def test_missing_country_cell_is_not_reported_as_unknown_country():
    """A blank Country cell read as NaN (e.g. from Excel) should not appear as unknown country 'nan'."""
    df = pd.DataFrame({"Mobile": ["+971 50 123 4567"], "Country": [math.nan]})
    _, _, stats = clean_dataframe(df)
    assert "unknown_countries" not in stats
