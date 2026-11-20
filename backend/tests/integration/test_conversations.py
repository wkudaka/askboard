import uuid

import psycopg
import pytest

from askboard.ask.prompts import NarrativeOutput, PlanOutput, SQLOutput
from askboard.ask.query_runner import QueryRunner
from askboard.db.migrations import MIGRATIONS_DIR, discover_migrations
from askboard.models import ConfirmRequest
from askboard.services.ask import AskService
from askboard.services.conversations import ConversationService
from askboard.services.errors import NotFoundError
from tests.fakes import ScriptedLLM

pytestmark = pytest.mark.integration

SQL = "SELECT cliente, sum(valor_total) AS total FROM pedidos GROUP BY cliente ORDER BY cliente"
SQL_MONTH = "SELECT date_trunc('month', data_pedido) AS mes, count(*) AS pedidos FROM pedidos GROUP BY 1 ORDER BY 1"


def scripted(*plans: PlanOutput, sqls=(SQL,)):
    return ScriptedLLM({
        PlanOutput: list(plans) or [PlanOutput(sub_questions=[])],
        SQLOutput: [SQLOutput(sql=s) for s in sqls],
        NarrativeOutput: [NarrativeOutput(title=f"Resposta {i}", summary=[], follow_ups=[]) for i in range(len(sqls))],
    })


def make_service(db, datasets, llm):
    return AskService(
        db,
        datasets,
        runner=QueryRunner(db, statement_timeout_ms=5000, max_rows=100),
        llm_factory=lambda: llm,
        max_correction_attempts=0,
    )


@pytest.fixture
async def loaded(workspaces, datasets, pedidos_csv):
    ws = await workspaces.create("Sales")
    ds = await datasets.create_preview(ws.id, "pedidos.csv", pedidos_csv)
    await datasets.confirm(ws.id, ds.id, ConfirmRequest())
    return ws


async def test_first_question_starts_a_conversation_titled_after_it(migrated_database, datasets, loaded):
    service = make_service(migrated_database, datasets, scripted())

    record = await service.ask(loaded.id, "Quanto cada cliente gastou?")

    [conversation] = await ConversationService(migrated_database).list(loaded.id)
    assert conversation.id == record.conversation_id
    assert conversation.title == "Quanto cada cliente gastou?"


async def test_follow_up_joins_the_conversation_and_gets_its_context(migrated_database, datasets, loaded):
    llm = scripted(
        PlanOutput(sub_questions=[]),
        PlanOutput(standalone_question="Quantos pedidos por mês?", sub_questions=[]),
        sqls=(SQL, SQL_MONTH),
    )
    service = make_service(migrated_database, datasets, llm)
    conversations = ConversationService(migrated_database)

    first = await service.ask(loaded.id, "Quantos pedidos por cliente?")
    second = await service.ask(loaded.id, "E por mês?", first.conversation_id)

    assert second.conversation_id == first.conversation_id
    assert len(await conversations.list(loaded.id)) == 1
    _, plan_user = llm.calls_for(PlanOutput)[1]
    assert "<previous_questions>\n- Quantos pedidos por cliente?\n</previous_questions>" in plan_user
    _, sql_user = llm.calls_for(SQLOutput)[1]
    assert "Quantos pedidos por mês?" in sql_user

    detail = await conversations.detail(loaded.id, first.conversation_id)
    assert [m.question for m in detail.messages] == ["Quantos pedidos por cliente?", "E por mês?"]
    assert detail.updated_at == second.created_at


async def test_conversations_are_listed_by_latest_activity(migrated_database, datasets, loaded):
    service = make_service(migrated_database, datasets, scripted(*[PlanOutput()] * 3, sqls=(SQL,) * 3))
    a = await service.ask(loaded.id, "Primeira?")
    b = await service.ask(loaded.id, "Segunda?")
    await service.ask(loaded.id, "De volta à primeira", a.conversation_id)

    listed = await ConversationService(migrated_database).list(loaded.id)

    assert [c.id for c in listed] == [a.conversation_id, b.conversation_id]


async def test_unknown_or_foreign_conversation_is_not_found(migrated_database, workspaces, datasets, loaded):
    other = await workspaces.create("Other")
    service = make_service(migrated_database, datasets, scripted())
    record = await service.ask(loaded.id, "Primeira?")

    with pytest.raises(NotFoundError):
        await service.ask(other.id, "Invasão?", record.conversation_id)
    with pytest.raises(NotFoundError):
        await service.ask(loaded.id, "Perdida?", uuid.uuid4())
    with pytest.raises(NotFoundError):
        await ConversationService(migrated_database).detail(other.id, record.conversation_id)


async def test_rename_and_delete(migrated_database, datasets, loaded):
    service = make_service(migrated_database, datasets, scripted())
    record = await service.ask(loaded.id, "Primeira?")
    conversations = ConversationService(migrated_database)

    renamed = await conversations.rename(loaded.id, record.conversation_id, "Clientes")
    assert renamed.title == "Clientes"

    await conversations.delete(loaded.id, record.conversation_id)
    assert await conversations.list(loaded.id) == []
    assert await service.history(loaded.id) == []
    with pytest.raises(NotFoundError):
        await conversations.delete(loaded.id, record.conversation_id)


async def test_migration_groups_earlier_questions_into_one_conversation(database):
    """Questions saved before 004 end up in an 'Earlier questions' thread per workspace."""
    async with database.connection() as conn:
        await conn.execute(
            "CREATE SCHEMA askboard; CREATE TABLE askboard.schema_migrations ("
            " version text PRIMARY KEY, name text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        for m in discover_migrations(MIGRATIONS_DIR):
            if int(m.version) < 4:
                await conn.execute(m.sql())
                await conn.execute(
                    "INSERT INTO askboard.schema_migrations (version, name) VALUES (%s, %s)", (m.version, m.name)
                )
        cur = await conn.execute(
            "INSERT INTO askboard.workspaces (name, schema_name) VALUES ('A', 'ws_a'), ('B', 'ws_b') RETURNING id"
        )
        ws_a, ws_b = [r[0] for r in await cur.fetchall()]
        await conn.execute(
            "INSERT INTO askboard.questions (workspace_id, question, created_at) VALUES"
            " (%s, 'q1', '2026-01-01'), (%s, 'q2', '2026-01-02'), (%s, 'q3', '2026-01-03')",
            (ws_a, ws_a, ws_b),
        )

    assert await database.migrate() == [m.version for m in discover_migrations(MIGRATIONS_DIR) if int(m.version) >= 4]

    conversations = ConversationService(database)
    [conv_a] = await conversations.list(ws_a)
    [conv_b] = await conversations.list(ws_b)
    assert conv_a.title == conv_b.title == "Earlier questions"
    assert conv_a.created_at.day == 1 and conv_a.updated_at.day == 2
    async with database.connection() as conn:
        cur = await conn.execute(
            "SELECT conversation_id, count(*) FROM askboard.questions GROUP BY 1 ORDER BY 2 DESC"
        )
        assert await cur.fetchall() == [(conv_a.id, 2), (conv_b.id, 1)]
        with pytest.raises(psycopg.errors.NotNullViolation):
            await conn.execute(
                "INSERT INTO askboard.questions (workspace_id, question) VALUES (%s, 'orphan')", (ws_a,)
            )
