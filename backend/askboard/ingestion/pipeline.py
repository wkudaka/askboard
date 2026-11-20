"""Pure (DB-free) steps between a parsed CSV and rows ready to COPY into Postgres."""

from dataclasses import dataclass, replace
from typing import Any

from askboard.ingestion.naming import unique_identifiers
from askboard.ingestion.sniff import CsvFormat, ParsedCsv
from askboard.ingestion.types import (
    LocaleHints,
    ParseOptions,
    PgType,
    convert,
    infer_column_type,
    infer_semantic_type,
    is_null,
)
from askboard.models import LoadError

SAMPLE_SIZE = 5
RAGGED_MESSAGE = "Row has a different number of columns than the header"


@dataclass(frozen=True)
class ColumnPlan:
    position: int  # 1-based
    name: str
    original_name: str
    pg_type: PgType
    options: ParseOptions
    semantic_type: str


def hints_for(fmt: CsvFormat) -> LocaleHints:
    # A ';' delimiter almost always means a locale where ',' is the decimal separator.
    return LocaleHints(decimal_comma=fmt.delimiter == ";", dayfirst=True)


def column_values(parsed: ParsedCsv, position: int) -> list[str]:
    return [row[position - 1] for row in parsed.rows]


def first_distinct(values: list[str], limit: int = SAMPLE_SIZE) -> list[str]:
    seen: dict[str, None] = {}
    for v in values:
        if not is_null(v) and v not in seen:
            seen[v] = None
            if len(seen) == limit:
                break
    return list(seen)


def plan_columns(parsed: ParsedCsv, hints: LocaleHints) -> list[ColumnPlan]:
    plans = []
    for position, (name, original) in enumerate(
        zip(unique_identifiers(parsed.header), parsed.header), start=1
    ):
        values = column_values(parsed, position)
        inferred = infer_column_type(values, hints)
        plans.append(ColumnPlan(
            position=position,
            name=name,
            original_name=original,
            pg_type=inferred.pg_type,
            options=inferred.options,
            semantic_type=infer_semantic_type(name, inferred.pg_type, inferred.options, values),
        ))
    return plans


def replan_column(
    plan: ColumnPlan,
    parsed: ParsedCsv,
    hints: LocaleHints,
    *,
    name: str | None = None,
    pg_type: PgType | None = None,
) -> ColumnPlan:
    """Applies a user override (rename and/or forced type) to a planned column."""
    values = column_values(parsed, plan.position)
    updated = plan
    if name is not None:
        updated = replace(updated, name=name)
    if pg_type is not None and pg_type != plan.pg_type:
        forced = infer_column_type(values, hints, forced=pg_type)
        updated = replace(updated, pg_type=forced.pg_type, options=forced.options)
    return replace(
        updated,
        semantic_type=infer_semantic_type(updated.name, updated.pg_type, updated.options, values),
    )


def ragged_errors(parsed: ParsedCsv) -> list[LoadError]:
    return [LoadError(line=line, message=RAGGED_MESSAGE) for line in parsed.ragged_lines]


def convert_rows(parsed: ParsedCsv, plans: list[ColumnPlan]) -> tuple[list[tuple[Any, ...]], list[LoadError]]:
    """Converts every row; a row with any unconvertible value is rejected as a whole."""
    rows: list[tuple[Any, ...]] = []
    errors: list[LoadError] = []
    for raw_row, line in zip(parsed.rows, parsed.row_lines):
        converted: list[Any] = []
        row_errors: list[LoadError] = []
        for plan in plans:
            raw = raw_row[plan.position - 1]
            try:
                converted.append(convert(raw, plan.pg_type, plan.options))
            except ValueError as exc:
                row_errors.append(LoadError(line=line, column=plan.name, value=raw, message=str(exc)))
        if row_errors:
            errors.extend(row_errors)
        else:
            rows.append(tuple(converted))
    return rows, errors
