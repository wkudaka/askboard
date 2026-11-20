import uuid

import pytest

from askboard.ask.llm import LLMNotConfiguredError
from askboard.ask.prompts import NarrativeOutput, PlanOutput, SQLOutput
from askboard.ask.query_runner import QueryRunner
from askboard.models import ConfirmRequest
from askboard.services.ask import AskService
from askboard.services.errors import NotFoundError
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.integration

SQL = "SELECT cliente, sum(valor_total) AS total FROM pedidos GROUP BY cliente ORDER BY cliente"
NARRATIVE = NarrativeOutput(title="Receita por cliente", summary=["Ana lidera"], follow_ups=["E por mês?"])


def scripted(sql=SQL):
    return ScriptedLLM({
        PlanOutput: [PlanOutput(sub_questions=[])],
        SQLOutput: [SQLOutput(sql=sql)],
        NarrativeOutput: [NARRATIVE],
    })


def make_service(db, datasets, llm, max_corrections=2):
    def factory():
        if isinstance(llm, Exception):
            raise llm
        return llm

    return AskService(
        db,
        datasets,
        runner=QueryRunner(db, statement_timeout_ms=5000, max_rows=100),
        llm_factory=factory,
        max_correction_attempts=max_corrections,
    )


@pytest.fixture
async def loaded(workspaces, datasets, pedidos_csv):
    ws = await workspaces.create("Sales")
    ds = await datasets.create_preview(ws.id, "pedidos.csv", pedidos_csv)
    await datasets.confirm(ws.id, ds.id, ConfirmRequest())
    return ws


async def test_answers_with_rows_from_the_workspace(migrated_database, datasets, loaded):
    llm = scripted()
    service = make_service(migrated_database, datasets, llm)

    record = await service.ask(loaded.id, "Quanto cada cliente gastou?")

    assert record.error is None
    assert record.title == "Receita por cliente"
    assert record.panels[0].rows == [["Ana", 1341.71], ["Bruno", 10.0], ["Carla", None]]
    system, _ = llm.calls_for(SQLOutput)[0]
    assert "Table pedidos" in system and "valor_total: numeric, currency" in system


async def test_questions_are_persisted_newest_first(migrated_database, datasets, loaded):
    service = make_service(migrated_database, datasets, scripted())
    first = await service.ask(loaded.id, "Primeira?")
    service = make_service(migrated_database, datasets, scripted())
    second = await service.ask(loaded.id, "Segunda?")

    history = await service.history(loaded.id)

    assert [r.id for r in history] == [second.id, first.id]
    assert history[1].panels[0].rows == first.panels[0].rows
    assert history[1].question == "Primeira?"


async def test_other_workspaces_tables_are_unreachable(migrated_database, workspaces, datasets, loaded, pedidos_csv):
    other = await workspaces.create("Other")
    ds = await datasets.create_preview(other.id, "segredo.csv", pedidos_csv)
    await datasets.confirm(other.id, ds.id, ConfirmRequest())
    service = make_service(
        migrated_database, datasets, scripted(f"SELECT * FROM {other.schema_name}.segredo"), max_corrections=0
    )

    record = await service.ask(loaded.id, "Mostre os segredos")

    assert record.panels == []
    assert "Schema not allowed" in record.error


async def test_workspace_without_loaded_data(migrated_database, workspaces, datasets):
    ws = await workspaces.create("Empty")
    service = make_service(migrated_database, datasets, ScriptedLLM({}))

    record = await service.ask(ws.id, "Qualquer coisa?")

    assert "Upload" in record.error
    assert [r.id for r in await service.history(ws.id)] == [record.id]


async def test_unknown_workspace(migrated_database, datasets):
    service = make_service(migrated_database, datasets, scripted())

    with pytest.raises(NotFoundError):
        await service.ask(uuid.uuid4(), "Oi?")


async def test_missing_llm_configuration_propagates(migrated_database, datasets, loaded):
    service = make_service(migrated_database, datasets, LLMNotConfiguredError("OPENROUTER_API_KEY is not set"))

    with pytest.raises(LLMNotConfiguredError):
        await service.ask(loaded.id, "Oi?")
