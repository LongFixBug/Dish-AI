import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_obsolete_clients_and_compatibility_entry_points_are_removed() -> None:
    obsolete_paths = (
        "FoodAI-CONTEXT.md",
        "LEARNING-ROADMAP.md",
        "hello.py",
        "requirements.txt",
        "streamlit_app.py",
        "scripts/create_tables.py",
        "scripts/seed_conversion_rates.py",
        "scripts/seed_grams_v2.py",
    )

    assert [path for path in obsolete_paths if (ROOT / path).is_file()] == []
    assert not list((ROOT / "scripts/legacy").rglob("*.py"))


def test_android_release_does_not_use_debug_signing() -> None:
    gradle = (ROOT / "mobile/android/app/build.gradle.kts").read_text()

    release_block = gradle.split("release {", maxsplit=1)[1]
    assert 'signingConfigs.getByName("debug")' not in release_block
    assert 'signingConfigs.getByName("release")' in release_block
    assert "key.properties" in gradle


def test_ci_covers_mobile_container_migrations_and_security() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()

    required_commands = (
        "flutter analyze",
        "flutter test --coverage",
        "flutter build apk --debug",
        "docker build",
        "alembic upgrade head",
        "pip-audit==2.10.1 pip-audit",
        "-r requirements.api.lock --require-hashes",
        "--disable-pip",
        "aquasecurity/trivy-action",
    )
    for command in required_commands:
        assert command in workflow


def test_release_mobile_requires_https_api_endpoint() -> None:
    workflow = (ROOT / ".github/workflows/release-mobile.yml").read_text()
    api_config = (ROOT / "mobile/lib/core/config/api_config.dart").read_text()

    assert "secrets.API_BASE_URL" in workflow
    assert "--dart-define=API_BASE_URL=$API_BASE_URL" in workflow
    assert "kReleaseMode" in api_config
    assert "uri.scheme != 'https'" in api_config


def test_api_image_can_run_database_migrations() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    requirements = (ROOT / "requirements.api.txt").read_text()

    assert "COPY alembic.ini" in dockerfile
    assert "COPY alembic" in dockerfile
    assert "alembic" in requirements


def test_api_image_includes_google_auth_used_during_startup() -> None:
    requirements = (ROOT / "requirements.api.txt").read_text()
    lockfile = (ROOT / "requirements.api.lock").read_text()
    project = (ROOT / "pyproject.toml").read_text()

    assert "google-auth" in requirements
    assert "google-auth==" in lockfile
    assert "requests" in requirements
    assert "requests==" in lockfile
    assert '"requests>=' in project


def test_release_build_passes_every_compile_time_secret() -> None:
    """Client ID là hằng số compile-time: thiếu nó thì nút Google hỏng vĩnh viễn.

    Không test Flutter nào bắt được vì test dùng gateway giả, nên chốt ở đây.
    """
    workflow = (ROOT / ".github/workflows/release-mobile.yml").read_text()

    assert "--dart-define=API_BASE_URL=$API_BASE_URL" in workflow
    assert "--dart-define=GOOGLE_WEB_CLIENT_ID=$GOOGLE_WEB_CLIENT_ID" in workflow
    assert "secrets.GOOGLE_WEB_CLIENT_ID" in workflow
    assert "GOOGLE_WEB_CLIENT_ID secret is missing or malformed" in workflow


def test_mobile_documents_the_required_dart_defines() -> None:
    readme = (ROOT / "mobile/README.md").read_text()
    example = (ROOT / "mobile/dart_defines.example.json").read_text()

    assert "--dart-define-from-file" in readme
    for key in ("API_BASE_URL", "GOOGLE_WEB_CLIENT_ID", "IOS_CLIENT_ID"):
        assert key in readme, key
        assert key in example, key


def test_dependency_and_toolchain_versions_are_reproducible() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    lockfile = (ROOT / "requirements.api.lock").read_text()
    dockerfile = (ROOT / "Dockerfile").read_text()

    assert 'version: "0.11.7"' in workflow
    assert 'flutter-version: "3.44.8"' in workflow
    assert "uv sync --all-groups --frozen" in workflow
    assert "--hash=sha256:" in lockfile
    assert "python:3.12-slim@sha256:" in dockerfile
    # Image CV cũng chạy production nên phải pin digest như image API.
    assert "python:3.12-slim@sha256:" in (ROOT / "Dockerfile.cv").read_text()


def test_cv_image_installs_a_complete_hashed_lockfile() -> None:
    dockerfile = (ROOT / "Dockerfile.cv").read_text()
    lockfile = (ROOT / "requirements.cv.lock").read_text()
    requirements = (ROOT / "requirements.cv.txt").read_text()

    assert "COPY requirements.cv.lock" in dockerfile
    assert "-r requirements.cv.lock" in dockerfile
    for package in ("torch==2.13.0+cpu", "torchvision==0.28.0+cpu", "timm=="):
        assert package in lockfile
    assert "--hash=sha256:" in lockfile
    assert "--find-links https://download.pytorch.org/whl/cpu/torch/" in requirements
    assert "--find-links https://download.pytorch.org/whl/cpu/torchvision/" in requirements
    assert "--find-links https://download.pytorch.org/whl/cpu/torch/" in lockfile
    assert "--find-links https://download.pytorch.org/whl/cpu/torchvision/" in lockfile
    for package in (r"torch==2\.13\.0\+cpu", r"torchvision==0\.28\.0\+cpu"):
        assert re.search(rf"{package} \\\n(?:    --hash=sha256:[a-f0-9]{{64}}\n)+", lockfile)
    assert "cuda-toolkit" not in lockfile


def test_container_healthchecks_probe_liveness_not_readiness() -> None:
    """Healthcheck quyết định restart container, nên phải độc lập với dịch vụ ngoài."""
    for name in ("Dockerfile", "Dockerfile.cv"):
        healthcheck = [
            line
            for line in (ROOT / name).read_text().splitlines()
            if "urlopen(" in line
        ]
        assert healthcheck, f"{name} thiếu HEALTHCHECK"
        assert all("/live" in line for line in healthcheck), name
