import uuid
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from askboard.ingestion.types import PgType
from askboard.models import ColumnOverride, ConfirmRequest
from askboard.services.errors import ConflictError, InvalidInputError, NotFoundError

pytestmark = pytest.mark.integration


async def preview(workspaces, datasets, raw, filename="pedidos.csv"):
    ws = await workspaces.create("Sales")
    return ws, await datasets.create_preview(ws.id, filename, raw)


def columns_by_name(dataset):
    return {c.name: c for c in dataset.columns}


async def table_columns(db, schema, table):
    async with db.connection() as conn:
        rows = await (await conn.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (schema, table),
        )).fetchall()
    return rows


# --- preview -----------------------------------------------------------------

async def test_preview_infers_brazilian_csv(workspaces, datasets, pedidos_csv):
    _, ds = await preview(workspaces, datasets, pedidos_csv)

    assert ds.status == "pending"
    assert ds.table_name == "pedidos"
    assert ds.source_format.encoding == "cp1252"
    assert ds.source_format.delimiter == ";"
    assert ds.row_count == 5  # one ragged row excluded

    cols = columns_by_name(ds)
    assert list(cols) == ["id", "cliente", "valor_total", "data_do_pedido", "pago", "codigo", "observacao"]
    assert cols["id"].pg_type is PgType.BIGINT and cols["id"].semantic_type == "id"
    assert cols["cliente"].pg_type is PgType.TEXT and cols["cliente"].semantic_type == "categorical"
    assert cols["valor_total"].pg_type is PgType.NUMERIC and cols["valor_total"].semantic_type == "currency"
    assert cols["data_do_pedido"].pg_type is PgType.DATE and cols["data_do_pedido"].semantic_type == "temporal"
    assert cols["pago"].pg_type is PgType.BOOLEAN
    assert cols["codigo"].pg_type is PgType.TEXT  # "A3" breaks the integers
    assert cols["observacao"].original_name == "Observação"
    assert cols["cliente"].sample_values[:3] == ["Ana", "Bruno", "Carla"]


async def test_preview_returns_first_rows_and_ragged_line_errors(workspaces, datasets, pedidos_csv):
    _, ds = await preview(workspaces, datasets, pedidos_csv)

    assert ds.preview_rows[0][:3] == ["1", "Ana", "R$ 1.234,56"]
    assert len(ds.preview_rows) == 5
    assert [(e.line, e.column) for e in ds.load_errors] == [(6, None)]


async def test_preview_does_not_create_the_table(workspaces, datasets, migrated_database, pedidos_csv):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)

    assert await table_columns(migrated_database, ws.schema_name, ds.table_name) == []


async def test_preview_dedupes_table_names_within_workspace(workspaces, datasets, pedidos_csv):
    ws = await workspaces.create("Sales")
    first = await datasets.create_preview(ws.id, "pedidos.csv", pedidos_csv)
    second = await datasets.create_preview(ws.id, "Pedidos.csv", pedidos_csv)

    assert (first.table_name, second.table_name) == ("pedidos", "pedidos_2")


async def test_preview_rejects_invalid_files(workspaces, datasets):
    ws = await workspaces.create("Sales")
    with pytest.raises(InvalidInputError, match="empty"):
        await datasets.create_preview(ws.id, "x.csv", b"")
    with pytest.raises(InvalidInputError, match="no data rows"):
        await datasets.create_preview(ws.id, "x.csv", b"a,b\n")


async def test_preview_unknown_workspace_raises_not_found(datasets, pedidos_csv):
    with pytest.raises(NotFoundError):
        await datasets.create_preview(uuid.uuid4(), "pedidos.csv", pedidos_csv)


# --- confirm -----------------------------------------------------------------

async def test_confirm_loads_table_with_inferred_types(workspaces, datasets, migrated_database, pedidos_csv):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)

    loaded = await datasets.confirm(ws.id, ds.id, ConfirmRequest())

    assert loaded.status == "loaded"
    assert loaded.row_count == 5
    assert loaded.rejected_rows == 1  # the ragged row
    assert await table_columns(migrated_database, ws.schema_name, "pedidos") == [
        ("id", "bigint"),
        ("cliente", "text"),
        ("valor_total", "numeric"),
        ("data_do_pedido", "date"),
        ("pago", "boolean"),
        ("codigo", "text"),
        ("observacao", "text"),
    ]
    async with migrated_database.connection() as conn:
        row = await (await conn.execute(
            f'SELECT valor_total, data_do_pedido, pago FROM "{ws.schema_name}".pedidos WHERE id = 1'
        )).fetchone()
    assert row == (Decimal("1234.56"), date(2024, 1, 15), True)


async def test_confirm_profiles_columns(workspaces, datasets, pedidos_csv):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)

    cols = columns_by_name(await datasets.confirm(ws.id, ds.id, ConfirmRequest()))

    assert cols["id"].is_unique is True
    assert cols["id"].distinct_count == 5
    assert (cols["id"].min_value, cols["id"].max_value) == ("1", "6")
    assert cols["cliente"].is_unique is False
    assert cols["cliente"].sample_values[0] == "Ana"  # most frequent first
    assert cols["valor_total"].null_ratio == pytest.approx(0.2)
    assert cols["observacao"].null_ratio == pytest.approx(0.6)
    assert cols["pago"].min_value is None  # no min/max for booleans


async def test_confirm_applies_renames_and_type_overrides(workspaces, datasets, migrated_database, pedidos_csv):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)

    loaded = await datasets.confirm(ws.id, ds.id, ConfirmRequest(
        table_name="Orders",
        columns=[
            ColumnOverride(position=1, name="Order ID"),
            ColumnOverride(position=4, pg_type=PgType.TEXT),
        ],
    ))

    assert loaded.table_name == "orders"
    cols = columns_by_name(loaded)
    assert "order_id" in cols and cols["order_id"].original_name == "ID"
    columns = dict(await table_columns(migrated_database, ws.schema_name, "orders"))
    assert columns["order_id"] == "bigint"
    assert columns["data_do_pedido"] == "text"


async def test_confirm_rejects_rows_that_do_not_fit_forced_type(workspaces, datasets, pedidos_csv):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)

    loaded = await datasets.confirm(ws.id, ds.id, ConfirmRequest(
        columns=[ColumnOverride(position=6, pg_type=PgType.BIGINT)],  # codigo has "A3"
    ))

    assert loaded.row_count == 4
    assert loaded.rejected_rows == 2  # ragged + "A3"
    errors = {(e.line, e.column, e.value) for e in loaded.load_errors}
    assert (4, "codigo", "A3") in errors
    assert (6, None, None) in errors


async def test_confirm_twice_raises_conflict(workspaces, datasets, pedidos_csv):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)
    await datasets.confirm(ws.id, ds.id, ConfirmRequest())

    with pytest.raises(ConflictError):
        await datasets.confirm(ws.id, ds.id, ConfirmRequest())


@pytest.mark.parametrize("request_", [
    ConfirmRequest(columns=[ColumnOverride(position=99, name="x")]),
    ConfirmRequest(columns=[ColumnOverride(position=1, name="cliente")]),  # duplicate name
    ConfirmRequest(columns=[ColumnOverride(position=1), ColumnOverride(position=1)]),
])
async def test_confirm_rejects_invalid_overrides(workspaces, datasets, pedidos_csv, request_):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)

    with pytest.raises(InvalidInputError):
        await datasets.confirm(ws.id, ds.id, request_)


async def test_confirm_rejects_table_name_already_loaded(workspaces, datasets, pedidos_csv):
    ws = await workspaces.create("Sales")
    first = await datasets.create_preview(ws.id, "pedidos.csv", pedidos_csv)
    second = await datasets.create_preview(ws.id, "other.csv", pedidos_csv)
    await datasets.confirm(ws.id, first.id, ConfirmRequest())

    with pytest.raises(InvalidInputError, match="pedidos"):
        await datasets.confirm(ws.id, second.id, ConfirmRequest(table_name="pedidos"))


async def test_confirm_unknown_dataset_raises_not_found(workspaces, datasets):
    ws = await workspaces.create("Sales")
    with pytest.raises(NotFoundError):
        await datasets.confirm(ws.id, uuid.uuid4(), ConfirmRequest())


async def test_dataset_from_other_workspace_is_not_found(workspaces, datasets, pedidos_csv):
    _, ds = await preview(workspaces, datasets, pedidos_csv)
    other = await workspaces.create("Other")

    with pytest.raises(NotFoundError):
        await datasets.confirm(other.id, ds.id, ConfirmRequest())


async def test_reader_can_select_loaded_table_but_not_write(workspaces, datasets, migrated_database, pedidos_csv):
    ws, ds = await preview(workspaces, datasets, pedidos_csv)
    await datasets.confirm(ws.id, ds.id, ConfirmRequest())

    async with migrated_database.connection() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL ROLE askboard_reader")
            count = await (await conn.execute(f'SELECT count(*) FROM "{ws.schema_name}".pedidos')).fetchone()
        assert count[0] == 5

        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            async with conn.transaction():
                await conn.execute("SET LOCAL ROLE askboard_reader")
                await conn.execute(f'DELETE FROM "{ws.schema_name}".pedidos')


# --- list / get ----------------------------------------------------------------

async def test_list_and_get_datasets(workspaces, datasets, pedidos_csv, customers_csv):
    ws = await workspaces.create("Sales")
    a = await datasets.create_preview(ws.id, "pedidos.csv", pedidos_csv)
    b = await datasets.create_preview(ws.id, "customers.csv", customers_csv)
    await datasets.confirm(ws.id, b.id, ConfirmRequest())

    listed = await datasets.list(ws.id)
    fetched = await datasets.get(ws.id, b.id)

    assert {d.id for d in listed} == {a.id, b.id}
    assert fetched.status == "loaded"
    assert [c.name for c in fetched.columns] == ["customer_id", "name", "city", "signup_date"]
