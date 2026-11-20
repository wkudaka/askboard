import os
from collections.abc import Mapping
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_pool_min_size: int
    db_pool_max_size: int
    auto_migrate: bool
    max_upload_mb: int
    statement_timeout_ms: int
    cors_origins: list[str]


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{key} must be an integer, got {raw!r}") from None


def _get_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{key} must be a boolean (true/false), got {raw!r}")


def _get_list(env: Mapping[str, str], key: str, default: list[str]) -> list[str]:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Builds Settings from an env mapping (defaults to os.environ)."""
    env = os.environ if env is None else env

    min_size = _get_int(env, "DB_POOL_MIN_SIZE", 1)
    max_size = _get_int(env, "DB_POOL_MAX_SIZE", 10)
    if min_size > max_size:
        raise ValueError(
            f"DB_POOL_MIN_SIZE ({min_size}) must be <= DB_POOL_MAX_SIZE ({max_size})"
        )

    return Settings(
        database_url=env.get(
            "DATABASE_URL", "postgresql://askboard:askboard@localhost:5433/askboard"
        ),
        db_pool_min_size=min_size,
        db_pool_max_size=max_size,
        auto_migrate=_get_bool(env, "AUTO_MIGRATE", True),
        max_upload_mb=_get_int(env, "MAX_UPLOAD_MB", 50),
        statement_timeout_ms=_get_int(env, "STATEMENT_TIMEOUT_MS", 10_000),
        cors_origins=_get_list(env, "CORS_ORIGINS", ["http://localhost:5173"]),
    )
