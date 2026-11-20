import pytest

from askboard.ask.query_runner import QueryExecutionError, QueryRunner, ResultColumn
from askboard.models import ConfirmRequest

pytestmark = pytest.mark.integration


@pytest.fixture
async def loaded_workspace(workspaces, datasets, pedidos_csv):
    ws = await workspaces.create("Sales")
    ds = await datasets.create_preview(ws.id, "pedidos.csv", pedidos_csv)
    await datasets.confirm(ws.id, ds.id, ConfirmRequest())
    return ws


def runner(db, **kwargs) -> QueryRunner:
    return QueryRunner(db, **{"statement_timeout_ms": 5000, "max_rows": 100, **kwargs})


async def test_runs_query_with_unqualified_table_names(migrated_database, loaded_workspace):
    result = await runner(migrated_database).run(
        loaded_workspace.schema_name,
        "SELECT cliente, sum(valor_total) AS total FROM pedidos GROUP BY cliente ORDER BY cliente",
    )

    assert result.columns == [ResultColumn("cliente", "text"), ResultColumn("total", "number")]
    assert result.rows == [["Ana", 1341.71], ["Bruno", 10.0], ["Carla", None]]
    assert result.truncated is False


async def test_values_are_json_friendly(migrated_database, loaded_workspace):
    result = await runner(migrated_database).run(
        loaded_workspace.schema_name,
        "SELECT id, data_do_pedido, pago, valor_total, now()::timestamp AS ts FROM pedidos WHERE id = 1",
    )

    assert [c.type for c in result.columns] == ["number", "date", "boolean", "number", "timestamp"]
    row = result.rows[0]
    assert row[:4] == [1, "2024-01-15", True, 1234.56]
    assert isinstance(row[4], str) and "T" in row[4]


async def test_truncates_to_max_rows(migrated_database, loaded_workspace):
    result = await runner(migrated_database, max_rows=2).run(
        loaded_workspace.schema_name, "SELECT id FROM pedidos ORDER BY id"
    )

    assert result.rows == [[1], [2]]
    assert result.truncated is True


async def test_runs_as_read_only_reader(migrated_database, loaded_workspace):
    result = await runner(migrated_database).run(
        loaded_workspace.schema_name,
        "SELECT current_user AS who, current_setting('transaction_read_only') AS ro",
    )

    assert result.rows == [["askboard_reader", "on"]]


async def test_metadata_schema_is_off_limits_even_without_the_guard(migrated_database, loaded_workspace):
    with pytest.raises(QueryExecutionError, match="permission denied"):
        await runner(migrated_database).run(loaded_workspace.schema_name, "SELECT * FROM askboard.workspaces")


async def test_statement_timeout(migrated_database, loaded_workspace):
    with pytest.raises(QueryExecutionError, match="timeout"):
        await runner(migrated_database, statement_timeout_ms=200).run(
            loaded_workspace.schema_name, "SELECT pg_sleep(2)"
        )


async def test_invalid_sql_raises_with_postgres_message(migrated_database, loaded_workspace):
    with pytest.raises(QueryExecutionError, match="nao_existe"):
        await runner(migrated_database).run(loaded_workspace.schema_name, "SELECT nao_existe FROM pedidos")


async def test_connection_is_reusable_after_an_error(migrated_database, loaded_workspace):
    r = runner(migrated_database)
    with pytest.raises(QueryExecutionError):
        await r.run(loaded_workspace.schema_name, "SELECT nao_existe FROM pedidos")

    result = await r.run(loaded_workspace.schema_name, "SELECT count(*) AS n FROM pedidos")

    assert result.rows == [[5]]
