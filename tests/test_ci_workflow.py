"""Contracts that keep CI independent from an arbitrary runner platform."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_MOBILE_WORKFLOW = ROOT / ".github" / "workflows" / "release-mobile.yml"
DART_TEST_CONFIG = ROOT / "mobile" / "dart_test.yaml"
GOLDEN_TESTS = (
    ROOT / "mobile" / "test" / "features" / "analyze" / "analyze_screens_golden_test.dart",
    ROOT / "mobile" / "test" / "features" / "auth" / "welcome_golden_test.dart",
    ROOT / "mobile" / "test" / "features" / "chat" / "chat_screen_golden_test.dart",
    ROOT / "mobile" / "test" / "features" / "journal" / "journal_golden_test.dart",
    ROOT / "mobile" / "test" / "features" / "onboarding" / "onboarding_golden_test.dart",
)


def test_ci_uses_a_supported_versioned_trivy_tag() -> None:
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    # Only the API image remains in CI; retired local image-model images are
    # no longer built or scanned here.
    assert workflow.count("aquasecurity/trivy-action@v0.36.0") == 1
    assert "aquasecurity/trivy-action@v0.32.0" not in workflow
    assert "aquasecurity/trivy-action@0.32.0" not in workflow


def test_linux_workflows_exclude_platform_specific_golden_tests() -> None:
    ci_workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    release_workflow = RELEASE_MOBILE_WORKFLOW.read_text(encoding="utf-8")

    assert "flutter test --coverage --exclude-tags=golden" in ci_workflow
    assert "flutter test --exclude-tags=golden" in release_workflow


def test_visual_golden_suites_are_explicitly_tagged() -> None:
    for golden_test in GOLDEN_TESTS:
        source = golden_test.read_text(encoding="utf-8")

        assert "@Tags(['golden'])" in source, golden_test


def test_golden_tag_is_declared_for_the_dart_test_runner() -> None:
    config = DART_TEST_CONFIG.read_text(encoding="utf-8")

    assert "tags:" in config
    assert "  golden:" in config
