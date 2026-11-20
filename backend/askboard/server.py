import logging
from contextlib import asynccontextmanager
from typing import Protocol

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from askboard.config import Settings, load_settings
from askboard.db.database import Database

logger = logging.getLogger(__name__)


class DatabaseLike(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool: ...
    async def migrate(self) -> list[str]: ...


def create_app(
    settings: Settings | None = None,
    database: DatabaseLike | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    db: DatabaseLike = database or Database(
        settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await db.open()
        try:
            if settings.auto_migrate:
                applied = await db.migrate()
                if applied:
                    logger.info("Applied migrations: %s", ", ".join(applied))
            yield
        finally:
            await db.close()

    app = FastAPI(title="Askboard", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz():
        if not await db.ping():
            raise HTTPException(status_code=503, detail="Database not reachable")
        return {"status": "ok"}

    return app
