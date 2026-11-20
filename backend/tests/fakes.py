"""Test doubles for the ask pipeline."""

from typing import Any

from askboard.ask.query_runner import QueryResult, ResultColumn

RESULT = QueryResult(
    columns=[ResultColumn("cliente", "text"), ResultColumn("total", "number")],
    rows=[["Ana", 1341.71], ["Bruno", 10.0]],
    truncated=False,
)


class ScriptedLLM:
    """Returns queued responses per output schema; an Exception instance is raised."""

    def __init__(self, script: dict[type, list[Any]]):
        self._script = {k: list(v) for k, v in script.items()}
        self.calls: list[tuple[type, str, str]] = []

    async def generate(self, system_prompt, user_prompt, schema):
        self.calls.append((schema, system_prompt, user_prompt))
        queue = self._script.get(schema)
        if not queue:
            raise AssertionError(f"Unexpected LLM call for {schema.__name__}")
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def calls_for(self, schema) -> list[tuple[str, str]]:
        return [(s, u) for sch, s, u in self.calls if sch is schema]


class FakeRunner:
    def __init__(self, results: dict[str, QueryResult | Exception] | None = None):
        self._results = results or {}
        self.calls: list[tuple[str, str]] = []

    async def run(self, schema, sql):
        self.calls.append((schema, sql))
        outcome = self._results.get(sql, RESULT)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
