import pytest

from askboard.ingestion.naming import (
    MAX_IDENTIFIER_LENGTH,
    dedupe,
    table_name_from_filename,
    to_identifier,
    unique_identifiers,
)


@pytest.mark.parametrize("raw, expected", [
    ("Customer Name", "customer_name"),
    ("customerName", "customer_name"),
    ("OrderID", "order_id"),
    ("  Valor Total (R$) ", "valor_total_r"),
    ("Preço Unitário", "preco_unitario"),
    ("São Paulo", "sao_paulo"),
    ("e-mail", "e_mail"),
    ("a__b---c", "a_b_c"),
    ("2024 sales", "c_2024_sales"),
    ("ÇÃO", "cao"),
    ("already_snake", "already_snake"),
])
def test_to_identifier_normalizes_to_snake_case_ascii(raw, expected):
    assert to_identifier(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "???", "日本"])
def test_to_identifier_uses_fallback_when_nothing_is_left(raw):
    assert to_identifier(raw, fallback="column") == "column"


@pytest.mark.parametrize("reserved", ["select", "from", "order", "user", "table", "group"])
def test_to_identifier_escapes_reserved_words(reserved):
    assert to_identifier(reserved) == f"{reserved}_"


def test_to_identifier_truncates_to_postgres_limit():
    result = to_identifier("x" * 100)
    assert len(result) == MAX_IDENTIFIER_LENGTH == 63


def test_dedupe_appends_numeric_suffix():
    taken = {"name", "name_2"}
    assert dedupe("name", taken) == "name_3"
    assert dedupe("other", taken) == "other"


def test_dedupe_keeps_suffix_within_length_limit():
    base = "x" * 63
    result = dedupe(base, {base})
    assert len(result) <= 63
    assert result.endswith("_2")


def test_unique_identifiers_dedupes_and_fills_blanks():
    assert unique_identifiers(["Name", "name", "", "NAME ", ""]) == [
        "name", "name_2", "column_3", "name_3", "column_5",
    ]


@pytest.mark.parametrize("filename, expected", [
    ("Vendas 2024.csv", "vendas_2024"),
    ("orders.CSV", "orders"),
    ("C:\\Users\\me\\data\\clientes.csv", "clientes"),
    ("/tmp/folder/products.tsv", "products"),
    ("123.csv", "t_123"),
    (".csv", "dataset"),
    ("order.csv", "order_"),
])
def test_table_name_from_filename(filename, expected):
    assert table_name_from_filename(filename) == expected
