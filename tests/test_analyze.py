"""Tests cho POST /analyze (ảnh → nutrition, 2-tier CV + vision).

Mock cv_model.predict + identify_dish để không phụ thuộc model/API thật.
Dùng httpx.AsyncClient (async) + db_session fixture (cùng event loop) —
tránh asyncpg InterfaceError/teardown error khi mix TestClient sync + async DB.
"""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.db.postgres import get_session
from backend.main import app
from ml.inference.cv import cv_model
from tests.conftest import db_session  # noqa: F401  (fixture)

TEST_IMAGE = Path("data/test_images/pho.jpg")


@pytest.fixture(autouse=True)
def _reset_cv_loaded():
    """Reset cv_model._loaded=False sau mỗi test (singleton global, tránh state leak)."""
    yield
    cv_model._loaded = False


def _upload_bytes() -> bytes:
    """Bytes ảnh test (JPEG hợp lệ)."""
    return TEST_IMAGE.read_bytes()


def _mock_predict(monkeypatch, dish_name, confidence, source="local"):
    """Mock cv_model.predict trả dict."""
    monkeypatch.setattr(
        cv_model, "predict",
        lambda _path: {
            "dish_name": dish_name,
            "confidence": confidence,
            "all_predictions": [],
            "source": source,
        },
    )
    monkeypatch.setattr(cv_model, "_loaded", True, raising=False)


def _mock_vision(monkeypatch, dish_name, ingredients, confidence=0.8):
    """Mock identify_dish (async) trả dict."""
    async def _fake(_path):
        return {
            "dish_name": dish_name,
            "ingredients": ingredients,
            "confidence": confidence,
        }
    monkeypatch.setattr("backend.api.analyze.identify_dish", _fake)


def _override_db(db_session):
    """Override get_session sang db_session fixture (engine riêng per-test)."""
    async def _override():
        yield db_session
    app.dependency_overrides[get_session] = _override


# ─── Tier 1: CV conf cao → lookup ────────────────────────────────────────────


async def test_cv_high_conf_lookup_institute(db_session, monkeypatch) -> None:
    """CV conf 0.9 'Com Suon' → lookup institute 'Cơm sườn' → source=cv_local."""
    _mock_predict(monkeypatch, dish_name="Com Suon", confidence=0.9)
    _mock_vision(monkeypatch, dish_name="zzz", ingredients=[])
    _override_db(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/analyze",
            files={"file": ("pho.jpg", _upload_bytes(), "image/jpeg")},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "cv_local", f"got {data}"
    assert data["cv_confidence"] == 0.9
    assert data["nutrition"] is not None


# ─── Tier 2: CV conf thấp → vision ───────────────────────────────────────────


async def test_cv_low_conf_fallback_vision(db_session, monkeypatch) -> None:
    """CV conf 0.3 → vision → source=vision, ingredients + nutrition."""
    _mock_predict(monkeypatch, dish_name="Pho Bo", confidence=0.3)
    _mock_vision(
        monkeypatch, dish_name="phở bò",
        ingredients=[{"name": "thịt nạc", "gram": 100}],
    )
    _override_db(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/analyze",
            files={"file": ("pho.jpg", _upload_bytes(), "image/jpeg")},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "vision"
    assert data["ingredients"] is not None
    assert len(data["ingredients"]) == 1
    assert data["nutrition"] is not None


# ─── CV conf cao nhưng lookup miss → vision ──────────────────────────────────


async def test_cv_not_found_fallback_vision(db_session, monkeypatch) -> None:
    """CV conf 0.9 dish 'zzz lạ 9f3k' → lookup miss → vision → cv_local_not_found_vision."""
    _mock_predict(monkeypatch, dish_name="zzz lạ 9f3k", confidence=0.9)
    _mock_vision(
        monkeypatch, dish_name="món lạ",
        ingredients=[{"name": "thịt nạc", "gram": 50}],
    )
    _override_db(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/analyze",
            files={"file": ("pho.jpg", _upload_bytes(), "image/jpeg")},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["source"] == "cv_local_not_found_vision"


# ─── Map name → ingredient_id ────────────────────────────────────────────────


async def test_resolve_ingredient_id_map(db_session) -> None:
    """Helper _resolve_ingredient_id với 'sữa bò' (ILIKE match thật) → trả UUID str."""
    from backend.api.analyze import _resolve_ingredient_id

    ing_id = await _resolve_ingredient_id(db_session, "sữa bò")
    assert ing_id is not None, "'sữa bò' phải map được ingredient_id (ILIKE có trong DB)"
    assert isinstance(ing_id, str)
    assert len(ing_id) == 36  # UUID format


# ─── Missing ingredient ──────────────────────────────────────────────────────


async def test_missing_ingredient(db_session, monkeypatch) -> None:
    """Vision trả ingredient không có DB → missing_ingredients chứa, confidence<1.0."""
    _mock_predict(monkeypatch, dish_name="Pho Bo", confidence=0.3)
    _mock_vision(
        monkeypatch, dish_name="phở bò xyz 9f3k",
        ingredients=[
            {"name": "zzz nguyên liệu kỳ lạ 9f3k xyz", "gram": 100},
            {"name": "sữa bò", "gram": 50},
        ],
    )
    _override_db(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post(
            "/api/v1/analyze",
            files={"file": ("pho.jpg", _upload_bytes(), "image/jpeg")},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "zzz nguyên liệu kỳ lạ 9f3k xyz" in data["missing_ingredients"]
    assert "sữa bò" not in data["missing_ingredients"]
    assert data["nutrition"]["confidence_score"] < 1.0


# ─── Startup load fail graceful ───────────────────────────────────────────────


async def test_startup_load_fail_graceful(db_session, monkeypatch) -> None:
    """cv_model.load raise → lifespan catch → app vẫn start, /analyze fallback vision."""
    monkeypatch.setattr(cv_model, "load", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    _mock_vision(
        monkeypatch, dish_name="phở bò",
        ingredients=[{"name": "thịt nạc", "gram": 100}],
    )
    _override_db(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # lifespan chạy qua ASGITransport startup
        health = await ac.get("/health")
        assert health.status_code == 200
        resp = await ac.post(
            "/api/v1/analyze",
            files={"file": ("pho.jpg", _upload_bytes(), "image/jpeg")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["source"] == "vision"
    app.dependency_overrides.clear()
