import pytest

from askboard.models import PanelColumn
from askboard.viz.rules import ChartPlan, Encoding, plan_chart


def cols(*spec: str) -> list[PanelColumn]:
    """'name:type' pairs -> columns."""
    return [PanelColumn(name=s.split(":")[0], type=s.split(":")[1]) for s in spec]


def months(n: int) -> list[str]:
    return [f"2024-{m:02d}-01" for m in range(1, n + 1)]


def plan(columns, rows) -> ChartPlan:
    return plan_chart(columns, rows)


# --- KPI / table -------------------------------------------------------------------------

def test_no_rows_is_a_table_without_alternatives():
    p = plan(cols("total:number"), [])
    assert (p.type, p.alternatives) == ("table", [])


def test_single_number_is_a_kpi():
    p = plan(cols("total_pedidos:number"), [[5]])
    assert p.type == "kpi"
    assert p.encoding == Encoding(y=["total_pedidos"])
    assert p.alternatives == ["table"]


def test_single_row_of_numbers_is_a_kpi_row():
    p = plan(cols("pedidos:number", "receita:number", "ticket_medio:number"), [[5, 1351.71, 270.3]])
    assert p.type == "kpi"
    assert p.encoding.y == ["pedidos", "receita", "ticket_medio"]


def test_single_category_row_is_a_table():
    assert plan(cols("cliente:text", "total:number"), [["Ana", 1341.71]]).type == "table"


def test_list_of_single_numbers_is_a_table():
    assert plan(cols("valor:number"), [[1], [2], [3]]).type == "table"


def test_wide_text_results_are_tables():
    p = plan(cols("a:text", "b:text", "c:text", "d:text"), [["1", "2", "3", "4"], ["5", "6", "7", "8"]])
    assert p.type == "table"


# --- time series ----------------------------------------------------------------------------

def test_time_series_is_a_line():
    rows = [[m, i * 10] for i, m in enumerate(months(12))]
    p = plan(cols("mes:date", "receita:number"), rows)
    assert p.type == "line"
    assert p.encoding == Encoding(x="mes", y=["receita"])
    assert p.alternatives == ["bar", "table"]


def test_short_time_series_is_a_bar():
    rows = [[m, 1] for m in months(3)]
    p = plan(cols("mes:timestamp", "pedidos:number"), rows)
    assert p.type == "bar"
    assert p.alternatives == ["line", "table"]


def test_time_series_split_by_category_is_a_multi_line():
    rows = [[m, c, 1] for m in months(6) for c in ("Ana", "Bruno", "Carla")]
    p = plan(cols("mes:date", "cliente:text", "receita:number"), rows)
    assert p.type == "line"
    assert p.encoding == Encoding(x="mes", y=["receita"], series="cliente")
    assert p.alternatives == ["stacked_bar", "table"]


def test_time_series_with_too_many_series_is_a_table():
    rows = [[m, f"c{i}", 1] for m in months(2) for i in range(20)]
    assert plan(cols("mes:date", "cliente:text", "receita:number"), rows).type == "table"


# --- categories ---------------------------------------------------------------------------------

def test_few_categories_of_a_total_is_a_pie():
    rows = [["credit_card", 50], ["pix", 30], ["boleto", 20]]
    p = plan(cols("pagamento:text", "receita:number"), rows)
    assert p.type == "pie"
    assert p.encoding == Encoding(x="pagamento", y=["receita"])
    assert p.alternatives == ["bar", "table"]


@pytest.mark.parametrize("metric", ["ticket_medio", "avg_amount", "taxa_conversao", "pct_share", "media"])
def test_averages_and_rates_are_never_pies(metric):
    rows = [["a", 1], ["b", 2], ["c", 3]]
    p = plan(cols("grupo:text", f"{metric}:number"), rows)
    assert p.type == "bar"
    assert "pie" not in p.alternatives


def test_negative_values_are_never_pies():
    p = plan(cols("loja:text", "lucro:number"), [["a", 10], ["b", -5]])
    assert p.type == "bar"
    assert "pie" not in p.alternatives


def test_many_categories_is_a_bar():
    rows = [[f"produto {i}", i] for i in range(10)]
    p = plan(cols("produto:text", "vendas:number"), rows)
    assert p.type == "bar"
    assert p.alternatives == ["table"]


def test_too_many_categories_is_a_table_with_bar_alternative():
    rows = [[f"produto {i}", i] for i in range(40)]
    p = plan(cols("produto:text", "vendas:number"), rows)
    assert (p.type, p.alternatives) == ("table", ["bar"])


def test_category_with_several_metrics_is_a_grouped_bar():
    rows = [["Ana", 3, 1341.71], ["Bruno", 1, 10.0]]
    p = plan(cols("cliente:text", "pedidos:number", "receita:number"), rows)
    assert p.type == "bar"
    assert p.encoding == Encoding(x="cliente", y=["pedidos", "receita"])


def test_two_categories_and_a_metric_is_a_stacked_bar():
    rows = [["Recife", "pix", 10], ["Recife", "boleto", 5], ["Natal", "pix", 7]]
    p = plan(cols("cidade:text", "pagamento:text", "receita:number"), rows)
    assert p.type == "stacked_bar"
    assert p.encoding == Encoding(x="cidade", y=["receita"], series="pagamento")
    assert p.alternatives == ["table"]


def test_id_like_numbers_are_categories():
    rows = [[1, 10.0], [2, 20.0], [3, 5.0], [4, 1.0], [5, 2.0], [6, 3.0], [7, 4.0]]
    p = plan(cols("customer_id:number", "total:number"), rows)
    assert p.type == "bar"
    assert p.encoding.x == "customer_id"


def test_booleans_are_categories():
    p = plan(cols("pago:boolean", "pedidos:number"), [[True, 3], [False, 2]])
    assert p.type == "pie"


def test_two_metrics_without_category_is_a_scatter():
    rows = [[i, i * 2.5] for i in range(20)]
    p = plan(cols("quantidade:number", "valor:number"), rows)
    assert p.type == "scatter"
    assert p.encoding == Encoding(x="quantidade", y=["valor"])
    assert p.alternatives == ["table"]


# --- formats -------------------------------------------------------------------------------------

def test_formats_are_inferred_from_names_and_values():
    rows = [["Ana", 3, 1341.71, 0.5], ["Bruno", 1, 10.0, 1.25]]
    p = plan(cols("cliente:text", "pedidos:number", "valor_total:number", "peso:number"), rows)
    assert p.formats == {"pedidos": "integer", "valor_total": "currency", "peso": "number"}
