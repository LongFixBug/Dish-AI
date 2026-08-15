from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _read(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8")


def test_api_image_includes_runtime_nutrition_snapshot() -> None:
    dockerfile = _read("Dockerfile")
    dockerignore = _read(".dockerignore")
    api_requirements = _read("requirements.api.txt")
    api_lock = _read("requirements.api.lock")

    assert "COPY data/vn_nutrition_reference_targets.json" in dockerfile
    assert "!data/" in dockerignore
    assert "!data/vn_nutrition_reference_targets.json" in dockerignore
    assert "langchain-community" in api_requirements
    assert "langchain-community==" in api_lock
    assert "langchain-text-splitters" in api_requirements
    assert "langchain-text-splitters==" in api_lock


def test_siglip_food_hint_image_contains_only_serving_artifacts() -> None:
    dockerfile = _read("Dockerfile.siglip-food-hint")
    dockerignore = _read(".dockerignore")

    assert "ml/inference/siglip_food_v1.py" in dockerfile
    assert "checkpoints/siglip_food_v1/encoder" in dockerfile
    assert "checkpoints/siglip_food_v1/classifier_head.pt" in dockerfile
    assert "!checkpoints/siglip_food_v1/" in dockerignore
    assert "--port ${PORT:-8085}" in dockerfile


def test_segment_image_uses_railway_port_and_healthcheck() -> None:
    dockerfile = _read("Dockerfile.segment")

    assert "ml.serving.segment_server:app" in dockerfile
    assert "--port ${PORT:-8083}" in dockerfile
    assert "/health" in dockerfile
