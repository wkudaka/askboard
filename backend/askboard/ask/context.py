"""Describes a workspace's loaded tables to the LLM, using the ingestion profiles."""

import json

from askboard.ingestion.types import NUMBER_TYPES, TEMPORAL_TYPES, PgType
from askboard.models import ColumnInfo, Dataset, Relationship

MAX_SAMPLE_CHARS = 40


def _loaded(datasets: list[Dataset]) -> list[Dataset]:
    return [d for d in datasets if d.status == "loaded"]


def allowed_tables(datasets: list[Dataset]) -> set[str]:
    return {d.table_name for d in _loaded(datasets)}


def _quote(value: str) -> str:
    if len(value) > MAX_SAMPLE_CHARS:
        value = value[:MAX_SAMPLE_CHARS] + "…"
    return json.dumps(value, ensure_ascii=False)


def _describe_column(c: ColumnInfo) -> str:
    parts = [c.pg_type.value, c.semantic_type]
    if c.is_unique:
        parts.append("unique")
    if c.null_ratio:
        parts.append(f"{round(c.null_ratio * 100)}% null")
    if c.pg_type is PgType.TEXT and c.distinct_count is not None:
        parts.append(f"{c.distinct_count} distinct")
    if (c.pg_type in NUMBER_TYPES or c.pg_type in TEMPORAL_TYPES) and c.min_value and c.max_value:
        parts.append(f"range {c.min_value} .. {c.max_value}")
    if c.pg_type is PgType.TEXT and c.sample_values:
        parts.append("e.g. " + ", ".join(_quote(v) for v in c.sample_values))

    line = f"  - {c.name}: " + ", ".join(parts)
    if c.original_name != c.name:
        line += f" (originally {_quote(c.original_name)})"
    return line


def _describe_relationship(r: Relationship) -> str:
    status = "confirmed" if r.status == "confirmed" else f"likely, {round(r.confidence * 100)}% of values match"
    return f"  - {r.from_table}.{r.from_column} = {r.to_table}.{r.to_column} ({status})"


def build_schema_context(datasets: list[Dataset], relationships: list[Relationship] | None = None) -> str:
    blocks = []
    for d in _loaded(datasets):
        header = f'Table {d.table_name} ({d.row_count} rows, from "{d.original_filename}")'
        blocks.append("\n".join([header, *(_describe_column(c) for c in d.columns)]))
    usable = [r for r in relationships or [] if r.status != "rejected"]
    if blocks and usable:
        blocks.append("\n".join(["Relationships (join on these):", *(_describe_relationship(r) for r in usable)]))
    return "\n\n".join(blocks)
