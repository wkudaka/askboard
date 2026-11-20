"""Finds likely join keys between the tables of a workspace.

Candidates come from *names* (cliente_id -> clientes.id, id_cliente, customer_id on both
sides, ...) against a *unique* target column of a compatible type. The values are then
checked in Postgres (see services/relationships.py): a candidate is only suggested when
most of its values exist on the target side. Requiring both keeps coincidences such as
`quantidade` vs `id` (same small integers) out.
"""

import re
import uuid
from dataclasses import dataclass

from askboard.ingestion.types import PgType
from askboard.models import Dataset

_KEY_TYPES = frozenset({PgType.BIGINT, PgType.TEXT, PgType.NUMERIC})
_ID_LIKE = re.compile(r"(^|_)(id|code|codigo|cod|key|uuid)$|^(id|cod|codigo)_")
_GENERIC_KEYS = frozenset({"id", "code", "codigo", "cod", "key", "uuid"})


@dataclass(frozen=True)
class Candidate:
    from_dataset_id: uuid.UUID
    from_table: str
    from_column: str
    to_dataset_id: uuid.UUID
    to_table: str
    to_column: str


def _singular(table: str) -> str:
    return table[:-1] if table.endswith("s") and len(table) > 3 else table


def _expected_names(table: str, key: str) -> set[str]:
    """Column names that would reference `table.key` from another table."""
    names: set[str] = set()
    last_word = table.rsplit("_", 1)[-1]  # loja_clientes -> clientes (export/file prefixes)
    for t in {table, _singular(table), last_word, _singular(last_word)}:
        names |= {f"{t}_{key}", f"{key}_{t}"}
        if key in _GENERIC_KEYS:
            names.add(t)  # pedidos.cliente -> clientes.id
    if key not in _GENERIC_KEYS and _ID_LIKE.search(key):
        names.add(key)  # customer_id on both sides
    return names


def _refers_to(column: str, table: str) -> bool:
    return any(column.startswith(t) or column.endswith(t) for t in {table, _singular(table)})


def find_candidates(datasets: list[Dataset]) -> list[Candidate]:
    loaded = [d for d in datasets if d.status == "loaded"]
    found: dict[tuple[str, str, str, str], Candidate] = {}

    for target in loaded:
        for key in target.columns:
            if not key.is_unique or key.pg_type not in _KEY_TYPES:
                continue
            expected = _expected_names(target.table_name, key.name)
            for source in loaded:
                if source.id == target.id:
                    continue
                for column in source.columns:
                    if column.name in expected and column.pg_type in _KEY_TYPES:
                        found[(source.table_name, column.name, target.table_name, key.name)] = Candidate(
                            source.id, source.table_name, column.name, target.id, target.table_name, key.name
                        )

    # 1:1 keys with the same name match in both directions: keep the one pointing at the
    # table the column is named after (perfis.usuario_id -> usuarios.usuario_id).
    result = []
    for (ft, fc, tt, tc), candidate in found.items():
        reverse = (tt, tc, ft, fc)
        if reverse in found and not _refers_to(fc, tt) and _refers_to(tc, ft):
            continue
        if reverse in found and _refers_to(fc, tt) == _refers_to(tc, ft) and (ft, fc) > (tt, tc):
            continue
        result.append(candidate)
    return sorted(result, key=lambda c: (c.from_table, c.from_column, c.to_table))
