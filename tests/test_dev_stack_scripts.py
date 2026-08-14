"""Contracts for starting and stopping every local inference dependency."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_dev_up_does_not_start_retired_image_model_sidecars() -> None:
    script = _script("dev_up.sh")

    assert "start_image_embed.sh" not in script
    assert "wait_for_port 8082" not in script
    assert "Image matching" not in script


def test_dev_up_starts_food_gate_with_the_api_dependencies() -> None:
    script = _script("dev_up.sh")

    assert "docker compose --profile food-gate up -d postgres qdrant food-gate" in script


def test_dev_down_stops_food_gate_with_the_data_stores() -> None:
    script = _script("dev_down.sh")

    assert "docker compose stop postgres qdrant food-gate" in script


def test_dev_up_runs_migrations_through_the_installed_python_module() -> None:
    script = _script("dev_up.sh")

    assert "uv run python -m alembic upgrade head" in script


def test_dev_up_api_does_not_depend_on_a_stale_console_script_shebang() -> None:
    script = _script("dev_up.sh")

    assert '"$ROOT/.venv/bin/python" -m uvicorn backend.main:app' in script
    assert "uv run uvicorn backend.main:app" not in script
    assert 'nohup "$ROOT/.venv/bin/python" -m uvicorn backend.main:app' in script


def test_dev_up_clears_stale_siglip_hint_environment_before_starting_api() -> None:
    script = _script("dev_up.sh")

    for variable in (
        "SIGLIP_FOOD_HINT_MODE",
        "SIGLIP_FOOD_HINT_URL",
        "SIGLIP_FOOD_HINT_TIMEOUT_SECONDS",
        "SIGLIP_FOOD_HINT_TOP_K",
        "SIGLIP_FOOD_HINT_MIN_SCORE",
    ):
        assert f'unset "{variable}"' in script


def test_dev_down_does_not_stop_a_retired_image_embedding_process() -> None:
    down_script = _script("dev_down.sh")

    assert "image_embed.pid" not in down_script


def test_segment_process_does_not_depend_on_a_stale_console_script_shebang() -> None:
    start_script = _script("start_segment.sh")

    assert 'nohup "$PROJECT_ROOT/.venv/bin/python" -m uvicorn' in start_script
    assert "nohup uv run uvicorn" not in start_script


def test_dev_stack_shell_scripts_have_valid_syntax() -> None:
    for script_name in ("dev_up.sh", "dev_down.sh", "start_segment.sh"):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPTS / script_name)],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
