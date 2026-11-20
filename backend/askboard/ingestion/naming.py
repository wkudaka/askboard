"""Turns arbitrary CSV headers and filenames into safe Postgres identifiers.

Identifiers are always quoted when Askboard builds SQL, but LLM-generated SQL may not
quote them, so we keep them boring: lowercase ASCII snake_case, not a reserved word,
not starting with a digit, at most 63 bytes (Postgres NAMEDATALEN - 1).
"""

import re
import unicodedata
from collections.abc import Iterable

MAX_IDENTIFIER_LENGTH = 63

# Postgres fully reserved keywords (cannot be used as unquoted column/table names).
RESERVED_WORDS = frozenset("""
all analyse analyze and any array as asc asymmetric authorization binary both case cast
check collate collation column concurrently constraint create cross current_catalog
current_date current_role current_schema current_time current_timestamp current_user
default deferrable desc distinct do else end except false fetch for foreign freeze from
full grant group having ilike in initially inner intersect into is isnull join lateral
leading left like limit localtime localtimestamp natural not notnull null offset on only
or order outer overlaps placing primary references returning right select session_user
similar some symmetric system_user table tablesample then to trailing true union unique
user using variadic verbose when where window with
""".split())

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_ACRONYM_BOUNDARY = re.compile(r"(?<=[A-Z])(?=[A-Z][a-z])")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _ascii_fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return decomposed.encode("ascii", "ignore").decode("ascii")


def to_identifier(raw: str, *, fallback: str = "column", digit_prefix: str = "c_") -> str:
    text = _ascii_fold(raw.strip())
    text = _ACRONYM_BOUNDARY.sub("_", text)
    text = _CAMEL_BOUNDARY.sub("_", text)
    text = _NON_ALNUM.sub("_", text.lower()).strip("_")

    if not text:
        return fallback
    if text[0].isdigit():
        text = digit_prefix + text
    if text in RESERVED_WORDS:
        text += "_"
    return text[:MAX_IDENTIFIER_LENGTH].rstrip("_") if len(text) > MAX_IDENTIFIER_LENGTH else text


def dedupe(name: str, taken: set[str]) -> str:
    """Returns `name`, or `name_<n>` (n >= 2) if `name` is already taken."""
    if name not in taken:
        return name
    n = 2
    while True:
        suffix = f"_{n}"
        candidate = name[: MAX_IDENTIFIER_LENGTH - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1


def unique_identifiers(raws: Iterable[str]) -> list[str]:
    """Normalizes a header row; blank headers become `column_<position>` (1-based)."""
    taken: set[str] = set()
    result: list[str] = []
    for position, raw in enumerate(raws, start=1):
        name = dedupe(to_identifier(raw, fallback=f"column_{position}"), taken)
        taken.add(name)
        result.append(name)
    return result


def table_name_from_filename(filename: str) -> str:
    basename = re.split(r"[\\/]", filename)[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return to_identifier(stem, fallback="dataset", digit_prefix="t_")
