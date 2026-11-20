import uuid
from datetime import datetime, timezone

from askboard.ask.context import allowed_tables, build_schema_context
from askboard.ingestion.types import PgType
from askboard.models import ColumnInfo, Dataset, SourceFormat


def column(position, name, pg_type, semantic, **kwargs) -> ColumnInfo:
    return ColumnInfo(
        position=position, name=name, original_name=kwargs.pop("original_name", name),
        pg_type=pg_type, semantic_type=semantic, **kwargs,
    )


def dataset(table_name, columns, status="loaded", row_count=5) -> Dataset:
    return Dataset(
        id=uuid.uuid4(), workspace_id=uuid.uuid4(), table_name=table_name,
        original_filename=f"{table_name}.csv", status=status, row_count=row_count,
        rejected_rows=0, source_format=SourceFormat(encoding="utf-8", delimiter=","),
        columns=columns, load_errors=[], created_at=datetime.now(timezone.utc),
    )


PEDIDOS = dataset("pedidos", [
    column(1, "id", PgType.BIGINT, "id", is_unique=True, min_value="1", max_value="6", distinct_count=5),
    column(2, "cliente", PgType.TEXT, "categorical", distinct_count=3, sample_values=["Ana", "Bruno", "Carla"]),
    column(3, "valor_total", PgType.NUMERIC, "currency", original_name="Valor Total",
           null_ratio=0.2, min_value="7.25", max_value="1234.56"),
    column(4, "data_do_pedido", PgType.DATE, "temporal", min_value="2024-01-15", max_value="2024-03-10"),
])


def test_describes_tables_and_columns():
    text = build_schema_context([PEDIDOS])

    assert 'Table pedidos (5 rows, from "pedidos.csv")' in text
    assert "- id: bigint, id, unique, range 1 .. 6" in text
    assert '- cliente: text, categorical, 3 distinct, e.g. "Ana", "Bruno", "Carla"' in text
    assert '- valor_total: numeric, currency, 20% null, range 7.25 .. 1234.56 (originally "Valor Total")' in text
    assert "- data_do_pedido: date, temporal, range 2024-01-15 .. 2024-03-10" in text


def test_skips_datasets_that_are_not_loaded():
    pending = dataset("rascunho", [column(1, "x", PgType.TEXT, "text")], status="pending")

    text = build_schema_context([PEDIDOS, pending])

    assert "rascunho" not in text
    assert allowed_tables([PEDIDOS, pending]) == {"pedidos"}


def test_truncates_long_sample_values():
    ds = dataset("notas", [column(1, "texto", PgType.TEXT, "text", sample_values=["x" * 200])])

    text = build_schema_context([ds])

    assert "x" * 40 + "…" in text
    assert "x" * 41 not in text


def test_escapes_quotes_in_sample_values():
    ds = dataset("t", [column(1, "c", PgType.TEXT, "categorical", sample_values=['say "hi"'])])

    assert r'"say \"hi\""' in build_schema_context([ds])


def test_empty_workspace_has_empty_context():
    assert build_schema_context([]) == ""
    assert allowed_tables([]) == set()
