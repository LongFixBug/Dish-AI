from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runpod_gpu_image_uses_cuda_torch_and_the_gpu_only_sidecar() -> None:
    dockerfile = (ROOT / "Dockerfile.runpod-ml").read_text(encoding="utf-8")
    startup = (ROOT / "scripts" / "start_food_gate_railway.sh").read_text(encoding="utf-8")

    assert "cu124" in dockerfile
    assert "torch==2.6.0" in dockerfile
    assert "torchvision==0.21.0" in dockerfile
    assert "start_food_gate_railway.sh" in dockerfile
    assert "ML_SIDECAR_APP" in startup
    assert "ml.serving.ml_gpu_sidecar:app" in dockerfile
    assert "PORT=8080" in dockerfile
    assert '"${PORT:-8084}"' in startup


def test_gpu_sidecar_does_not_publish_the_sticker_segmentation_route() -> None:
    gpu_sidecar = (ROOT / "ml" / "serving" / "ml_gpu_sidecar.py").read_text(
        encoding="utf-8"
    )

    assert "segment_server" not in gpu_sidecar
    assert ".mount(\"/segment\"" not in gpu_sidecar


def test_runpod_guide_documents_warm_gpu_and_railway_variables() -> None:
    guide = (ROOT / "docs" / "runpod-gpu-sidecar.md").read_text(encoding="utf-8")

    assert "SIGLIP_FOOD_V1_WARM_ON_STARTUP=true" in guide
    assert "FOOD_GATE_URL" in guide
    assert "SIGLIP_FOOD_HINT_URL" in guide
    assert "SIGLIP_FOOD_HINT_SERVICE_TOKEN" in guide
    assert "FOOD_GATE_SERVICE_TOKEN" in guide


def test_github_action_builds_the_amd64_runpod_image_on_demand() -> None:
    workflow = (ROOT / ".github" / "workflows" / "publish-runpod-image.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" in workflow
    assert "packages: write" in workflow
    assert "Dockerfile.runpod-ml" in workflow
    assert "linux/amd64" in workflow
