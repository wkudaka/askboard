import uuid
from datetime import datetime, timezone

from askboard.ingestion.relationships import Candidate, find_candidates
from askboard.ingestion.types import PgType
from askboard.models import ColumnInfo, Dataset, SourceFormat


def col(position, name, pg_type=PgType.BIGINT, unique=False, semantic="numeric") -> ColumnInfo:
    return ColumnInfo(
        position=position, name=name, original_name=name, pg_type=pg_type,
        semantic_type=semantic, is_unique=unique,
    )


def ds(table, columns, status="loaded") -> Dataset:
    return Dataset(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), table_name=table, original_filename=f"{table}.csv",
        status=status, row_count=5, rejected_rows=0, source_format=SourceFormat(encoding="utf-8", delimiter=","),
        columns=columns, load_errors=[], created_at=datetime.now(timezone.utc),
    )


CLIENTES = ds("clientes", [col(1, "id", unique=True, semantic="id"), col(2, "nome", PgType.TEXT, semantic="text")])


def pairs(candidates: list[Candidate]) -> set[tuple[str, str, str, str]]:
    return {(c.from_table, c.from_column, c.to_table, c.to_column) for c in candidates}


def test_singular_table_name_plus_id():
    pedidos = ds("pedidos", [col(1, "id", unique=True), col(2, "cliente_id")])

    assert pairs(find_candidates([CLIENTES, pedidos])) == {("pedidos", "cliente_id", "clientes", "id")}


def test_id_prefix_style():
    pedidos = ds("pedidos", [col(1, "id_cliente")])

    assert pairs(find_candidates([CLIENTES, pedidos])) == {("pedidos", "id_cliente", "clientes", "id")}


def test_english_plural_and_same_column_name():
    customers = ds("customers", [col(1, "customer_id", PgType.TEXT, unique=True, semantic="id")])
    orders = ds("orders", [col(1, "order_id", unique=True), col(2, "customer_id", PgType.TEXT, semantic="id")])

    assert pairs(find_candidates([customers, orders])) == {("orders", "customer_id", "customers", "customer_id")}


def test_column_named_after_the_table():
    pedidos = ds("pedidos", [col(1, "cliente")])

    assert pairs(find_candidates([CLIENTES, pedidos])) == {("pedidos", "cliente", "clientes", "id")}


def test_target_must_be_unique():
    clientes = ds("clientes", [col(1, "id", unique=False)])
    pedidos = ds("pedidos", [col(1, "cliente_id")])

    assert find_candidates([clientes, pedidos]) == []


def test_types_must_be_compatible():
    pedidos = ds("pedidos", [col(1, "cliente_id", PgType.DATE, semantic="temporal")])

    assert find_candidates([CLIENTES, pedidos]) == []


def test_text_and_integer_keys_are_compatible():
    pedidos = ds("pedidos", [col(1, "cliente_id", PgType.TEXT, semantic="id")])

    assert pairs(find_candidates([CLIENTES, pedidos])) == {("pedidos", "cliente_id", "clientes", "id")}


def test_unrelated_names_are_ignored_even_with_matching_types():
    pedidos = ds("pedidos", [col(1, "quantidade"), col(2, "id", unique=True)])

    assert find_candidates([CLIENTES, pedidos]) == []


def test_no_relationships_within_one_table():
    clientes = ds("clientes", [col(1, "id", unique=True), col(2, "cliente_id")])

    assert find_candidates([clientes]) == []


def test_pending_datasets_are_ignored():
    pedidos = ds("pedidos", [col(1, "cliente_id")], status="pending")

    assert find_candidates([CLIENTES, pedidos]) == []


def test_one_to_one_same_name_yields_a_single_direction():
    a = ds("perfis", [col(1, "usuario_id", unique=True)])
    b = ds("usuarios", [col(1, "usuario_id", unique=True)])

    found = find_candidates([a, b])

    assert len(found) == 1
    assert (found[0].from_table, found[0].to_table) == ("perfis", "usuarios")  # FK side = not the table it names


def test_prefixed_table_names_match_on_their_last_word():
    clientes = ds("loja_clientes", [col(1, "id", unique=True, semantic="id")])
    pedidos = ds("loja_pedidos", [col(1, "id", unique=True), col(2, "cliente_id")])

    assert pairs(find_candidates([clientes, pedidos])) == {("loja_pedidos", "cliente_id", "loja_clientes", "id")}


def test_prefix_words_alone_do_not_create_candidates():
    clientes = ds("loja_clientes", [col(1, "id", unique=True, semantic="id")])
    pedidos = ds("pedidos", [col(1, "loja_id")])

    assert find_candidates([clientes, pedidos]) == []
