"""Static validation of LLM-generated SQL before it reaches Postgres.

This is the first of two layers: the query is also executed as a role that can only
SELECT, inside a READ ONLY transaction with a statement timeout (see query_runner.py).
The guard is what keeps a query inside *its* workspace: only the workspace schema and its
loaded tables may be referenced.
"""

import re

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, TokenError

_FENCE = re.compile(r"^\s*```(?:sql)?\s*(.*?)\s*```\s*$", re.DOTALL | re.IGNORECASE)

_FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Create, exp.Drop, exp.Alter,
    exp.TruncateTable, exp.Command, exp.Grant, exp.Copy, exp.Set, exp.Into, exp.Lock,
)

_FORBIDDEN_FUNCTIONS = frozenset({
    "set_config", "current_setting", "version", "current_version", "inet_server_addr",
    "inet_server_port",
})
_FORBIDDEN_FUNCTION_PREFIXES = (
    "pg_", "lo_", "dblink", "query_to_", "table_to_", "schema_to_", "database_to_", "cursor_to_",
    "txid_",
)


class UnsafeQueryError(ValueError):
    """The SQL is not a single read-only query over the workspace tables."""


def _clean(sql: str) -> str:
    if match := _FENCE.match(sql):
        sql = match.group(1)
    return sql.strip().rstrip(";").strip()


def _function_name(func: exp.Func) -> str:
    return (func.name if isinstance(func, exp.Anonymous) else func.sql_name()).lower()


def check_sql(sql: str, *, schema: str, allowed_tables: set[str]) -> str:
    """Returns the cleaned SQL if it is safe to run, else raises UnsafeQueryError."""
    cleaned = _clean(sql)
    if not cleaned:
        raise UnsafeQueryError("The query is empty")

    try:
        statements = [s for s in sqlglot.parse(cleaned, dialect="postgres") if s is not None]
    except (ParseError, TokenError) as exc:
        raise UnsafeQueryError(f"The query could not be parsed: {exc}") from None
    if len(statements) != 1:
        raise UnsafeQueryError("Only a single SELECT statement is allowed")

    [statement] = statements
    if not isinstance(statement, exp.Query):
        raise UnsafeQueryError("Only SELECT queries are allowed")

    for node in statement.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise UnsafeQueryError(f"Forbidden SQL construct: {node.key.upper()}")
        if isinstance(node, exp.Func):
            name = _function_name(node)
            if name in _FORBIDDEN_FUNCTIONS or name.startswith(_FORBIDDEN_FUNCTION_PREFIXES):
                raise UnsafeQueryError(f"Function not allowed: {name}")

    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    allowed = {t.lower() for t in allowed_tables}
    for table in statement.find_all(exp.Table):
        name = table.name.lower()
        if table.catalog:
            raise UnsafeQueryError(f"Cross-database reference not allowed: {table.sql()}")
        if table.db:
            if table.db.lower() != schema.lower():
                raise UnsafeQueryError(f"Schema not allowed: {table.db}")
        elif name in cte_names:
            continue
        if name not in allowed:
            raise UnsafeQueryError(f"Unknown table: {table.name or table.sql()}")

    return cleaned
