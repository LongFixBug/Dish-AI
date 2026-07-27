"""Unit tests cho phần pure của ml.evaluation.recognition_eval.

HTTP được mock hoàn toàn bằng httpx.MockTransport — chạy offline.
"""

import json

import httpx
import pytest

from ml.evaluation.recognition_eval import (
    NO_PREDICTION,
    ClassTruth,
    ImageResult,
    build_report,
    build_url,
    collect_images,
    compute_metrics,
    confusion_counts,
    extract_prediction,
    is_correct,
    load_ground_truth,
    normalize_name,
    run_eval,
)


def _truth(slug: str, display: str, aliases: tuple[str, ...] = ()) -> ClassTruth:
    return ClassTruth(
        slug=slug,
        display_name=display,
        acceptable=frozenset(
            normalize_name(n) for n in (display, *aliases)
        ),
    )


def _result(**overrides) -> ImageResult:
    base = {
        "image": "img.jpg",
        "truth_slug": "pho_bo",
        "truth_name": "Phở bò",
        "predicted": None,
        "vision_dish_name": None,
        "found_in_db": False,
        "correct": False,
    }
    return ImageResult(**{**base, **overrides})


# ─── normalize + matching ────────────────────────────────────────────────────


def test_normalize_name_strips_accents_and_casefolds():
    assert normalize_name("Phở Bò") == "pho bo"
    assert normalize_name("BÚN CHẢ") == "bun cha"


def test_normalize_name_collapses_whitespace():
    assert normalize_name("  Bánh   mì  ") == "banh mi"


def test_normalize_name_maps_dj_to_d():
    assert normalize_name("Bánh đa cua") == "banh da cua"


def test_is_correct_accepts_display_name_accent_insensitive():
    truth = _truth("pho_bo", "Phở bò")
    assert is_correct("Phở bò", truth)
    assert is_correct("pho bo", truth)
    assert is_correct("PHO   BO", truth)


def test_is_correct_accepts_alias_and_rejects_other_dish():
    truth = _truth("pho_bo", "Phở bò", ("Phở bò tái", "Phở bò chín"))
    assert is_correct("phở bò tái", truth)
    assert not is_correct("Bún chả", truth)


def test_is_correct_rejects_none_prediction():
    assert not is_correct(None, _truth("pho_bo", "Phở bò"))


def test_load_ground_truth_merges_aliases(tmp_path):
    class_names = tmp_path / "class_names.json"
    aliases = tmp_path / "dish_aliases.json"
    class_names.write_text(
        json.dumps({"pho_bo": "Phở bò"}, ensure_ascii=False), encoding="utf-8"
    )
    aliases.write_text(
        json.dumps({"pho_bo": ["Phở bò tái"]}, ensure_ascii=False),
        encoding="utf-8",
    )

    truths = load_ground_truth(class_names, aliases)

    assert truths["pho_bo"].display_name == "Phở bò"
    assert truths["pho_bo"].acceptable == frozenset({"pho bo", "pho bo tai"})


def test_load_ground_truth_without_aliases_file(tmp_path):
    class_names = tmp_path / "class_names.json"
    class_names.write_text(
        json.dumps({"pho_ga": "Phở gà"}, ensure_ascii=False), encoding="utf-8"
    )

    truths = load_ground_truth(class_names, tmp_path / "missing.json")

    assert truths["pho_ga"].acceptable == frozenset({"pho ga"})


# ─── extract_prediction ──────────────────────────────────────────────────────


def test_extract_prediction_picks_first_non_side_dish():
    payload = {
        "dishes": [
            {"dish_name": "Canh chua", "is_side": True, "found_in_db": True},
            {
                "dish_name": "Phở bò",
                "vision_dish_name": "Phở bò tái",
                "is_side": False,
                "found_in_db": True,
            },
            {"dish_name": "Cơm tấm", "is_side": False, "found_in_db": False},
        ]
    }

    prediction = extract_prediction(payload)

    assert prediction.dish_name == "Phở bò"
    assert prediction.vision_dish_name == "Phở bò tái"
    assert prediction.found_in_db is True


def test_extract_prediction_empty_dishes_is_no_prediction():
    assert extract_prediction({"dishes": []}).dish_name is None
    assert extract_prediction({}).dish_name is None


def test_extract_prediction_only_sides_is_no_prediction():
    payload = {"dishes": [{"dish_name": "Trà đá", "is_side": True}]}
    assert extract_prediction(payload).dish_name is None


# ─── collect_images ──────────────────────────────────────────────────────────


def test_collect_images_reads_class_layout_and_limits(tmp_path):
    (tmp_path / "pho_bo").mkdir()
    (tmp_path / "pho_ga").mkdir()
    (tmp_path / "pho_bo" / "b.jpg").write_bytes(b"x")
    (tmp_path / "pho_bo" / "a.jpg").write_bytes(b"x")
    (tmp_path / "pho_bo" / "notes.txt").write_text("skip")
    (tmp_path / "pho_ga" / "c.png").write_bytes(b"x")

    pairs = collect_images(tmp_path)
    assert [(slug, p.name) for slug, p in pairs] == [
        ("pho_bo", "a.jpg"),
        ("pho_bo", "b.jpg"),
        ("pho_ga", "c.png"),
    ]

    limited = collect_images(tmp_path, limit_per_class=1)
    assert [(slug, p.name) for slug, p in limited] == [
        ("pho_bo", "a.jpg"),
        ("pho_ga", "c.png"),
    ]


def test_collect_images_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        collect_images(tmp_path / "missing")


# ─── metrics ─────────────────────────────────────────────────────────────────


def _sample_results() -> list[ImageResult]:
    return [
        _result(predicted="Phở bò", found_in_db=True, correct=True),
        _result(predicted="Bún chả", correct=False),
        _result(
            truth_slug="pho_ga", truth_name="Phở gà",
            predicted="Phở gà", correct=True,
        ),
        _result(truth_slug="pho_ga", truth_name="Phở gà", predicted=None),
        _result(
            truth_slug="xoi_xeo", truth_name="Xôi xéo",
            predicted=None, error="RuntimeError: HTTP 500",
        ),
    ]


def test_compute_metrics_on_synthetic_results():
    metrics = compute_metrics(_sample_results())

    assert metrics["total_images"] == 5
    assert metrics["correct"] == 2
    assert metrics["top1_accuracy"] == pytest.approx(0.4)
    assert metrics["per_class"]["pho_bo"]["accuracy"] == pytest.approx(0.5)
    assert metrics["per_class"]["pho_ga"]["accuracy"] == pytest.approx(0.5)
    assert metrics["per_class"]["xoi_xeo"]["accuracy"] == pytest.approx(0.0)
    assert metrics["macro_recall"] == pytest.approx(0.333, abs=1e-3)
    # Lỗi request không tính vào no_prediction — hai chỉ số tách bạch.
    assert metrics["no_prediction"] == 1
    assert metrics["no_prediction_rate"] == pytest.approx(0.2)
    assert metrics["request_errors"] == 1
    assert metrics["found_in_db"] == 1


def test_compute_metrics_empty_results():
    metrics = compute_metrics([])
    assert metrics["total_images"] == 0
    assert metrics["top1_accuracy"] == 0.0
    assert metrics["macro_recall"] == 0.0


def test_confusion_counts_groups_truth_to_predicted():
    confusion = confusion_counts(_sample_results())

    assert confusion["Phở bò"] == {"Phở bò": 1, "Bún chả": 1}
    assert confusion["Phở gà"] == {"Phở gà": 1, NO_PREDICTION: 1}
    assert confusion["Xôi xéo"] == {NO_PREDICTION: 1}


def test_build_report_shape_is_json_serializable():
    report = build_report(
        _sample_results(), "http://x/api/v1/analyze", "data/images/golden",
        "20260726_120000",
    )

    assert set(report) == {
        "timestamp", "suite", "endpoint", "images_dir",
        "metrics", "confusion", "errors", "per_image",
    }
    assert report["suite"] == "recognition_eval"
    assert len(report["per_image"]) == 5
    assert len(report["errors"]) == 3  # chỉ các ảnh sai
    assert all(
        set(e) == {"image", "truth", "predicted"} for e in report["errors"]
    )
    json.dumps(report, ensure_ascii=False)  # không được nổ


# ─── URL ─────────────────────────────────────────────────────────────────────


def test_build_url_appends_route_and_respects_vision_only():
    assert build_url("http://localhost:8000", False) == (
        "http://localhost:8000/api/v1/analyze"
    )
    assert build_url("http://localhost:8000/", True) == (
        "http://localhost:8000/api/v1/analyze/vision-only"
    )
    full = "http://staging:9000/api/v1/analyze"
    assert build_url(full, False) == full


# ─── run_eval với HTTP mock ──────────────────────────────────────────────────


async def test_run_eval_posts_multipart_field_file_and_records_errors(tmp_path):
    (tmp_path / "pho_bo").mkdir()
    (tmp_path / "pho_ga").mkdir()
    (tmp_path / "pho_bo" / "a.jpg").write_bytes(b"fake-jpeg")
    (tmp_path / "pho_ga" / "b.jpg").write_bytes(b"fake-jpeg")
    truths = {
        "pho_bo": _truth("pho_bo", "Phở bò"),
        "pho_ga": _truth("pho_ga", "Phở gà"),
    }
    seen_fields: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_fields.append(request.content)
        if b'filename="a.jpg"' in request.content:
            payload = {
                "dishes": [
                    {"dish_name": "Phở bò", "is_side": False, "found_in_db": True}
                ]
            }
            return httpx.Response(200, json=payload)
        return httpx.Response(500, text="boom")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        results = await run_eval(
            collect_images(tmp_path), truths,
            "http://test/api/v1/analyze", client=client,
        )

    assert all(b'name="file"' in content for content in seen_fields)
    by_slug = {r.truth_slug: r for r in results}
    assert by_slug["pho_bo"].correct is True
    assert by_slug["pho_bo"].found_in_db is True
    assert by_slug["pho_ga"].correct is False
    assert "HTTP 500" in by_slug["pho_ga"].error


async def test_run_eval_empty_dishes_counts_as_no_prediction(tmp_path):
    (tmp_path / "pho_bo").mkdir()
    (tmp_path / "pho_bo" / "a.jpg").write_bytes(b"fake-jpeg")
    truths = {"pho_bo": _truth("pho_bo", "Phở bò")}
    message = "Vision không nhận diện được món ăn trong ảnh."

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"dishes": [], "error": message})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        results = await run_eval(
            collect_images(tmp_path), truths,
            "http://test/api/v1/analyze", client=client,
        )

    assert results[0].predicted is None
    assert results[0].error is None
    assert results[0].detail == message
    metrics = compute_metrics(results)
    assert metrics["no_prediction"] == 1
    assert metrics["request_errors"] == 0


# ─── 429 retry ────────────────────────────────────────────────────────────────


async def test_analyze_image_retries_on_429_then_succeeds(tmp_path) -> None:
    from ml.evaluation import recognition_eval as re_mod

    image = tmp_path / "pho.jpg"
    image.write_bytes(b"fake-jpeg")
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0.01"})
        return httpx.Response(200, json={"dishes": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        payload = await re_mod.analyze_image(client, "http://x/analyze", image)

    assert calls["n"] == 2
    assert payload == {"dishes": []}


def test_retry_after_seconds_parses_and_defaults() -> None:
    from ml.evaluation.recognition_eval import (
        DEFAULT_RETRY_AFTER_SECONDS,
        _retry_after_seconds,
    )

    assert _retry_after_seconds(httpx.Response(429, headers={"Retry-After": "7"})) == 7.0
    assert _retry_after_seconds(httpx.Response(429, headers={"Retry-After": "999"})) == 120.0
    assert (
        _retry_after_seconds(httpx.Response(429))
        == DEFAULT_RETRY_AFTER_SECONDS
    )
