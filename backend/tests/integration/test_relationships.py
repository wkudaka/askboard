import uuid

import pytest

from askboard.models import ConfirmRequest
from askboard.services.errors import NotFoundError
from askboard.services.relationships import RelationshipService
from tests.integration.conftest import FIXTURES

pytestmark = pytest.mark.integration


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


async def load(datasets, workspace_id, filename: str, fixture_name: str):
    preview = await datasets.create_preview(workspace_id, filename, fixture(fixture_name))
    return await datasets.confirm(workspace_id, preview.id, ConfirmRequest())


@pytest.fixture
def relationships(migrated_database) -> RelationshipService:
    return RelationshipService(migrated_database)


def described(rels):
    return [(r.from_table, r.from_column, r.to_table, r.to_column, r.status, r.confidence) for r in rels]


async def test_suggests_relationship_after_loading_both_tables(workspaces, datasets, relationships):
    ws = await workspaces.create("Loja")
    await load(datasets, ws.id, "clientes.csv", "loja_clientes.csv")
    await load(datasets, ws.id, "pedidos.csv", "loja_pedidos.csv")

    assert described(await relationships.list(ws.id)) == [
        ("pedidos", "cliente_id", "clientes", "id", "suggested", 1.0),
    ]


async def test_upload_order_does_not_matter(workspaces, datasets, relationships):
    ws = await workspaces.create("Loja")
    await load(datasets, ws.id, "pedidos.csv", "loja_pedidos.csv")
    await load(datasets, ws.id, "clientes.csv", "loja_clientes.csv")

    assert [(r.from_table, r.to_table) for r in await relationships.list(ws.id)] == [("pedidos", "clientes")]


async def test_low_value_overlap_is_not_suggested(workspaces, datasets, relationships):
    ws = await workspaces.create("Loja")
    await load(datasets, ws.id, "clientes.csv", "loja_clientes.csv")
    await load(datasets, ws.id, "pedidos.csv", "loja_pedidos_orfaos.csv")  # 1 of 4 ids exist

    assert await relationships.list(ws.id) == []


async def test_confirm_and_reject(workspaces, datasets, relationships):
    ws = await workspaces.create("Loja")
    await load(datasets, ws.id, "clientes.csv", "loja_clientes.csv")
    await load(datasets, ws.id, "pedidos.csv", "loja_pedidos.csv")
    [rel] = await relationships.list(ws.id)

    confirmed = await relationships.set_status(ws.id, rel.id, "confirmed")
    rejected = await relationships.set_status(ws.id, rel.id, "rejected")

    assert (confirmed.status, rejected.status) == ("confirmed", "rejected")
    assert [r.status for r in await relationships.list(ws.id)] == ["rejected"]


async def test_user_decisions_survive_new_uploads(workspaces, datasets, relationships, pedidos_csv):
    ws = await workspaces.create("Loja")
    await load(datasets, ws.id, "clientes.csv", "loja_clientes.csv")
    await load(datasets, ws.id, "pedidos.csv", "loja_pedidos.csv")
    [rel] = await relationships.list(ws.id)
    await relationships.set_status(ws.id, rel.id, "rejected")

    await load(datasets, ws.id, "outros.csv", "customers.csv")

    assert [r.status for r in await relationships.list(ws.id)] == ["rejected"]


async def test_unknown_or_foreign_relationship_is_not_found(workspaces, datasets, relationships):
    ws = await workspaces.create("Loja")
    other = await workspaces.create("Outra")
    await load(datasets, ws.id, "clientes.csv", "loja_clientes.csv")
    await load(datasets, ws.id, "pedidos.csv", "loja_pedidos.csv")
    [rel] = await relationships.list(ws.id)

    with pytest.raises(NotFoundError):
        await relationships.set_status(ws.id, uuid.uuid4(), "confirmed")
    with pytest.raises(NotFoundError):
        await relationships.set_status(other.id, rel.id, "confirmed")
