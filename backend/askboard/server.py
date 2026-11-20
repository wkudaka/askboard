import logging
from contextlib import asynccontextmanager
from collections.abc import Callable
from typing import Protocol

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from askboard.api.routes import register_error_handlers, router
from askboard.ask.llm import StructuredLLM, make_llm
from askboard.ask.query_runner import QueryRunner
from askboard.config import Settings, load_settings
from askboard.db.database import Database
from askboard.services.ask import AskService
from askboard.services.datasets import DatasetService
from askboard.services.relationships import RelationshipService
from askboard.services.workspaces import WorkspaceService

logger = logging.getLogger(__name__)


class DatabaseLike(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def ping(self) -> bool: ...
    async def migrate(self) -> list[str]: ...


def create_app(
    settings: Settings | None = None,
    database: DatabaseLike | None = None,
    llm_factory: Callable[[], StructuredLLM] | None = None,
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
    app.state.workspaces = WorkspaceService(db)  # type: ignore[arg-type]
    app.state.datasets = DatasetService(db)  # type: ignore[arg-type]
    app.state.relationships = RelationshipService(db)  # type: ignore[arg-type]
    app.state.ask = AskService(
        db,  # type: ignore[arg-type]
        app.state.datasets,
        runner=QueryRunner(
            db,  # type: ignore[arg-type]
            statement_timeout_ms=settings.statement_timeout_ms,
            max_rows=settings.max_query_rows,
        ),
        llm_factory=llm_factory or (lambda: make_llm(settings)),
        max_correction_attempts=settings.max_correction_attempts,
    )

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

    app.include_router(router)
    register_error_handlers(app)
    return app
