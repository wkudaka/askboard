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
from askboard.services.datasets import DatasetService
from askboard.services.workspaces import WorkspaceService

HISTORY_LIMIT = 20


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

    async def ask(self, workspace_id: uuid.UUID, question: str) -> AskRecord:
        workspace = await self._workspaces.get(workspace_id)
        datasets = await self._datasets.list(workspace_id)
        context = build_schema_context(datasets)

        graph = (
            self._graph_for_questions() if context
            else AskGraph(_NoLLM(), self._runner, max_correction_attempts=0)
        )
        result = await graph.answer(
            question=question,
            schema_name=workspace.schema_name,
            context=context,
            allowed_tables=allowed_tables(datasets),
        )
        return await self._save(workspace_id, result)

    async def history(self, workspace_id: uuid.UUID, limit: int = HISTORY_LIMIT) -> list[AskRecord]:
        await self._workspaces.get(workspace_id)
        async with self._db.connection() as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                "SELECT id, created_at, dashboard FROM askboard.questions"
                " WHERE workspace_id = %s ORDER BY created_at DESC, id LIMIT %s",
                (workspace_id, limit),
            )
            rows = await cur.fetchall()
        return [AskRecord(**r["dashboard"], id=r["id"], created_at=r["created_at"]) for r in rows]

    async def _save(self, workspace_id: uuid.UUID, result: AskResult) -> AskRecord:
        async with self._db.connection() as conn:
            cur = await conn.execute(
                "INSERT INTO askboard.questions (workspace_id, question, queries, dashboard, error)"
                " VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at",
                (
                    workspace_id,
                    result.question,
                    Jsonb([p.sql for p in result.panels]),
                    Jsonb(result.model_dump(mode="json")),
                    result.error,
                ),
            )
            question_id, created_at = await cur.fetchone()
        return AskRecord(**result.model_dump(), id=question_id, created_at=created_at)
