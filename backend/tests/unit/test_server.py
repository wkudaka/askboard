from fastapi.testclient import TestClient

from askboard.config import load_settings
from askboard.server import create_app


class FakeDatabase:
    def __init__(self, healthy: bool = True):
        self.healthy = healthy
        self.opened = False
        self.closed = False
        self.migrated = False

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def ping(self) -> bool:
        return self.healthy

    async def migrate(self) -> list[str]:
        self.migrated = True
        return []


def make_client(db: FakeDatabase, **env: str) -> TestClient:
    settings = load_settings({"AUTO_MIGRATE": "false", **env})
    return TestClient(create_app(settings=settings, database=db))


def test_healthz_returns_ok_even_when_db_is_down():
    with make_client(FakeDatabase(healthy=False)) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_ok_when_db_is_reachable():
    with make_client(FakeDatabase(healthy=True)) as client:
        response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readyz_returns_503_when_db_is_unreachable():
    with make_client(FakeDatabase(healthy=False)) as client:
        response = client.get("/readyz")

    assert response.status_code == 503


def test_lifespan_opens_and_closes_database():
    db = FakeDatabase()
    with make_client(db):
        assert db.opened is True
        assert db.closed is False
    assert db.closed is True


def test_lifespan_runs_migrations_when_auto_migrate_enabled():
    db = FakeDatabase()
    with make_client(db, AUTO_MIGRATE="true"):
        pass
    assert db.migrated is True


def test_lifespan_skips_migrations_when_auto_migrate_disabled():
    db = FakeDatabase()
    with make_client(db, AUTO_MIGRATE="false"):
        pass
    assert db.migrated is False


def test_cors_allows_configured_origin():
    with make_client(FakeDatabase(), CORS_ORIGINS="http://localhost:5173") as client:
        response = client.get("/healthz", headers={"Origin": "http://localhost:5173"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_rejects_unknown_origin():
    with make_client(FakeDatabase(), CORS_ORIGINS="http://localhost:5173") as client:
        response = client.get("/healthz", headers={"Origin": "http://evil.example"})

    assert "access-control-allow-origin" not in response.headers
