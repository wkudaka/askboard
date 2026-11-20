from __future__ import annotations

import uuid

from psycopg import sql
from psycopg.rows import class_row

from askboard.db.database import Database
from askboard.models import Workspace
from askboard.services.errors import InvalidInputError, NotFoundError

READER_ROLE = "askboard_reader"


class WorkspaceService:
    def __init__(self, db: Database):
        self._db = db

    async def create(self, name: str) -> Workspace:
        name = name.strip()
        if not name:
            raise InvalidInputError("Workspace name is required")

        workspace_id = uuid.uuid4()
        schema = sql.Identifier(f"ws_{workspace_id.hex[:12]}")
        reader = sql.Identifier(READER_ROLE)

        async with self._db.connection() as conn, conn.transaction():
            cur = conn.cursor(row_factory=class_row(Workspace))
            await cur.execute(
                "INSERT INTO askboard.workspaces (id, name, schema_name) VALUES (%s, %s, %s) "
                "RETURNING id, name, schema_name, created_at",
                (workspace_id, name, f"ws_{workspace_id.hex[:12]}"),
            )
            workspace = await cur.fetchone()
            await conn.execute(sql.SQL("CREATE SCHEMA {}").format(schema))
            await conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema, reader))
            await conn.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {}").format(
                    schema, reader
                )
            )
        return workspace

    async def list(self) -> list[Workspace]:
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=class_row(Workspace))
            await cur.execute(
                "SELECT id, name, schema_name, created_at FROM askboard.workspaces "
                "ORDER BY created_at DESC, id"
            )
            return await cur.fetchall()

    async def get(self, workspace_id: uuid.UUID) -> Workspace:
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=class_row(Workspace))
            await cur.execute(
                "SELECT id, name, schema_name, created_at FROM askboard.workspaces WHERE id = %s",
                (workspace_id,),
            )
            workspace = await cur.fetchone()
        if workspace is None:
            raise NotFoundError(f"Workspace {workspace_id} not found")
        return workspace
