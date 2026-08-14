"""Tests for the open-license Wikimedia Commons candidate crawler."""

from io import BytesIO

from PIL import Image

from scripts import crawl_commons_reference_classes as crawler
from scripts.crawl_commons_reference_classes import (
    CommonsCandidate,
    is_candidate_title_relevant,
    parse_commons_candidates,
    normalize_license_status,
    provenance_record,
)


def test_normalize_license_status_allows_only_reusable_licenses() -> None:
    assert normalize_license_status("CC0") == "cc0"
    assert normalize_license_status("Public domain") == "public_domain"
    assert normalize_license_status("CC BY-SA 4.0") == "cc_by"
    assert normalize_license_status("CC BY-NC 4.0") is None
    assert normalize_license_status("") is None


def test_target_classes_include_the_soup_confusion_group() -> None:
    assert crawler.TARGET_CLASSES["hu_tieu"] == "Hủ tiếu"
    assert crawler.TARGET_CLASSES["bun_bo_hue"] == "Bún bò Huế"
    assert crawler.TARGET_CLASSES["chao_long"] == "Cháo lòng"


def test_parse_commons_candidates_keeps_license_and_source_page() -> None:
    payload = {
        "query": {
            "pages": {
                "2": {
                    "pageid": 2,
                    "title": "File:Banh Xeo.jpg",
                    "imageinfo": [
                        {
                            "url": "https://upload.wikimedia.org/full.jpg",
                            "thumburl": "https://upload.wikimedia.org/thumb.jpg",
                            "descriptionurl": "https://commons.wikimedia.org/wiki/File:Banh_Xeo.jpg",
                            "extmetadata": {
                                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                "Artist": {"value": "Example"},
                            },
                        }
                    ],
                },
                "1": {
                    "pageid": 1,
                    "title": "File:Unlicensed.jpg",
                    "imageinfo": [
                        {
                            "url": "https://example.com/unlicensed.jpg",
                            "extmetadata": {},
                        }
                    ],
                },
            }
        }
    }

    candidates = parse_commons_candidates(payload, limit=10)

    assert candidates == [
        CommonsCandidate(
            title="File:Banh Xeo.jpg",
            image_url="https://upload.wikimedia.org/thumb.jpg",
            source_url="https://commons.wikimedia.org/wiki/File:Banh_Xeo.jpg",
            license_name="CC BY-SA 4.0",
            license_status="cc_by",
            artist="Example",
        )
    ]


def test_provenance_record_is_index_manifest_ready() -> None:
    candidate = CommonsCandidate(
        title="File:Pho.jpg",
        image_url="https://upload.wikimedia.org/pho.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:Pho.jpg",
        license_name="CC0",
        license_status="cc0",
        artist="Example",
    )

    assert provenance_record("pho_bo/pho_bo_commons_0.jpg", candidate) == {
        "path": "pho_bo/pho_bo_commons_0.jpg",
        "source_url": "https://commons.wikimedia.org/wiki/File:Pho.jpg",
        "license_status": "cc0",
        "license_name": "CC0",
        "source_title": "File:Pho.jpg",
        "artist": "Example",
    }


def test_candidate_title_filter_rejects_unrelated_commons_search_hits() -> None:
    candidate = CommonsCandidate(
        title="File:Big Mac hamburger.jpg",
        image_url="https://upload.wikimedia.org/big-mac.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:Big_Mac_hamburger.jpg",
        license_name="CC0",
        license_status="cc0",
        artist="Example",
    )

    assert not is_candidate_title_relevant(candidate, "Bánh căn")
    assert is_candidate_title_relevant(candidate, "Hamburger")


def test_run_updates_cross_class_duplicate_registry(tmp_path, monkeypatch) -> None:
    image = Image.effect_noise((120, 120), 64).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    candidate = CommonsCandidate(
        title="File:Bánh căn Bánh xèo shared.jpg",
        image_url="https://upload.wikimedia.org/shared.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:Shared.jpg",
        license_name="CC0",
        license_status="cc0",
        artist="Example",
    )

    monkeypatch.setattr(crawler, "collect_blocked_hashes", lambda _roots: [])

    counts = crawler.run(
        per_class=1,
        search_limit=1,
        sleep_seconds=0,
        candidate_root=tmp_path / "references_candidate",
        requested_classes="banh_can,banh_xeo",
        query=lambda _name, *, limit: [candidate][:limit],
        download=lambda _url: buffer.getvalue(),
    )

    assert counts == {"banh_can": 1, "banh_xeo": 0}


def test_run_does_not_download_unrelated_title_hits(tmp_path, monkeypatch) -> None:
    image = Image.effect_noise((120, 120), 64).convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    candidates = [
        CommonsCandidate(
            title="File:Big Mac hamburger.jpg",
            image_url="https://upload.wikimedia.org/big-mac.jpg",
            source_url="https://commons.wikimedia.org/wiki/File:Big_Mac_hamburger.jpg",
            license_name="CC0",
            license_status="cc0",
            artist="Example",
        ),
        CommonsCandidate(
            title="File:Bánh căn Đà Lạt.jpg",
            image_url="https://upload.wikimedia.org/banh-can.jpg",
            source_url="https://commons.wikimedia.org/wiki/File:Banh_can.jpg",
            license_name="CC0",
            license_status="cc0",
            artist="Example",
        ),
    ]
    downloaded: list[str] = []

    monkeypatch.setattr(crawler, "collect_blocked_hashes", lambda _roots: [])

    counts = crawler.run(
        per_class=1,
        search_limit=2,
        sleep_seconds=0,
        candidate_root=tmp_path / "references_candidate",
        requested_classes="banh_can",
        query=lambda _name, *, limit: candidates[:limit],
        download=lambda url: downloaded.append(url) or buffer.getvalue(),
    )

    assert counts == {"banh_can": 1}
    assert downloaded == ["https://upload.wikimedia.org/banh-can.jpg"]
