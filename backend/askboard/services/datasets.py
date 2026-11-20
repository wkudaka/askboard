from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from askboard.db.database import Database
from askboard.ingestion.naming import dedupe, table_name_from_filename, to_identifier
from askboard.ingestion.pipeline import (
    ColumnPlan,
    column_values,
    convert_rows,
    first_distinct,
    hints_for,
    plan_columns,
    ragged_errors,
    replan_column,
)
from askboard.ingestion.sniff import CsvFormat, CsvFormatError, ParsedCsv, detect_format, parse_csv
from askboard.ingestion.types import ParseOptions, PgType
from askboard.models import (
    ColumnInfo,
    ConfirmRequest,
    Dataset,
    DatasetPreview,
    LoadError,
    SourceFormat,
)
from askboard.services.errors import ConflictError, InvalidInputError, NotFoundError
from askboard.services.workspaces import WorkspaceService

PREVIEW_ROWS = 20
MAX_STORED_ERRORS = 100
TOP_VALUES = 5

_DATASET_COLUMNS = """
    id, workspace_id, table_name, original_filename, status, row_count, rejected_rows,
    source_format, load_errors, created_at
"""


def _parse(raw: bytes, fmt: CsvFormat | None = None) -> tuple[CsvFormat, ParsedCsv]:
    try:
        fmt = fmt or detect_format(raw)
        return fmt, parse_csv(raw, fmt)
    except (CsvFormatError, UnicodeDecodeError) as exc:
        raise InvalidInputError(str(exc)) from exc


def _plan_from_row(row: dict[str, Any]) -> ColumnPlan:
    return ColumnPlan(
        position=row["position"],
        name=row["name"],
        original_name=row["original_name"],
        pg_type=PgType(row["pg_type"]),
        options=ParseOptions(**row["parse_options"]),
        semantic_type=row["semantic_type"],
    )


class DatasetService:
    def __init__(self, db: Database):
        self._db = db
        self._workspaces = WorkspaceService(db)

    # --- preview ------------------------------------------------------------------

    async def create_preview(self, workspace_id: uuid.UUID, filename: str, raw: bytes) -> DatasetPreview:
        await self._workspaces.get(workspace_id)
        fmt, parsed = _parse(raw)
        if not parsed.rows:
            raise InvalidInputError("The file has no data rows")

        plans = plan_columns(parsed, hints_for(fmt))
        errors = ragged_errors(parsed)
        dataset_id = uuid.uuid4()

        async with self._db.connection() as conn, conn.transaction():
            # Serialize uploads per workspace so table-name dedupe cannot race.
            await conn.execute(
                "SELECT 1 FROM askboard.workspaces WHERE id = %s FOR UPDATE", (workspace_id,)
            )
            taken = await self._taken_table_names(conn, workspace_id)
            table_name = dedupe(table_name_from_filename(filename), taken)

            await conn.execute(
                "INSERT INTO askboard.datasets (id, workspace_id, table_name, original_filename,"
                " status, row_count, rejected_rows, source_format, load_errors)"
                " VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, %s)",
                (
                    dataset_id, workspace_id, table_name, filename, len(parsed.rows), len(errors),
                    Jsonb(asdict(fmt)), Jsonb([e.model_dump() for e in errors]),
                ),
            )
            await self._insert_columns(conn, dataset_id, [
                (plan, {"sample_values": first_distinct(column_values(parsed, plan.position))})
                for plan in plans
            ])
            await conn.execute(
                "INSERT INTO askboard.dataset_sources (dataset_id, content) VALUES (%s, %s)",
                (dataset_id, raw),
            )

        dataset = await self.get(workspace_id, dataset_id)
        return DatasetPreview(**dataset.model_dump(), preview_rows=parsed.rows[:PREVIEW_ROWS])

    # --- confirm ------------------------------------------------------------------

    async def confirm(self, workspace_id: uuid.UUID, dataset_id: uuid.UUID, request: ConfirmRequest) -> Dataset:
        workspace = await self._workspaces.get(workspace_id)

        async with self._db.connection() as conn, conn.transaction():
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"SELECT {_DATASET_COLUMNS} FROM askboard.datasets"
                " WHERE id = %s AND workspace_id = %s FOR UPDATE",
                (dataset_id, workspace_id),
            )
            dataset = await cur.fetchone()
            if dataset is None:
                raise NotFoundError(f"Dataset {dataset_id} not found")
            if dataset["status"] != "pending":
                raise ConflictError(f"Dataset {dataset_id} is already {dataset['status']}")

            await cur.execute(
                "SELECT d.content FROM askboard.dataset_sources d WHERE d.dataset_id = %s", (dataset_id,)
            )
            source = await cur.fetchone()
            fmt, parsed = _parse(bytes(source["content"]), CsvFormat(**dataset["source_format"]))

            await cur.execute(
                "SELECT position, name, original_name, pg_type, semantic_type, parse_options"
                " FROM askboard.columns WHERE dataset_id = %s ORDER BY position",
                (dataset_id,),
            )
            plans = self._apply_overrides(
                [_plan_from_row(r) for r in await cur.fetchall()], request, parsed, fmt
            )
            table_name = dataset["table_name"]
            if request.table_name is not None:
                table_name = to_identifier(request.table_name, fallback="dataset", digit_prefix="t_")
                taken = await self._taken_table_names(conn, workspace_id, exclude=dataset_id)
                if table_name in taken:
                    raise InvalidInputError(f"Table name '{table_name}' is already used in this workspace")

            rows, conversion_errors = convert_rows(parsed, plans)
            errors = ragged_errors(parsed) + conversion_errors
            rejected = len(parsed.ragged_lines) + len({e.line for e in conversion_errors})

            table = sql.Identifier(workspace.schema_name, table_name)
            await self._create_and_copy(conn, table, plans, rows)
            profiles = [await self._profile(conn, table, plan) for plan in plans]

            await conn.execute("DELETE FROM askboard.columns WHERE dataset_id = %s", (dataset_id,))
            await self._insert_columns(conn, dataset_id, list(zip(plans, profiles)))
            await conn.execute(
                "UPDATE askboard.datasets SET status = 'loaded', table_name = %s, row_count = %s,"
                " rejected_rows = %s, load_errors = %s WHERE id = %s",
                (
                    table_name, len(rows), rejected,
                    Jsonb([e.model_dump() for e in errors[:MAX_STORED_ERRORS]]), dataset_id,
                ),
            )
            await conn.execute("DELETE FROM askboard.dataset_sources WHERE dataset_id = %s", (dataset_id,))

        return await self.get(workspace_id, dataset_id)

    def _apply_overrides(
        self, plans: list[ColumnPlan], request: ConfirmRequest, parsed: ParsedCsv, fmt: CsvFormat
    ) -> list[ColumnPlan]:
        by_position = {p.position: p for p in plans}
        seen: set[int] = set()
        for override in request.columns:
            if override.position not in by_position:
                raise InvalidInputError(f"Unknown column position {override.position}")
            if override.position in seen:
                raise InvalidInputError(f"Column position {override.position} given more than once")
            seen.add(override.position)
            name = (
                to_identifier(override.name, fallback=f"column_{override.position}")
                if override.name is not None else None
            )
            by_position[override.position] = replan_column(
                by_position[override.position], parsed, hints_for(fmt), name=name, pg_type=override.pg_type
            )

        final = [by_position[p] for p in sorted(by_position)]
        names = [p.name for p in final]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise InvalidInputError(f"Duplicate column name(s): {', '.join(duplicates)}")
        return final

    async def _create_and_copy(
        self, conn: psycopg.AsyncConnection, table: sql.Identifier, plans: list[ColumnPlan], rows: list[tuple]
    ) -> None:
        column_defs = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(p.name), sql.SQL(p.pg_type.value)) for p in plans
        )
        try:
            await conn.execute(sql.SQL("CREATE TABLE {} ({})").format(table, column_defs))
        except psycopg.errors.DuplicateTable as exc:
            raise InvalidInputError("A table with this name already exists in the workspace") from exc

        columns = sql.SQL(", ").join(sql.Identifier(p.name) for p in plans)
        async with conn.cursor().copy(
            sql.SQL("COPY {} ({}) FROM STDIN").format(table, columns)
        ) as copy:
            for row in rows:
                await copy.write_row(row)

    async def _profile(self, conn: psycopg.AsyncConnection, table: sql.Identifier, plan: ColumnPlan) -> dict:
        col = sql.Identifier(plan.name)
        has_order = plan.pg_type is not PgType.BOOLEAN  # min()/max() do not exist for boolean
        min_max = (
            sql.SQL("min({c})::text, max({c})::text").format(c=col)
            if has_order else sql.SQL("NULL::text, NULL::text")
        )
        cur = await conn.execute(
            sql.SQL("SELECT count(*), count({c}), count(DISTINCT {c}), {mm} FROM {t}").format(
                c=col, mm=min_max, t=table
            )
        )
        total, non_null, distinct, min_value, max_value = await cur.fetchone()

        cur = await conn.execute(
            sql.SQL(
                "SELECT {c}::text FROM {t} WHERE {c} IS NOT NULL"
                " GROUP BY {c} ORDER BY count(*) DESC, {c} LIMIT {n}"
            ).format(c=col, t=table, n=sql.Literal(TOP_VALUES))
        )
        top = [r[0] for r in await cur.fetchall()]

        return {
            "sample_values": top,
            "null_ratio": (total - non_null) / total if total else None,
            "distinct_count": distinct,
            "min_value": min_value,
            "max_value": max_value,
            "is_unique": total > 0 and non_null == total and distinct == total,
        }

    # --- reads -----------------------------------------------------------------------

    async def get(self, workspace_id: uuid.UUID, dataset_id: uuid.UUID) -> Dataset:
        datasets = await self._fetch(workspace_id, dataset_id)
        if not datasets:
            raise NotFoundError(f"Dataset {dataset_id} not found")
        return datasets[0]

    async def list(self, workspace_id: uuid.UUID) -> list[Dataset]:
        await self._workspaces.get(workspace_id)
        return await self._fetch(workspace_id)

    async def _fetch(self, workspace_id: uuid.UUID, dataset_id: uuid.UUID | None = None) -> list[Dataset]:
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                f"SELECT {_DATASET_COLUMNS} FROM askboard.datasets"
                " WHERE workspace_id = %s AND (%s::uuid IS NULL OR id = %s)"
                " ORDER BY created_at DESC, id",
                (workspace_id, dataset_id, dataset_id),
            )
            rows = await cur.fetchall()
            if not rows:
                return []
            await cur.execute(
                "SELECT dataset_id, position, name, original_name, pg_type, semantic_type,"
                " sample_values, null_ratio, distinct_count, min_value, max_value, is_unique"
                " FROM askboard.columns WHERE dataset_id = ANY(%s) ORDER BY position",
                ([r["id"] for r in rows],),
            )
            columns: dict[uuid.UUID, list[ColumnInfo]] = {}
            for c in await cur.fetchall():
                columns.setdefault(c.pop("dataset_id"), []).append(ColumnInfo(**c))

        return [
            Dataset(
                **{k: v for k, v in r.items() if k not in ("source_format", "load_errors")},
                source_format=SourceFormat(**r["source_format"]),
                load_errors=[LoadError(**e) for e in r["load_errors"]],
                columns=columns.get(r["id"], []),
            )
            for r in rows
        ]

    # --- helpers --------------------------------------------------------------------------

    async def _taken_table_names(
        self, conn: psycopg.AsyncConnection, workspace_id: uuid.UUID, exclude: uuid.UUID | None = None
    ) -> set[str]:
        cur = await conn.execute(
            "SELECT table_name FROM askboard.datasets WHERE workspace_id = %s AND id IS DISTINCT FROM %s",
            (workspace_id, exclude),
        )
        return {r[0] for r in await cur.fetchall()}

    async def _insert_columns(
        self, conn: psycopg.AsyncConnection, dataset_id: uuid.UUID, columns: list[tuple[ColumnPlan, dict]]
    ) -> None:
        async with conn.cursor() as cur:
            await cur.executemany(
                "INSERT INTO askboard.columns (dataset_id, position, name, original_name, pg_type,"
                " semantic_type, parse_options, sample_values, null_ratio, distinct_count,"
                " min_value, max_value, is_unique)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (
                        dataset_id, plan.position, plan.name, plan.original_name, plan.pg_type.value,
                        plan.semantic_type, Jsonb(asdict(plan.options)),
                        Jsonb(profile.get("sample_values", [])), profile.get("null_ratio"),
                        profile.get("distinct_count"), profile.get("min_value"),
                        profile.get("max_value"), profile.get("is_unique", False),
                    )
                    for plan, profile in columns
                ],
            )
