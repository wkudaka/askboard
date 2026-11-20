from __future__ import annotations

import uuid

from psycopg import AsyncConnection
from psycopg.rows import class_row, dict_row

from askboard.db.database import Database
from askboard.models import AskRecord, Conversation, ConversationDetail
from askboard.services.errors import NotFoundError

TITLE_MAX = 60
LIST_LIMIT = 100

_COLUMNS = "id, workspace_id, title, created_at, updated_at"


def title_from_question(question: str) -> str:
    """First line of the question, cut at a word boundary (like a chat assistant's sidebar)."""
    line = " ".join(question.split())
    if len(line) <= TITLE_MAX:
        return line or "New chat"
    cut = line[:TITLE_MAX].rsplit(" ", 1)[0] or line[:TITLE_MAX]
    return cut.rstrip(" ,.;:?!") + "…"


def record_from_row(row: dict) -> AskRecord:
    return AskRecord(
        **row["dashboard"],
        id=row["id"],
        conversation_id=row["conversation_id"],
        created_at=row["created_at"],
    )


class ConversationService:
    def __init__(self, db: Database):
        self._db = db

    async def list(self, workspace_id: uuid.UUID, limit: int = LIST_LIMIT) -> list[Conversation]:
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=class_row(Conversation))
            await cur.execute(
                f"SELECT {_COLUMNS} FROM askboard.conversations"
                " WHERE workspace_id = %s ORDER BY updated_at DESC, id LIMIT %s",
                (workspace_id, limit),
            )
            return await cur.fetchall()

    async def get(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
        async with self._db.connection() as conn:
            return await self._get(conn, workspace_id, conversation_id)

    async def detail(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> ConversationDetail:
        async with self._db.connection() as conn:
            conversation = await self._get(conn, workspace_id, conversation_id)
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                "SELECT id, conversation_id, created_at, dashboard FROM askboard.questions"
                " WHERE conversation_id = %s ORDER BY created_at, id",
                (conversation_id,),
            )
            rows = await cur.fetchall()
        return ConversationDetail(**conversation.model_dump(), messages=[record_from_row(r) for r in rows])

    async def previous_questions(self, conversation_id: uuid.UUID, limit: int) -> list[str]:
        """The last ``limit`` questions of a conversation, oldest first."""
        async with self._db.connection() as conn:
            cur = await conn.execute(
                "SELECT question FROM ("
                "  SELECT question, created_at, id FROM askboard.questions"
                "  WHERE conversation_id = %s ORDER BY created_at DESC, id DESC LIMIT %s"
                ") q ORDER BY created_at, id",
                (conversation_id, limit),
            )
            return [r[0] for r in await cur.fetchall()]

    async def rename(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID, title: str) -> Conversation:
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=class_row(Conversation))
            await cur.execute(
                f"UPDATE askboard.conversations SET title = %s"
                f" WHERE id = %s AND workspace_id = %s RETURNING {_COLUMNS}",
                (title, conversation_id, workspace_id),
            )
            conversation = await cur.fetchone()
        if conversation is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        return conversation

    async def delete(self, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> None:
        async with self._db.connection() as conn:
            cur = await conn.execute(
                "DELETE FROM askboard.conversations WHERE id = %s AND workspace_id = %s",
                (conversation_id, workspace_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Conversation {conversation_id} not found")

    @staticmethod
    async def _get(conn: AsyncConnection, workspace_id: uuid.UUID, conversation_id: uuid.UUID) -> Conversation:
        cur = conn.cursor(row_factory=class_row(Conversation))
        await cur.execute(
            f"SELECT {_COLUMNS} FROM askboard.conversations WHERE id = %s AND workspace_id = %s",
            (conversation_id, workspace_id),
        )
        conversation = await cur.fetchone()
        if conversation is None:
            raise NotFoundError(f"Conversation {conversation_id} not found")
        return conversation
