from __future__ import annotations

import uuid
from collections.abc import Callable

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from askboard.ask.context import allowed_tables, build_schema_context
from askboard.ask.graph import AskGraph, Runner
from askboard.ask.llm import LLMError, StructuredLLM
from askboard.db.database import Database
from askboard.models import AskRecord, AskResult
from askboard.services.conversations import ConversationService, record_from_row, title_from_question
from askboard.services.datasets import DatasetService
from askboard.services.relationships import RelationshipService
from askboard.services.workspaces import WorkspaceService

HISTORY_LIMIT = 20
CONVERSATION_CONTEXT = 5  # earlier questions of the thread given to the LLM


class _NoLLM:
    """Used when a workspace has no data: the graph stops before any LLM call."""

    async def generate(self, system_prompt, user_prompt, schema):
        raise LLMError("No LLM needed for this request")


class AskService:
    def __init__(
        self,
        db: Database,
        datasets: DatasetService,
        *,
        runner: Runner,
        llm_factory: Callable[[], StructuredLLM],
        max_correction_attempts: int,
    ):
        self._db = db
        self._datasets = datasets
        self._workspaces = WorkspaceService(db)
        self._conversations = ConversationService(db)
        self._runner = runner
        self._llm_factory = llm_factory
        self._max_corrections = max_correction_attempts
        self._graph: AskGraph | None = None

    def _graph_for_questions(self) -> AskGraph:
        # Built lazily so the app starts (and uploads work) without LLM credentials.
        if self._graph is None:
            self._graph = AskGraph(
                self._llm_factory(), self._runner, max_correction_attempts=self._max_corrections
            )
        return self._graph

    async def ask(
        self, workspace_id: uuid.UUID, question: str, conversation_id: uuid.UUID | None = None
    ) -> AskRecord:
        workspace = await self._workspaces.get(workspace_id)
        previous: list[str] = []
        if conversation_id is not None:
            await self._conversations.get(workspace_id, conversation_id)
            previous = await self._conversations.previous_questions(conversation_id, CONVERSATION_CONTEXT)
        datasets = await self._datasets.list(workspace_id)
        relationships = await RelationshipService(self._db).list(workspace_id)
        context = build_schema_context(datasets, relationships)

        graph = (
            self._graph_for_questions() if context
            else AskGraph(_NoLLM(), self._runner, max_correction_attempts=0)
        )
        result = await graph.answer(
            question=question,
            schema_name=workspace.schema_name,
            context=context,
            allowed_tables=allowed_tables(datasets),
            previous_questions=previous,
        )
        return await self._save(workspace_id, conversation_id, result)

    async def history(self, workspace_id: uuid.UUID, limit: int = HISTORY_LIMIT) -> list[AskRecord]:
        await self._workspaces.get(workspace_id)
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                "SELECT id, conversation_id, created_at, dashboard FROM askboard.questions"
                " WHERE workspace_id = %s ORDER BY created_at DESC, id LIMIT %s",
                (workspace_id, limit),
            )
            rows = await cur.fetchall()
        return [record_from_row(r) for r in rows]

    async def _save(
        self, workspace_id: uuid.UUID, conversation_id: uuid.UUID | None, result: AskResult
    ) -> AskRecord:
        async with self._db.connection() as conn, conn.transaction():
            if conversation_id is None:
                cur = await conn.execute(
                    "INSERT INTO askboard.conversations (workspace_id, title) VALUES (%s, %s) RETURNING id",
                    (workspace_id, title_from_question(result.question)),
                )
                (conversation_id,) = await cur.fetchone()
            cur = await conn.execute(
                "INSERT INTO askboard.questions"
                " (workspace_id, conversation_id, question, queries, dashboard, error)"
                " VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, created_at",
                (
                    workspace_id,
                    conversation_id,
                    result.question,
                    Jsonb([p.sql for p in result.panels]),
                    Jsonb(result.model_dump(mode="json")),
                    result.error,
                ),
            )
            question_id, created_at = await cur.fetchone()
            await conn.execute(
                "UPDATE askboard.conversations SET updated_at = %s WHERE id = %s",
                (created_at, conversation_id),
            )
        return AskRecord(
            **result.model_dump(), id=question_id, conversation_id=conversation_id, created_at=created_at
        )
