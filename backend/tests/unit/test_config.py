import pytest

from askboard.config import Settings, load_settings


def test_defaults_when_env_is_empty():
    settings = load_settings({})

    assert isinstance(settings, Settings)
    assert settings.database_url == "postgresql://askboard:askboard@localhost:5433/askboard"
    assert settings.db_pool_min_size == 1
    assert settings.db_pool_max_size == 10
    assert settings.auto_migrate is True
    assert settings.max_upload_mb == 50
    assert settings.statement_timeout_ms == 10_000
    assert settings.cors_origins == ["http://localhost:5173"]


def test_env_overrides_defaults():
    settings = load_settings({
        "DATABASE_URL": "postgresql://u:p@db:5432/x",
        "DB_POOL_MIN_SIZE": "2",
        "DB_POOL_MAX_SIZE": "5",
        "AUTO_MIGRATE": "false",
        "MAX_UPLOAD_MB": "10",
        "STATEMENT_TIMEOUT_MS": "3000",
        "CORS_ORIGINS": "http://a.com, http://b.com",
    })

    assert settings.database_url == "postgresql://u:p@db:5432/x"
    assert settings.db_pool_min_size == 2
    assert settings.db_pool_max_size == 5
    assert settings.auto_migrate is False
    assert settings.max_upload_mb == 10
    assert settings.statement_timeout_ms == 3000
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


@pytest.mark.parametrize("raw, expected", [
    ("true", True), ("1", True), ("YES", True), ("on", True),
    ("false", False), ("0", False), ("no", False), ("off", False),
])
def test_boolean_parsing(raw, expected):
    assert load_settings({"AUTO_MIGRATE": raw}).auto_migrate is expected


def test_invalid_boolean_raises():
    with pytest.raises(ValueError, match="AUTO_MIGRATE"):
        load_settings({"AUTO_MIGRATE": "maybe"})


def test_invalid_integer_raises_with_variable_name():
    with pytest.raises(ValueError, match="MAX_UPLOAD_MB"):
        load_settings({"MAX_UPLOAD_MB": "fifty"})


def test_pool_min_greater_than_max_raises():
    with pytest.raises(ValueError, match="DB_POOL_MIN_SIZE"):
        load_settings({"DB_POOL_MIN_SIZE": "20", "DB_POOL_MAX_SIZE": "5"})


def test_settings_are_immutable():
    settings = load_settings({})
    with pytest.raises(Exception):
        settings.max_upload_mb = 1  # type: ignore[misc]


def test_llm_defaults():
    settings = load_settings({})

    assert settings.llm_provider == "openrouter"
    assert settings.llm_model == "openai/gpt-4o-mini"
    assert settings.openrouter_api_key == ""
    assert settings.llm_timeout_seconds == 60
    assert settings.max_query_rows == 1000
    assert settings.max_correction_attempts == 2


def test_llm_overrides():
    settings = load_settings({
        "LLM_PROVIDER": "Bedrock",
        "LLM_MODEL": "anthropic/claude",
        "OPENROUTER_API_KEY": " sk-test ",
        "LLM_TIMEOUT_SECONDS": "5",
        "MAX_QUERY_ROWS": "50",
        "MAX_CORRECTION_ATTEMPTS": "0",
    })

    assert settings.llm_provider == "bedrock"
    assert settings.llm_model == "anthropic/claude"
    assert settings.openrouter_api_key == "sk-test"
    assert settings.llm_timeout_seconds == 5
    assert settings.max_query_rows == 50
    assert settings.max_correction_attempts == 0


def test_unknown_llm_provider_raises():
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        load_settings({"LLM_PROVIDER": "skynet"})


def test_secret_is_not_in_repr():
    assert "sk-secret" not in repr(load_settings({"OPENROUTER_API_KEY": "sk-secret"}))
