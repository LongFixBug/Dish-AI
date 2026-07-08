"""Tests for health check endpoint."""

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """Health endpoint should return 200 with status ok."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_health_returns_correct_version(client: TestClient) -> None:
    """Health endpoint should return the configured version."""
    response = client.get("/health")

    data = response.json()
    assert data["version"] == "0.1.0"
def test_info_returns_ok(client: TestClient) -> None:
    """Info endpoint should return 200 with app info."""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "FoodAI"
    assert "author" in data
    assert "vision_model" in data
    assert "llm_model" in data