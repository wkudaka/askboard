import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from psycopg_pool import AsyncConnectionPool

from askboard.db.migrations import MIGRATIONS_DIR, discover_migrations

logger = logging.getLogger(__name__)

# Arbitrary constant so concurrent app instances never run migrations at the same time.
_MIGRATION_LOCK_ID = 7_314_250_001


class Database:
    """Thin wrapper around a psycopg async connection pool."""

    def __init__(
        self,
        url: str,
        *,
        min_size: int = 1,
        max_size: int = 10,
        connect_timeout: float = 5,
    ):
        self._url = url
        self._connect_timeout = connect_timeout
        self._pool = AsyncConnectionPool(
            conninfo=url,
            min_size=min_size,
            max_size=max_size,
            # autocommit: explicit `conn.transaction()` blocks are real transactions,
            # not savepoints inside an implicit one.
            kwargs={"connect_timeout": max(1, int(connect_timeout)), "autocommit": True},
            timeout=connect_timeout,
            open=False,
        )

    async def open(self, *, wait: bool = True) -> None:
        await self._pool.open(wait=wait, timeout=self._connect_timeout)

    async def close(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[psycopg.AsyncConnection]:
        async with self._pool.connection() as conn:
            yield conn

    async def ping(self) -> bool:
        try:
            async with self.connection() as conn:
                await conn.execute("SELECT 1")
            return True
        except Exception:
            logger.warning("Database ping failed", exc_info=True)
            return False

    async def migrate(self) -> list[str]:
        """Applies pending migrations in order; returns the versions applied now."""
        applied_now: list[str] = []
        async with self.connection() as conn:
            await conn.execute("SELECT pg_advisory_lock(%s)", (_MIGRATION_LOCK_ID,))
            try:
                async with conn.transaction():
                    await conn.execute("CREATE SCHEMA IF NOT EXISTS askboard")
                    await conn.execute(
                        "CREATE TABLE IF NOT EXISTS askboard.schema_migrations ("
                        " version text PRIMARY KEY,"
                        " name text NOT NULL,"
                        " applied_at timestamptz NOT NULL DEFAULT now())"
                    )
                cursor = await conn.execute("SELECT version FROM askboard.schema_migrations")
                done = {row[0] for row in await cursor.fetchall()}

                for migration in discover_migrations(MIGRATIONS_DIR):
                    if migration.version in done:
                        continue
                    logger.info("Applying migration %s_%s", migration.version, migration.name)
                    async with conn.transaction():
                        await conn.execute(migration.sql())
                        await conn.execute(
                            "INSERT INTO askboard.schema_migrations (version, name) VALUES (%s, %s)",
                            (migration.version, migration.name),
                        )
                    applied_now.append(migration.version)
            finally:
                await conn.execute("SELECT pg_advisory_unlock(%s)", (_MIGRATION_LOCK_ID,))
        return applied_now
