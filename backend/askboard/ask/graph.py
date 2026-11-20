"""LangGraph pipeline: question -> plan -> (SQL -> guard -> run -> correct?)* -> narrative.

    START -> prepare -> plan -> generate_sql -> execute --ok, more steps--> generate_sql
                 |                   |             |  \--ok, done-------> narrative -> END
                 v                   |             |  \--error, retries left--> correct -> execute
                END (bad input)      +-- error ----+--error, no retries--> give_up --> generate_sql | narrative
"""

import logging
import re
import unicodedata
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from askboard.ask.llm import LLMError, StructuredLLM
from askboard.ask.prompts import (
    CorrectionOutput,
    NarrativeOutput,
    PlanOutput,
    SQLOutput,
    correction_prompts,
    narrative_prompts,
    plan_prompts,
    sql_prompts,
)
from askboard.ask.query_runner import QueryExecutionError, QueryResult
from askboard.ask.sql_guard import UnsafeQueryError, check_sql
from askboard.models import AskResult, FailedStep, Panel, PanelColumn
from askboard.viz.rules import plan_chart

logger = logging.getLogger(__name__)

NARRATIVE_MAX_ROWS = 30
BLANK_QUESTION = "Please type a question."
NO_DATA = "This workspace has no loaded data yet. Upload a CSV first."
VALUE_FORMATS = {"number", "integer", "currency", "percent"}
_CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")


class Runner:  # structural type of QueryRunner, so tests can pass a fake
    async def run(self, schema: str, query: str) -> QueryResult: ...


class AskState(TypedDict, total=False):
    question: str
    previous_questions: list[str]
    standalone_question: str
    schema_name: str
    context: str
    allowed_tables: list[str]
    sub_questions: list[str]
    step: int
    current_sql: str | None
    attempts: int
    last_error: str | None
    panels: list[Panel]
    failed_steps: list[FailedStep]
    title: str
    summary: list[str]
    follow_ups: list[str]
    currency: str | None
    error: str | None


def _sanitize(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    return "".join(c for c in normalized if c.isprintable() or c in "\n\t").strip()


class AskGraph:
    def __init__(self, llm: StructuredLLM, runner: Runner, *, max_correction_attempts: int, max_sub_questions: int = 3):
        self._llm = llm
        self._runner = runner
        self._max_corrections = max_correction_attempts
        self._max_sub_questions = max_sub_questions
        self._graph = self._build()

    async def answer(
        self,
        *,
        question: str,
        schema_name: str,
        context: str,
        allowed_tables: set[str],
        previous_questions: list[str] | None = None,
    ) -> AskResult:
        state: AskState = await self._graph.ainvoke({
            "question": question,
            "previous_questions": [q for q in (_sanitize(p) for p in previous_questions or []) if q],
            "schema_name": schema_name,
            "context": context,
            "allowed_tables": sorted(allowed_tables),
            "panels": [],
            "failed_steps": [],
        })
        clean_question = state.get("question") or question
        return AskResult(
            question=clean_question,
            title=state.get("title") or clean_question,
            summary=state.get("summary") or [],
            panels=state.get("panels") or [],
            follow_ups=state.get("follow_ups") or [],
            currency=state.get("currency"),
            failed_steps=state.get("failed_steps") or [],
            error=state.get("error"),
        )

    # --- nodes -----------------------------------------------------------------------

    async def _prepare(self, state: AskState) -> dict:
        question = _sanitize(state["question"])
        if not question:
            return {"question": question, "error": BLANK_QUESTION}
        if not state["context"].strip():
            return {"question": question, "error": NO_DATA}
        return {"question": question}

    async def _plan(self, state: AskState) -> dict:
        previous = state.get("previous_questions") or []
        base = state["question"]
        try:
            plan = await self._llm.generate(*plan_prompts(base, state["context"], previous), PlanOutput)
            subs = [q.strip() for q in plan.sub_questions if q.strip()][: self._max_sub_questions]
            if previous and plan.standalone_question and plan.standalone_question.strip():
                base = _sanitize(plan.standalone_question)
        except LLMError:
            logger.warning("Planner failed; answering the question as a single step", exc_info=True)
            subs = []
        return {"sub_questions": subs or [base], "standalone_question": base, "step": 0}

    async def _generate_sql(self, state: AskState) -> dict:
        question = state["sub_questions"][state["step"]]
        try:
            output = await self._llm.generate(*sql_prompts(question, state["context"]), SQLOutput)
        except LLMError as exc:
            return {"current_sql": None, "attempts": 0, "last_error": str(exc)}
        return {"current_sql": output.sql, "attempts": 0, "last_error": None}

    async def _execute(self, state: AskState) -> dict:
        try:
            sql = check_sql(
                state["current_sql"] or "", schema=state["schema_name"], allowed_tables=set(state["allowed_tables"])
            )
            result = await self._runner.run(state["schema_name"], sql)
        except (UnsafeQueryError, QueryExecutionError) as exc:
            logger.info("Step %d query failed: %s", state["step"] + 1, exc)
            return {"last_error": str(exc)}

        columns = [PanelColumn(name=c.name, type=c.type) for c in result.columns]
        chart = plan_chart(columns, result.rows)
        panels = list(state["panels"])
        panels.append(Panel(
            id=f"p{len(panels) + 1}",
            type=chart.type,
            title=state["sub_questions"][state["step"]],
            sql=sql,
            columns=columns,
            rows=result.rows,
            truncated=result.truncated,
            encoding=chart.encoding,
            alternatives=chart.alternatives,
            formats=chart.formats,
        ))
        return {"panels": panels, "step": state["step"] + 1, "current_sql": None, "last_error": None}

    async def _correct(self, state: AskState) -> dict:
        question = state["sub_questions"][state["step"]]
        prompts = correction_prompts(question, state["context"], state["current_sql"] or "", state["last_error"] or "")
        try:
            output = await self._llm.generate(*prompts, CorrectionOutput)
        except LLMError as exc:
            return {"attempts": self._max_corrections, "last_error": str(exc)}
        return {"current_sql": output.sql, "attempts": state["attempts"] + 1, "last_error": None}

    async def _give_up(self, state: AskState) -> dict:
        failed = list(state["failed_steps"])
        failed.append(FailedStep(
            question=state["sub_questions"][state["step"]],
            sql=state.get("current_sql"),
            error=state.get("last_error") or "Unknown error",
        ))
        return {"failed_steps": failed, "step": state["step"] + 1, "current_sql": None, "last_error": None}

    async def _narrative(self, state: AskState) -> dict:
        if not state["panels"]:
            reasons = "; ".join(s.error for s in state["failed_steps"]) or "no query succeeded"
            return {"error": f"Could not answer the question: {reasons}"}

        steps = [
            {
                "id": p.id,
                "question": p.title,
                "chart": p.type,
                "alternatives": p.alternatives,
                "columns": [c.name for c in p.columns],
                "rows": p.rows[:NARRATIVE_MAX_ROWS],
                "truncated": p.truncated or len(p.rows) > NARRATIVE_MAX_ROWS,
            }
            for p in state["panels"]
        ]
        question = state.get("standalone_question") or state["question"]
        try:
            output = await self._llm.generate(*narrative_prompts(question, steps), NarrativeOutput)
        except LLMError:
            logger.warning("Narrative failed; returning panels without summary", exc_info=True)
            return {"title": state["question"], "summary": [], "follow_ups": []}
        currency = (output.currency or "").strip().upper()
        return {
            "title": output.title,
            "summary": output.summary,
            "follow_ups": output.follow_ups,
            "panels": [self._styled(p, output) for p in state["panels"]],
            "currency": currency if _CURRENCY_CODE.match(currency) else None,
        }

    @staticmethod
    def _styled(panel: Panel, output: NarrativeOutput) -> Panel:
        style = next((s for s in output.panels if s.id == panel.id), None)
        if style is None:
            return panel
        updates: dict[str, Any] = {}
        if style.chart and style.chart in panel.alternatives:
            updates["type"] = style.chart
            updates["alternatives"] = [t for t in [panel.type, *panel.alternatives] if t != style.chart]
        if style.title and style.title.strip():
            updates["title"] = style.title.strip()
        formats = {
            col: fmt for col, fmt in style.formats.items() if col in panel.formats and fmt in VALUE_FORMATS
        }
        if formats:
            updates["formats"] = {**panel.formats, **formats}
        return panel.model_copy(update=updates)

    # --- routing ---------------------------------------------------------------------

    def _after_prepare(self, state: AskState) -> str:
        return END if state.get("error") else "plan"

    def _after_generate(self, state: AskState) -> str:
        return "give_up" if state.get("last_error") else "execute"

    def _after_execute(self, state: AskState) -> str:
        if state.get("last_error"):
            return "correct" if state["attempts"] < self._max_corrections else "give_up"
        return self._next_step(state)

    def _after_correct(self, state: AskState) -> str:
        return "give_up" if state.get("last_error") else "execute"

    def _next_step(self, state: AskState) -> str:
        return "generate_sql" if state["step"] < len(state["sub_questions"]) else "narrative"

    def _build(self) -> Any:
        g = StateGraph(AskState)
        g.add_node("prepare", self._prepare)
        g.add_node("plan", self._plan)
        g.add_node("generate_sql", self._generate_sql)
        g.add_node("execute", self._execute)
        g.add_node("correct", self._correct)
        g.add_node("give_up", self._give_up)
        g.add_node("narrative", self._narrative)

        g.add_edge(START, "prepare")
        g.add_conditional_edges("prepare", self._after_prepare, ["plan", END])
        g.add_edge("plan", "generate_sql")
        g.add_conditional_edges("generate_sql", self._after_generate, ["execute", "give_up"])
        g.add_conditional_edges("execute", self._after_execute, ["correct", "give_up", "generate_sql", "narrative"])
        g.add_conditional_edges("correct", self._after_correct, ["execute", "give_up"])
        g.add_conditional_edges("give_up", self._next_step, ["generate_sql", "narrative"])
        g.add_edge("narrative", END)
        return g.compile()
