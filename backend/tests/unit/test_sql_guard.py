import pytest

from askboard.ask.sql_guard import UnsafeQueryError, check_sql

SCHEMA = "ws_abc"
TABLES = {"pedidos", "clientes"}


def ok(sql: str) -> str:
    return check_sql(sql, schema=SCHEMA, allowed_tables=TABLES)


def rejected(sql: str) -> str:
    with pytest.raises(UnsafeQueryError) as exc:
        check_sql(sql, schema=SCHEMA, allowed_tables=TABLES)
    return str(exc.value)


# --- allowed ---------------------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "SELECT * FROM pedidos",
    "select cliente, sum(valor_total) as total from pedidos group by cliente order by total desc",
    "SELECT p.cliente, c.cidade FROM pedidos p JOIN clientes c ON c.nome = p.cliente",
    "WITH t AS (SELECT cliente, count(*) AS n FROM pedidos GROUP BY cliente) SELECT * FROM t WHERE n > 1",
    "SELECT cliente FROM pedidos UNION ALL SELECT nome FROM clientes",
    "SELECT * FROM ws_abc.pedidos",
    'SELECT * FROM "pedidos"',
    "SELECT date_trunc('month', data_do_pedido) AS mes, sum(valor_total) FROM pedidos GROUP BY 1",
    "SELECT cliente, rank() OVER (ORDER BY valor_total DESC) FROM pedidos",
    "SELECT count(*) FROM pedidos WHERE id IN (SELECT id FROM pedidos WHERE pago)",
    "SELECT 1",
])
def test_allows_read_only_queries_over_workspace_tables(sql):
    assert ok(sql)


def test_strips_trailing_semicolons_and_whitespace():
    assert ok("  SELECT * FROM pedidos ;  \n") == "SELECT * FROM pedidos"


def test_strips_markdown_fences_from_llm_output():
    assert ok("```sql\nSELECT * FROM pedidos\n```") == "SELECT * FROM pedidos"


# --- rejected: not a single read-only statement -------------------------------------------

@pytest.mark.parametrize("sql", [
    "DELETE FROM pedidos",
    "UPDATE pedidos SET valor_total = 0",
    "INSERT INTO pedidos (id) VALUES (1)",
    "DROP TABLE pedidos",
    "TRUNCATE pedidos",
    "ALTER TABLE pedidos ADD COLUMN x int",
    "CREATE TABLE x AS SELECT * FROM pedidos",
    "GRANT ALL ON pedidos TO public",
    "COPY pedidos TO '/tmp/x.csv'",
    "SET ROLE postgres",
    "SELECT * INTO novo FROM pedidos",
    "WITH d AS (DELETE FROM pedidos RETURNING *) SELECT * FROM d",
])
def test_rejects_writes_and_ddl(sql):
    rejected(sql)


def test_rejects_multiple_statements():
    assert "single" in rejected("SELECT * FROM pedidos; DROP TABLE pedidos")


@pytest.mark.parametrize("sql", ["", "   ", "this is not sql at all ((("])
def test_rejects_empty_or_unparsable(sql):
    rejected(sql)


# --- rejected: outside the workspace --------------------------------------------------------

def test_rejects_unknown_tables():
    assert "vendas" in rejected("SELECT * FROM vendas")


@pytest.mark.parametrize("sql", [
    "SELECT * FROM askboard.workspaces",
    "SELECT * FROM ws_other.pedidos",
    "SELECT * FROM pg_catalog.pg_user",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM pg_shadow",
    "SELECT * FROM otherdb.ws_abc.pedidos",
])
def test_rejects_other_schemas_and_catalogs(sql):
    rejected(sql)


def test_cte_names_are_not_treated_as_tables():
    assert ok("WITH vendas AS (SELECT * FROM pedidos) SELECT * FROM vendas")


def test_cte_cannot_hide_a_forbidden_table():
    rejected("WITH x AS (SELECT * FROM askboard.workspaces) SELECT * FROM x")


# --- rejected: dangerous functions ------------------------------------------------------------

@pytest.mark.parametrize("sql", [
    "SELECT pg_sleep(10)",
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT set_config('role', 'postgres', false)",
    "SELECT current_setting('data_directory')",
    "SELECT lo_import('/etc/passwd')",
    "SELECT dblink('host=evil', 'select 1')",
    "SELECT * FROM pedidos WHERE pg_terminate_backend(1)",
    "SELECT version()",
    "SELECT query_to_xml('select * from askboard.workspaces', true, true, '')",
])
def test_rejects_dangerous_functions(sql):
    rejected(sql)


def test_rejects_row_locking_clauses():
    rejected("SELECT * FROM pedidos FOR UPDATE")
