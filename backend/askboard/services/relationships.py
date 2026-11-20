from __future__ import annotations

import uuid

import psycopg
from psycopg import sql
from psycopg.rows import class_row

from askboard.db.database import Database
from askboard.ingestion.relationships import Candidate, find_candidates
from askboard.models import Dataset, Relationship, RelationshipStatus
from askboard.services.errors import NotFoundError

MIN_COVERAGE = 0.9

_SELECT = """
    SELECT r.id, r.workspace_id, r.from_dataset_id, f.table_name AS from_table, r.from_column,
           r.to_dataset_id, t.table_name AS to_table, r.to_column, r.confidence, r.status
    FROM askboard.relationships r
    JOIN askboard.datasets f ON f.id = r.from_dataset_id
    JOIN askboard.datasets t ON t.id = r.to_dataset_id
"""


class RelationshipService:
    def __init__(self, db: Database):
        self._db = db

    async def refresh(self, workspace_id: uuid.UUID, schema_name: str, datasets: list[Dataset]) -> None:
        """Re-scores name-based candidates against the data; keeps user decisions."""
        async with self._db.connection() as conn:
            for candidate in find_candidates(datasets):
                coverage = await self._coverage(conn, schema_name, candidate)
                if coverage is None:
                    continue
                key = (candidate.from_dataset_id, candidate.from_column, candidate.to_dataset_id, candidate.to_column)
                if coverage >= MIN_COVERAGE:
                    await conn.execute(
                        "INSERT INTO askboard.relationships (workspace_id, from_dataset_id, from_column,"
                        " to_dataset_id, to_column, confidence) VALUES (%s, %s, %s, %s, %s, %s)"
                        " ON CONFLICT (from_dataset_id, from_column, to_dataset_id, to_column)"
                        " DO UPDATE SET confidence = EXCLUDED.confidence",
                        (workspace_id, *key, coverage),
                    )
                else:  # the data no longer supports an automatic suggestion
                    await conn.execute(
                        "DELETE FROM askboard.relationships WHERE from_dataset_id = %s AND from_column = %s"
                        " AND to_dataset_id = %s AND to_column = %s AND status = 'suggested'",
                        key,
                    )

    async def list(self, workspace_id: uuid.UUID) -> list[Relationship]:
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=class_row(Relationship))
            await cur.execute(
                _SELECT + " WHERE r.workspace_id = %s ORDER BY f.table_name, r.from_column, t.table_name",
                (workspace_id,),
            )
            return await cur.fetchall()

    async def set_status(
        self, workspace_id: uuid.UUID, relationship_id: uuid.UUID, status: RelationshipStatus
    ) -> Relationship:
        async with self._db.connection() as conn:
            cur = await conn.execute(
                "UPDATE askboard.relationships SET status = %s WHERE id = %s AND workspace_id = %s",
                (status, relationship_id, workspace_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Relationship {relationship_id} not found")
            cur = conn.cursor(row_factory=class_row(Relationship))
            await cur.execute(_SELECT + " WHERE r.id = %s", (relationship_id,))
            return await cur.fetchone()

    @staticmethod
    async def _coverage(conn: psycopg.AsyncConnection, schema: str, c: Candidate) -> float | None:
        """Share of distinct non-null source values that exist in the target column."""
        query = sql.SQL(
            "WITH src AS (SELECT DISTINCT {fc}::text AS v FROM {ft} WHERE {fc} IS NOT NULL)"
            " SELECT count(*), count(*) FILTER (WHERE EXISTS"
            " (SELECT 1 FROM {tt} WHERE {tc}::text = src.v)) FROM src"
        ).format(
            fc=sql.Identifier(c.from_column),
            ft=sql.Identifier(schema, c.from_table),
            tc=sql.Identifier(c.to_column),
            tt=sql.Identifier(schema, c.to_table),
        )
        total, matched = await (await conn.execute(query)).fetchone()
        return matched / total if total else None
