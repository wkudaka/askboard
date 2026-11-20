"""Deterministic chart choice from the *shape* of a query result.

The LLM may later pick another chart, but only one listed in `alternatives`, so a
nonsensical visualization (a pie of averages, a line over categories) cannot happen.
"""

import re
from dataclasses import dataclass, field
from typing import Any

from askboard.ingestion.types import is_money_name
from askboard.models import Encoding, PanelColumn

MAX_PIE_SLICES = 6
MAX_BAR_CATEGORIES = 30
MAX_SERIES = 8
SHORT_SERIES = 3

_ID_LIKE = re.compile(r"(^|_)(id|code|codigo|cod)$|^id_")
# Averages, rates and shares are not parts of a whole: never a pie.
_NOT_ADDITIVE = re.compile(
    r"(^|_)(avg|average|mean|media|medio|median|mediana|ticket|rate|taxa|ratio|pct|percent|percentual|share|min|max)(_|$)"
)


@dataclass
class ChartPlan:
    type: str
    encoding: Encoding = field(default_factory=Encoding)
    alternatives: list[str] = field(default_factory=list)
    formats: dict[str, str] = field(default_factory=dict)


def _role(column: PanelColumn) -> str:
    if column.type in ("date", "timestamp"):
        return "temporal"
    if column.type == "number" and not _ID_LIKE.search(column.name.lower()):
        return "numeric"
    return "categorical"


def _values(rows: list[list[Any]], index: int) -> list[Any]:
    return [r[index] for r in rows if r[index] is not None]


def _number_format(name: str, values: list[Any]) -> str:
    if is_money_name(name):
        return "currency"
    if all(isinstance(v, int) or (isinstance(v, float) and v.is_integer()) for v in values):
        return "integer"
    return "number"


def plan_chart(columns: list[PanelColumn], rows: list[list[Any]]) -> ChartPlan:
    index = {c.name: i for i, c in enumerate(columns)}
    temporal = [c.name for c in columns if _role(c) == "temporal"]
    categorical = [c.name for c in columns if _role(c) == "categorical"]
    numeric = [c.name for c in columns if _role(c) == "numeric"]
    formats = {n: _number_format(n, _values(rows, index[n])) for n in numeric}

    def distinct(name: str) -> int:
        return len({str(v) for v in _values(rows, index[name])})

    def make(kind: str, alternatives: list[str], x=None, y=None, series=None) -> ChartPlan:
        return ChartPlan(kind, Encoding(x=x, y=y or [], series=series), alternatives, formats)

    n_rows = len(rows)
    if n_rows == 0:
        return make("table", [])

    if n_rows == 1:
        if numeric and not temporal and not categorical:
            return make("kpi", ["table"], y=numeric)
        return make("table", [])

    # time series
    if len(temporal) == 1 and numeric and not categorical:
        x = temporal[0]
        if distinct(x) <= SHORT_SERIES:
            return make("bar", ["line", "table"], x=x, y=numeric)
        return make("line", ["bar", "table"], x=x, y=numeric)
    if len(temporal) == 1 and len(categorical) == 1 and len(numeric) == 1:
        if distinct(categorical[0]) <= MAX_SERIES:
            return make("line", ["stacked_bar", "table"], x=temporal[0], y=numeric, series=categorical[0])
        return make("table", [])

    if temporal:
        return make("table", [])

    # categories
    if len(categorical) == 1 and numeric:
        x = categorical[0]
        if distinct(x) > MAX_BAR_CATEGORIES:
            return make("table", ["bar"], x=x, y=numeric)
        if len(numeric) == 1:
            metric = numeric[0]
            values = _values(rows, index[metric])
            pie_ok = (
                2 <= distinct(x) <= MAX_PIE_SLICES
                and all(v >= 0 for v in values)
                and not _NOT_ADDITIVE.search(metric.lower())
            )
            if pie_ok:
                return make("pie", ["bar", "table"], x=x, y=numeric)
        return make("bar", ["table"], x=x, y=numeric)

    if len(categorical) == 2 and len(numeric) == 1:
        x, series = categorical
        if distinct(series) <= MAX_SERIES and distinct(x) <= MAX_BAR_CATEGORIES:
            return make("stacked_bar", ["table"], x=x, y=numeric, series=series)
        return make("table", [])

    if not categorical and len(numeric) == 2:
        return make("scatter", ["table"], x=numeric[0], y=[numeric[1]])

    return make("table", [])
