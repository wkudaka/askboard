"""Executes validated SQL with the least privileges possible.

Every query runs in its own READ ONLY transaction, as the `askboard_reader` role (SELECT
only, no access to the `askboard` metadata schema), with `search_path` pinned to the
workspace schema and a statement timeout.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import sql

from askboard.db.database import Database

READER_ROLE = "askboard_reader"

_TYPE_CATEGORIES = {
    "int2": "number", "int4": "number", "int8": "number", "numeric": "number",
    "float4": "number", "float8": "number", "oid": "number",
    "bool": "boolean",
    "date": "date",
    "timestamp": "timestamp", "timestamptz": "timestamp",
}


class QueryExecutionError(Exception):
    """Postgres rejected or aborted the query; the message is safe to show the LLM."""


@dataclass(frozen=True)
class ResultColumn:
    name: str
    type: str  # number | text | boolean | date | timestamp


@dataclass
class QueryResult:
    columns: list[ResultColumn]
    rows: list[list[Any]]
    truncated: bool


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (timedelta, uuid.UUID, bytes, memoryview)):
        return str(value)
    return value


class QueryRunner:
    def __init__(self, db: Database, *, statement_timeout_ms: int, max_rows: int):
        self._db = db
        self._timeout_ms = statement_timeout_ms
        self._max_rows = max_rows

    async def run(self, schema: str, query: str) -> QueryResult:
        bounded = sql.SQL("SELECT * FROM ({}) AS _askboard_q LIMIT {}").format(
            sql.SQL(query), sql.Literal(self._max_rows + 1)
        )
        async with self._db.connection() as conn:
            try:
                async with conn.transaction():
                    await conn.execute("SET TRANSACTION READ ONLY")
                    await conn.execute(
                        sql.SQL("SET LOCAL statement_timeout = {}").format(sql.Literal(self._timeout_ms))
                    )
                    await conn.execute(sql.SQL("SET LOCAL search_path = {}").format(sql.Identifier(schema)))
                    await conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(READER_ROLE)))
                    cursor = await conn.execute(bounded)
                    rows = await cursor.fetchall()
                    description = cursor.description or []
            except psycopg.Error as exc:
                message = (exc.diag.message_primary if exc.diag else None) or str(exc)
                raise QueryExecutionError(message) from exc

            columns = [
                ResultColumn(
                    name=col.name,
                    type=_TYPE_CATEGORIES.get(getattr(conn.adapters.types.get(col.type_code), "name", ""), "text"),
                )
                for col in description
            ]

        truncated = len(rows) > self._max_rows
        return QueryResult(
            columns=columns,
            rows=[[_json_value(v) for v in row] for row in rows[: self._max_rows]],
            truncated=truncated,
        )
