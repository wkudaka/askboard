"""Column type inference and value conversion for CSV ingestion.

Inference runs over every value of a column (files are capped by MAX_UPLOAD_MB), so a
type is only chosen when *all* non-null values fit it. Ambiguities that values alone
cannot settle ("1.234": 1.234 or 1234? "01/02/2024": Jan 2 or Feb 1?) follow the
`LocaleHints` of the file.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class PgType(StrEnum):
    BOOLEAN = "boolean"
    BIGINT = "bigint"
    NUMERIC = "numeric"
    DATE = "date"
    TIMESTAMP = "timestamp"
    TIMESTAMPTZ = "timestamptz"
    TEXT = "text"


TEMPORAL_TYPES = frozenset({PgType.DATE, PgType.TIMESTAMP, PgType.TIMESTAMPTZ})
NUMBER_TYPES = frozenset({PgType.BIGINT, PgType.NUMERIC})


@dataclass(frozen=True)
class LocaleHints:
    decimal_comma: bool = False  # "1.234,56" style when values are ambiguous
    dayfirst: bool = True  # "01/02/2024" = 1 Feb when values are ambiguous


@dataclass(frozen=True)
class ParseOptions:
    decimal: str = "."
    dayfirst: bool = True
    currency: bool = False


@dataclass(frozen=True)
class InferredType:
    pg_type: PgType
    options: ParseOptions


# --- nulls ---------------------------------------------------------------------

NULL_TOKENS = frozenset({"", "na", "n/a", "null", "none", "-", "nan"})


def is_null(value: str) -> bool:
    return value.strip().lower() in NULL_TOKENS


# --- booleans -----------------------------------------------------------------

TRUE_TOKENS = frozenset({"true", "yes", "sim", "verdadeiro"})
FALSE_TOKENS = frozenset({"false", "no", "não", "nao", "falso"})


def _parse_bool(value: str) -> bool:
    token = value.strip().lower()
    if token in TRUE_TOKENS:
        return True
    if token in FALSE_TOKENS:
        return False
    raise ValueError(f"Not a boolean: {value!r}")


# --- numbers ------------------------------------------------------------------

_CURRENCY = re.compile(r"^(?P<sign>[+-])?\s*(?:R\$|US\$|\$|€|£)\s*(?P<rest>.+)$")
_NUMBER = {
    ".": re.compile(r"^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$"),
    ",": re.compile(r"^[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$"),
}
_LEADING_ZERO = re.compile(r"^[+-]?0\d")  # zip codes, ids: "01310"
_BIGINT_MAX = 2**63 - 1


def _strip_currency(value: str) -> tuple[str, bool]:
    text = value.strip()
    match = _CURRENCY.match(text)
    if not match:
        return text, False
    return (match["sign"] or "") + match["rest"].strip(), True


def _matches(number_text: str, decimal: str) -> bool:
    return bool(_NUMBER[decimal].match(number_text)) and not _LEADING_ZERO.match(number_text)


def _parse_number(value: str, decimal: str) -> tuple[Decimal, bool]:
    """Returns (number, has_fraction_part)."""
    text, _ = _strip_currency(value)
    if not _matches(text, decimal):
        raise ValueError(f"Not a number: {value!r}")
    thousands = "," if decimal == "." else "."
    has_fraction = decimal in text
    try:
        return Decimal(text.replace(thousands, "").replace(decimal, ".")), has_fraction
    except InvalidOperation:
        raise ValueError(f"Not a number: {value!r}") from None


def _number_type(values: Sequence[str], hints: LocaleHints, *, strict: bool) -> InferredType | None:
    stripped = [_strip_currency(v) for v in values]
    texts = [t for t, _ in stripped]
    currency = any(has for _, has in stripped)

    us = sum(_matches(t, ".") for t in texts)
    br = sum(_matches(t, ",") for t in texts)
    preferred = "," if hints.decimal_comma else "."

    if strict:
        us_ok, br_ok = us == len(texts), br == len(texts)
        if not (us_ok or br_ok):
            return None
        decimal = preferred if us_ok and br_ok else ("." if us_ok else ",")
    else:
        decimal = preferred if us == br else ("." if us > br else ",")

    options = ParseOptions(decimal=decimal, currency=currency)
    parsed = []
    for t in texts:
        try:
            parsed.append(_parse_number(t, decimal))
        except ValueError:
            continue
    is_integer = all(not has_fraction for _, has_fraction in parsed)
    fits_bigint = all(abs(n) <= _BIGINT_MAX for n, _ in parsed)
    pg_type = PgType.BIGINT if is_integer and fits_bigint else PgType.NUMERIC
    return InferredType(pg_type, options)


# --- dates & timestamps -----------------------------------------------------------

_ISO = re.compile(
    r"^(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"
    r"(?:[T ](?P<H>\d{2}):(?P<M>\d{2})(?::(?P<S>\d{2})(?:\.(?P<f>\d{1,6}))?)?"
    r"(?P<tz>Z|[+-]\d{2}:?\d{2})?)?$"
)
_DMY = re.compile(
    r"^(?P<a>\d{1,2})[/.-](?P<b>\d{1,2})[/.-](?P<y>\d{4})"
    r"(?:[ T](?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?$"
)


@dataclass(frozen=True)
class _Temporal:
    value: datetime
    has_time: bool
    has_tz: bool


def _tz(text: str) -> timezone:
    if text == "Z":
        return timezone.utc
    sign = -1 if text[0] == "-" else 1
    digits = text[1:].replace(":", "")
    return timezone(sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:])))


def _parse_temporal(value: str, dayfirst: bool) -> _Temporal:
    text = value.strip()
    if match := _ISO.match(text):
        year, month, day = int(match["y"]), int(match["m"]), int(match["d"])
    elif match := _DMY.match(text):
        a, b = int(match["a"]), int(match["b"])
        day, month = (a, b) if dayfirst else (b, a)
        year = int(match["y"])
    else:
        raise ValueError(f"Not a date: {value!r}")

    groups = match.groupdict()
    has_time = groups.get("H") is not None
    tz_text = groups.get("tz")
    micro = int((groups.get("f") or "0").ljust(6, "0"))
    result = datetime(  # raises ValueError for impossible dates (Feb 30, month 13)
        year, month, day,
        int(groups.get("H") or 0), int(groups.get("M") or 0), int(groups.get("S") or 0), micro,
        tzinfo=_tz(tz_text) if tz_text else None,
    )
    return _Temporal(result, has_time, tz_text is not None)


def _dayfirst_evidence(values: Sequence[str]) -> tuple[int, int]:
    """Counts values that are only valid day-first / only valid month-first."""
    day, month = 0, 0
    for v in values:
        if match := _DMY.match(v.strip()):
            a, b = int(match["a"]), int(match["b"])
            day += a > 12
            month += b > 12
    return day, month


def _temporal_type(values: Sequence[str], hints: LocaleHints, *, strict: bool) -> InferredType | None:
    day, month = _dayfirst_evidence(values)
    if strict and day and month:
        return None  # "15/01/2024" and "01/15/2024" in the same column
    if day != month:
        dayfirst = day > month
    else:
        dayfirst = hints.dayfirst

    parsed: list[_Temporal] = []
    for v in values:
        try:
            parsed.append(_parse_temporal(v, dayfirst))
        except ValueError:
            if strict:
                return None
    options = ParseOptions(dayfirst=dayfirst)

    if any(p.has_tz for p in parsed):
        if strict and not all(p.has_tz for p in parsed):
            return None
        return InferredType(PgType.TIMESTAMPTZ, options)
    if any(p.has_time for p in parsed):
        return InferredType(PgType.TIMESTAMP, options)
    return InferredType(PgType.DATE, options)


# --- inference ----------------------------------------------------------------------

def infer_column_type(
    values: Sequence[str],
    hints: LocaleHints,
    *,
    forced: PgType | None = None,
) -> InferredType:
    """Picks the narrowest type every non-null value fits, or the options for `forced`."""
    present = [v for v in values if not is_null(v)]

    if forced is not None:
        if forced in NUMBER_TYPES:
            inferred = _number_type(present, hints, strict=False)
            return InferredType(forced, inferred.options if inferred else ParseOptions())
        if forced in TEMPORAL_TYPES:
            inferred = _temporal_type(present, hints, strict=False)
            return InferredType(forced, inferred.options if inferred else ParseOptions())
        return InferredType(forced, ParseOptions())

    if not present:
        return InferredType(PgType.TEXT, ParseOptions())
    if all(v.strip().lower() in TRUE_TOKENS | FALSE_TOKENS for v in present):
        return InferredType(PgType.BOOLEAN, ParseOptions())
    for candidate in (_number_type, _temporal_type):
        if inferred := candidate(present, hints, strict=True):
            return inferred
    return InferredType(PgType.TEXT, ParseOptions())


# --- conversion ---------------------------------------------------------------------

def convert(value: str, pg_type: PgType, options: ParseOptions):
    """Converts a raw CSV value to the Python value loaded into Postgres (None = NULL)."""
    if is_null(value):
        return None
    text = value.strip()

    if pg_type is PgType.TEXT:
        return text
    if pg_type is PgType.BOOLEAN:
        return _parse_bool(text)
    if pg_type is PgType.BIGINT:
        number, has_fraction = _parse_number(text, options.decimal)
        if has_fraction or number != number.to_integral_value():
            raise ValueError(f"Not an integer: {value!r}")
        result = int(number)
        if abs(result) > _BIGINT_MAX:
            raise ValueError(f"Integer out of range: {value!r}")
        return result
    if pg_type is PgType.NUMERIC:
        return _parse_number(text, options.decimal)[0]

    parsed = _parse_temporal(text, options.dayfirst)
    if pg_type is PgType.DATE:
        if parsed.has_time:
            raise ValueError(f"Expected a date without time: {value!r}")
        return parsed.value.date()
    if pg_type is PgType.TIMESTAMP:
        if parsed.has_tz:
            raise ValueError(f"Expected a timestamp without time zone: {value!r}")
        return parsed.value
    if pg_type is PgType.TIMESTAMPTZ:
        if not parsed.has_tz:
            raise ValueError(f"Expected a timestamp with time zone: {value!r}")
        return parsed.value
    raise ValueError(f"Unsupported type: {pg_type}")


# --- semantic type ------------------------------------------------------------------

_ID_NAME = re.compile(r"(^|_)(id|cod|codigo|code|uuid|key)$|^(id|cod|codigo|code)_")
_MONEY_WORDS = frozenset({
    "price", "preco", "amount", "revenue", "receita", "valor", "cost", "custo",
    "faturamento", "salary", "salario", "fee", "taxa",
})
_CATEGORICAL_MAX_DISTINCT = 50
_CATEGORICAL_MAX_RATIO = 0.5
_SMALL_SAMPLE = 20


def infer_semantic_type(name: str, pg_type: PgType, options: ParseOptions, values: Sequence[str]) -> str:
    if pg_type in TEMPORAL_TYPES:
        return "temporal"
    if pg_type is PgType.BOOLEAN:
        return "boolean"
    if pg_type in (PgType.BIGINT, PgType.TEXT) and _ID_NAME.search(name):
        return "id"
    if pg_type in NUMBER_TYPES:
        if options.currency or is_money_name(name):
            return "currency"
        return "numeric"

    present = [v for v in values if not is_null(v)]
    distinct = len(set(present))
    if distinct <= _CATEGORICAL_MAX_DISTINCT and (
        len(present) < _SMALL_SAMPLE or distinct / max(len(present), 1) <= _CATEGORICAL_MAX_RATIO
    ):
        return "categorical"
    return "text"


def is_money_name(name: str) -> bool:
    """True when a snake_case column name suggests a monetary value."""
    return bool(_MONEY_WORDS & set(name.lower().split("_")))
