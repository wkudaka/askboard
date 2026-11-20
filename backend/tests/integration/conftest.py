import os
from pathlib import Path

import psycopg
import pytest

from askboard.db.database import Database
from askboard.services.datasets import DatasetService
from askboard.services.workspaces import WorkspaceService

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://askboard:askboard@localhost:5433/askboard_test",
)
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def _reachable(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=2):
            return True
    except psycopg.Error:
        return False


@pytest.fixture(scope="session")
def database_url() -> str:
    if not _reachable(TEST_DATABASE_URL):
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL} (run: docker compose up -d db)")
    return TEST_DATABASE_URL


@pytest.fixture
def clean_database(database_url: str) -> str:
    """Drops every Askboard-owned schema so each test starts from scratch."""
    with psycopg.connect(database_url, autocommit=True) as conn:
        schemas = conn.execute(
            "SELECT nspname FROM pg_namespace WHERE nspname = 'askboard' OR nspname LIKE 'ws\\_%'"
        ).fetchall()
        for (schema,) in schemas:
            conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
    return database_url


@pytest.fixture
async def database(clean_database: str):
    db = Database(clean_database, min_size=1, max_size=2)
    await db.open()
    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
async def migrated_database(database: Database) -> Database:
    await database.migrate()
    return database


@pytest.fixture
def workspaces(migrated_database: Database) -> WorkspaceService:
    return WorkspaceService(migrated_database)


@pytest.fixture
def datasets(migrated_database: Database) -> DatasetService:
    return DatasetService(migrated_database)


@pytest.fixture
def pedidos_csv() -> bytes:
    return (FIXTURES / "pedidos.csv").read_bytes()


@pytest.fixture
def customers_csv() -> bytes:
    return (FIXTURES / "customers.csv").read_bytes()
