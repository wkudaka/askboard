from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from askboard.ingestion.types import (
    LocaleHints,
    ParseOptions,
    PgType,
    convert,
    infer_column_type,
    infer_semantic_type,
    is_null,
)

US = LocaleHints(decimal_comma=False, dayfirst=True)
BR = LocaleHints(decimal_comma=True, dayfirst=True)


def infer(values, hints=US, forced=None):
    return infer_column_type(values, hints, forced=forced)


# --- nulls -----------------------------------------------------------------

@pytest.mark.parametrize("value", ["", "  ", "NA", "n/a", "NULL", "null", "None", "-", "NaN"])
def test_null_tokens(value):
    assert is_null(value)


@pytest.mark.parametrize("value", ["0", "no", "x", "Nan Goldin"])
def test_non_null_values(value):
    assert not is_null(value)


def test_all_null_column_is_text():
    assert infer(["", "NA", ""]).pg_type is PgType.TEXT


# --- integers / numerics -------------------------------------------------------

def test_integers():
    result = infer(["1", "-20", "300", ""])
    assert result.pg_type is PgType.BIGINT


def test_integers_beyond_bigint_become_numeric():
    assert infer(["1", "99999999999999999999"]).pg_type is PgType.NUMERIC


def test_us_decimals():
    result = infer(["10.5", "1,234.75", "3"])
    assert result.pg_type is PgType.NUMERIC
    assert result.options.decimal == "."


def test_br_decimals():
    result = infer(["10,5", "1.234,75", "3"], hints=US)
    assert result.pg_type is PgType.NUMERIC
    assert result.options.decimal == ","


def test_ambiguous_thousands_follow_locale_hint():
    # "1.234" is 1.234 in US style and 1234 in BR style
    assert infer(["1.234", "2.500"], hints=US).options.decimal == "."
    assert infer(["1.234", "2.500"], hints=BR).options.decimal == ","


def test_ambiguous_br_thousands_without_decimals_is_integer():
    result = infer(["1.234", "2.500"], hints=BR)
    assert result.pg_type is PgType.BIGINT


def test_currency_symbols_are_accepted_and_flagged():
    result = infer(["R$ 1.234,56", "R$ 10,00", "-R$ 5,00"], hints=BR)
    assert result.pg_type is PgType.NUMERIC
    assert result.options.decimal == ","
    assert result.options.currency is True


def test_dollar_amounts():
    result = infer(["$1,200.00", "$15.99"])
    assert result.pg_type is PgType.NUMERIC
    assert result.options.currency is True


def test_mixed_number_and_text_is_text():
    assert infer(["10", "abc", "20"]).pg_type is PgType.TEXT


def test_zip_codes_with_leading_zeros_stay_text():
    assert infer(["01310", "04538", "22041"]).pg_type is PgType.TEXT


# --- booleans --------------------------------------------------------------

@pytest.mark.parametrize("values", [
    ["true", "false", "TRUE"],
    ["yes", "no"],
    ["sim", "não", "Nao"],
    ["Verdadeiro", "Falso"],
])
def test_booleans(values):
    assert infer(values).pg_type is PgType.BOOLEAN


def test_zero_one_columns_are_integers_not_booleans():
    assert infer(["0", "1", "1"]).pg_type is PgType.BIGINT


# --- dates / timestamps ------------------------------------------------------

def test_iso_dates():
    assert infer(["2024-01-15", "2024-12-31"]).pg_type is PgType.DATE


def test_day_first_dates_detected_from_values():
    result = infer(["15/01/2024", "03/02/2024"], hints=LocaleHints(decimal_comma=False, dayfirst=False))
    assert result.pg_type is PgType.DATE
    assert result.options.dayfirst is True


def test_month_first_dates_detected_from_values():
    result = infer(["01/15/2024", "02/03/2024"])
    assert result.pg_type is PgType.DATE
    assert result.options.dayfirst is False


def test_ambiguous_dates_follow_hint():
    assert infer(["01/02/2024"], hints=LocaleHints(False, dayfirst=True)).options.dayfirst is True
    assert infer(["01/02/2024"], hints=LocaleHints(False, dayfirst=False)).options.dayfirst is False


def test_contradictory_dates_are_text():
    assert infer(["15/01/2024", "01/15/2024"]).pg_type is PgType.TEXT


def test_invalid_calendar_dates_are_text():
    assert infer(["2024-02-30"]).pg_type is PgType.TEXT


@pytest.mark.parametrize("values", [
    ["2024-01-15T10:30:00", "2024-01-16 08:00"],
    ["15/01/2024 10:30", "16/01/2024 08:00:59"],
])
def test_timestamps(values):
    assert infer(values).pg_type is PgType.TIMESTAMP


def test_timestamps_with_timezone():
    assert infer(["2024-01-15T10:30:00Z", "2024-01-15T10:30:00-03:00"]).pg_type is PgType.TIMESTAMPTZ


def test_mixed_dates_and_timestamps_are_timestamps():
    assert infer(["2024-01-15", "2024-01-16 08:00"]).pg_type is PgType.TIMESTAMP


# --- forced (user override) ------------------------------------------------

def test_forced_type_computes_matching_parse_options():
    result = infer(["1,5", "abc"], hints=BR, forced=PgType.NUMERIC)
    assert result.pg_type is PgType.NUMERIC
    assert result.options.decimal == ","


def test_forced_text_always_works():
    assert infer(["1", "2"], forced=PgType.TEXT).pg_type is PgType.TEXT


# --- convert -----------------------------------------------------------------

@pytest.mark.parametrize("value, pg_type, options, expected", [
    ("42", PgType.BIGINT, ParseOptions(), 42),
    ("1.234", PgType.BIGINT, ParseOptions(decimal=","), 1234),
    ("1,234.5", PgType.NUMERIC, ParseOptions(decimal="."), Decimal("1234.5")),
    ("R$ 1.234,56", PgType.NUMERIC, ParseOptions(decimal=",", currency=True), Decimal("1234.56")),
    ("-R$ 5,00", PgType.NUMERIC, ParseOptions(decimal=",", currency=True), Decimal("-5.00")),
    ("Sim", PgType.BOOLEAN, ParseOptions(), True),
    ("false", PgType.BOOLEAN, ParseOptions(), False),
    ("15/01/2024", PgType.DATE, ParseOptions(dayfirst=True), date(2024, 1, 15)),
    ("01/15/2024", PgType.DATE, ParseOptions(dayfirst=False), date(2024, 1, 15)),
    ("2024-01-15", PgType.DATE, ParseOptions(), date(2024, 1, 15)),
    ("2024-01-15 10:30", PgType.TIMESTAMP, ParseOptions(), datetime(2024, 1, 15, 10, 30)),
    ("2024-01-15", PgType.TIMESTAMP, ParseOptions(), datetime(2024, 1, 15)),
    ("2024-01-15T10:30:00-03:00", PgType.TIMESTAMPTZ, ParseOptions(),
     datetime(2024, 1, 15, 10, 30, tzinfo=timezone(timedelta(hours=-3)))),
    ("hello", PgType.TEXT, ParseOptions(), "hello"),
    ("", PgType.BIGINT, ParseOptions(), None),
    ("NA", PgType.TEXT, ParseOptions(), None),
])
def test_convert(value, pg_type, options, expected):
    assert convert(value, pg_type, options) == expected


@pytest.mark.parametrize("value, pg_type", [
    ("abc", PgType.BIGINT),
    ("1.5", PgType.BIGINT),
    ("maybe", PgType.BOOLEAN),
    ("2024-13-01", PgType.DATE),
])
def test_convert_raises_on_invalid_values(value, pg_type):
    with pytest.raises(ValueError):
        convert(value, pg_type, ParseOptions())


# --- semantic type -------------------------------------------------------------

@pytest.mark.parametrize("name, pg_type, options, values, expected", [
    ("order_date", PgType.DATE, ParseOptions(), ["2024-01-01"], "temporal"),
    ("created_at", PgType.TIMESTAMP, ParseOptions(), ["2024-01-01 10:00"], "temporal"),
    ("active", PgType.BOOLEAN, ParseOptions(), ["true"], "boolean"),
    ("id", PgType.BIGINT, ParseOptions(), ["1", "2"], "id"),
    ("customer_id", PgType.TEXT, ParseOptions(), ["a1", "b2"], "id"),
    ("codigo_produto", PgType.BIGINT, ParseOptions(), ["10", "20"], "id"),
    ("amount", PgType.NUMERIC, ParseOptions(), ["1.5"], "currency"),
    ("valor_total", PgType.NUMERIC, ParseOptions(), ["1,5"], "currency"),
    ("weight", PgType.NUMERIC, ParseOptions(currency=True), ["$1"], "currency"),
    ("quantity", PgType.BIGINT, ParseOptions(), ["1", "2"], "numeric"),
    ("city", PgType.TEXT, ParseOptions(), ["Recife", "Natal", "Recife", "Natal"] * 10, "categorical"),
    ("comment", PgType.TEXT, ParseOptions(), [f"comment {i}" for i in range(100)], "text"),
])
def test_infer_semantic_type(name, pg_type, options, values, expected):
    assert infer_semantic_type(name, pg_type, options, values) == expected
