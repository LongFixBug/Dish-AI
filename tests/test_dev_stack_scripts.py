"""Contracts for starting and stopping every local inference dependency."""

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _script(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def test_dev_up_starts_and_waits_for_image_embedding_sidecar() -> None:
    script = _script("dev_up.sh")

    assert "bash scripts/start_image_embed.sh" in script
    assert "wait_for_port 8082" in script
    assert "Image matching" in script


def test_image_embedding_process_is_tracked_and_stopped() -> None:
    start_script = _script("start_image_embed.sh")
    down_script = _script("dev_down.sh")

    assert 'nohup "$PROJECT_ROOT/.venv/bin/uvicorn"' in start_script
    assert "nohup uv run uvicorn" not in start_script
    assert 'echo $! > "$RUN_DIR/image_embed.pid"' in start_script
    assert '"$RUN_DIR/image_embed.pid"' in down_script


def test_dev_stack_shell_scripts_have_valid_syntax() -> None:
    for script_name in ("dev_up.sh", "dev_down.sh", "start_image_embed.sh"):
        result = subprocess.run(
            ["bash", "-n", str(SCRIPTS / script_name)],
            check=False,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr
