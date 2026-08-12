"""Configuration defaults must match the checked-in local stack."""

from backend.config import Settings
import pytest
from pydantic import ValidationError


def test_database_default_matches_docker_compose_port() -> None:
    default_url = Settings.model_fields["database_url"].default

    assert default_url.endswith("localhost:5432/foodai")


def test_runtime_defaults_are_safe_and_documented() -> None:
    assert Settings.model_fields["debug"].default is False
    assert Settings.model_fields["vision_model"].default == "qwen3.5-plus"


def test_qdrant_default_matches_local_compose() -> None:
    assert Settings.model_fields["qdrant_url"].default == "http://localhost:6333"


def test_retired_local_image_flows_are_disabled_by_default() -> None:
    assert Settings.model_fields["cv_enabled"].default is False
    assert Settings.model_fields["image_embed_enabled"].default is False
    assert Settings.model_fields["local_fusion_enabled"].default is False


def test_food_gate_mode_is_disabled_by_default() -> None:
    assert Settings.model_fields["food_gate_mode"].default == "disabled"


def test_active_food_gate_mode_requires_a_service_url() -> None:
    with pytest.raises(ValueError):
        Settings(food_gate_mode="shadow", _env_file=None)


def test_production_rejects_demo_auth_and_process_local_rate_limit() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production", _env_file=None)


def test_production_accepts_explicit_security_configuration() -> None:
    settings = Settings(
        environment="production",
        auth_secret_key="a-unique-production-secret-with-32-characters",
        rate_limit_backend="redis",
        vision_api_key="vision-key",
        object_storage_backend="s3",
        database_url="postgresql+asyncpg://foodai_prod:secret@db:5432/foodai",
        metrics_token="metrics-secret-with-at-least-32-characters",
        _env_file=None,
    )

    assert settings.environment == "production"


def test_railway_postgres_url_is_normalized_to_asyncpg() -> None:
    settings = Settings(
        database_url="postgresql://foodai_prod:secret@db.railway.internal:5432/foodai",
        _env_file=None,
    )

    assert settings.database_url == (
        "postgresql+asyncpg://foodai_prod:secret@db.railway.internal:5432/foodai"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rate_limit_backend", "typo"),
        ("object_storage_backend", "local-disk"),
        ("vision_max_concurrency", 0),
        ("embedding_max_concurrency", 0),
        ("feedback_retention_days", 0),
    ],
)
def test_invalid_operational_settings_fail_fast(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("auth_secret_key", "replace_with_at_least_32_random_characters"),
        ("vision_api_key", "your_opencode_api_key_here"),
        ("metrics_token", "replace-with-production-metrics-token"),
        (
            "database_url",
            "postgresql+asyncpg://foodai:foodai@db:5432/foodai",
        ),
    ],
)
def test_production_rejects_placeholder_or_development_credentials(
    field: str,
    value: str,
) -> None:
    values = {
        "environment": "production",
        "auth_secret_key": "a-unique-production-secret-with-32-characters",
        "rate_limit_backend": "redis",
        "vision_api_key": "real-vision-key",
        "object_storage_backend": "s3",
        "database_url": "postgresql+asyncpg://foodai_prod:secret@db:5432/foodai",
        "metrics_token": "metrics-secret-with-at-least-32-characters",
        field: value,
        "_env_file": None,
    }

    with pytest.raises(ValueError):
        Settings(**values)


def test_configuration_errors_do_not_echo_secret_inputs() -> None:
    leaked_secret = "database-secret-that-must-not-appear"

    with pytest.raises(ValueError) as exc:
        Settings(
            environment="production",
            auth_secret_key="a-unique-production-secret-with-32-characters",
            rate_limit_backend="redis",
            vision_api_key="real-vision-key",
            object_storage_backend="s3",
            database_url=(
                "postgresql+asyncpg://foodai_prod:"
                f"{leaked_secret}@localhost:5432/foodai"
            ),
            metrics_token="metrics-secret-with-at-least-32-characters",
            _env_file=None,
        )

    assert leaked_secret not in str(exc.value)
    assert Settings.model_config["hide_input_in_errors"] is True
