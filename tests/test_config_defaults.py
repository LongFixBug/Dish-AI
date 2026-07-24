"""Configuration defaults must match the checked-in local stack."""

from backend.config import Settings


def test_database_default_matches_docker_compose_port() -> None:
    default_url = Settings.model_fields["database_url"].default

    assert default_url.endswith("localhost:5432/foodai")


def test_runtime_defaults_are_safe_and_documented() -> None:
    assert Settings.model_fields["debug"].default is False
    assert Settings.model_fields["vision_model"].default == "qwen3.7-plus"


def test_qdrant_default_matches_local_compose() -> None:
    assert Settings.model_fields["qdrant_url"].default == "http://localhost:6333"
