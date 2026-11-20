from pathlib import Path

import pytest

from askboard.db.migrations import MIGRATIONS_DIR, Migration, discover_migrations


def write(dir_: Path, name: str, sql: str = "SELECT 1;") -> None:
    (dir_ / name).write_text(sql, encoding="utf-8")


def test_discovers_sql_files_sorted_by_version(tmp_path):
    write(tmp_path, "010_later.sql")
    write(tmp_path, "002_second.sql")
    write(tmp_path, "001_first.sql")

    migrations = discover_migrations(tmp_path)

    assert [m.version for m in migrations] == ["001", "002", "010"]
    assert [m.name for m in migrations] == ["first", "second", "later"]


def test_ignores_non_sql_and_unprefixed_files(tmp_path):
    write(tmp_path, "001_first.sql")
    write(tmp_path, "README.md")
    write(tmp_path, "notes.sql")

    migrations = discover_migrations(tmp_path)

    assert [m.version for m in migrations] == ["001"]


def test_duplicate_version_raises(tmp_path):
    write(tmp_path, "001_a.sql")
    write(tmp_path, "001_b.sql")

    with pytest.raises(ValueError, match="001"):
        discover_migrations(tmp_path)


def test_migration_reads_sql(tmp_path):
    write(tmp_path, "001_first.sql", "CREATE TABLE t (id int);")

    [migration] = discover_migrations(tmp_path)

    assert isinstance(migration, Migration)
    assert migration.sql() == "CREATE TABLE t (id int);"


def test_shipped_migrations_exist_and_are_ordered():
    migrations = discover_migrations(MIGRATIONS_DIR)
    versions = [m.version for m in migrations]

    assert versions[:2] == ["001", "002"]
    assert versions == sorted(versions)


def test_shipped_metadata_migration_defines_core_tables():
    sql = next(m for m in discover_migrations(MIGRATIONS_DIR) if m.version == "001").sql().lower()

    for table in ("workspaces", "datasets", "columns", "relationships", "questions"):
        assert f"askboard.{table}" in sql, f"missing table askboard.{table}"


def test_shipped_roles_migration_defines_reader_role():
    sql = next(m for m in discover_migrations(MIGRATIONS_DIR) if m.version == "002").sql().lower()

    assert "askboard_reader" in sql
    assert "revoke" in sql
