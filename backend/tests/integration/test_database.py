import psycopg
import pytest

from askboard.db.database import Database

pytestmark = pytest.mark.integration


async def test_ping_returns_true_when_reachable(database):
    assert await database.ping() is True


async def test_ping_returns_false_when_unreachable():
    db = Database("postgresql://nobody:nothing@localhost:1/none", min_size=1, max_size=1, connect_timeout=1)
    await db.open(wait=False)
    try:
        assert await db.ping() is False
    finally:
        await db.close()


async def test_migrate_creates_metadata_tables(database):
    applied = await database.migrate()

    assert applied[:2] == ["001", "002"]
    async with database.connection() as conn:
        rows = await (await conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'askboard'"
        )).fetchall()
    tables = {r[0] for r in rows}
    assert {"workspaces", "datasets", "columns", "relationships", "questions", "schema_migrations"} <= tables


async def test_migrate_is_idempotent(database):
    await database.migrate()
    assert await database.migrate() == []


async def test_reader_role_cannot_read_metadata(database):
    await database.migrate()

    async with database.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with conn.transaction():
                await conn.execute("SET LOCAL ROLE askboard_reader")
                await conn.execute("SELECT * FROM askboard.workspaces")


async def test_reader_role_cannot_create_tables(database):
    await database.migrate()

    async with database.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with conn.transaction():
                await conn.execute("SET LOCAL ROLE askboard_reader")
                await conn.execute("CREATE TABLE public.hacked (id int)")
