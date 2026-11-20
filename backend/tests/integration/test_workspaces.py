import uuid

import psycopg
import pytest

from askboard.services.errors import InvalidInputError, NotFoundError

pytestmark = pytest.mark.integration


async def test_create_workspace_creates_its_schema(workspaces, migrated_database):
    ws = await workspaces.create("Sales 2024")

    assert ws.name == "Sales 2024"
    assert ws.schema_name.startswith("ws_")
    async with migrated_database.connection() as conn:
        row = await (await conn.execute(
            "SELECT 1 FROM pg_namespace WHERE nspname = %s", (ws.schema_name,)
        )).fetchone()
    assert row is not None


async def test_reader_can_use_workspace_schema(workspaces, migrated_database):
    ws = await workspaces.create("Sales")

    async with migrated_database.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE askboard_reader")
            row = await (await conn.execute(
                "SELECT has_schema_privilege(%s, 'USAGE')", (ws.schema_name,)
            )).fetchone()
    assert row[0] is True


async def test_workspace_name_is_trimmed_and_required(workspaces):
    assert (await workspaces.create("  Ops  ")).name == "Ops"
    with pytest.raises(InvalidInputError):
        await workspaces.create("   ")


async def test_list_returns_newest_first(workspaces):
    first = await workspaces.create("first")
    second = await workspaces.create("second")

    assert [w.id for w in await workspaces.list()] == [second.id, first.id]


async def test_get_returns_workspace(workspaces):
    ws = await workspaces.create("x")
    assert await workspaces.get(ws.id) == ws


async def test_get_unknown_workspace_raises_not_found(workspaces):
    with pytest.raises(NotFoundError):
        await workspaces.get(uuid.uuid4())


async def test_reader_cannot_create_tables_in_workspace_schema(workspaces, migrated_database):
    ws = await workspaces.create("x")

    async with migrated_database.connection() as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with conn.transaction():
                await conn.execute("SET LOCAL ROLE askboard_reader")
                await conn.execute(f'CREATE TABLE "{ws.schema_name}".hacked (id int)')
