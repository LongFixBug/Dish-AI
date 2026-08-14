"""Tests for the candidate review/provenance queue artifact."""

import json
from pathlib import Path

from scripts.build_candidate_review_queue import build_review_queue


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def test_build_queue_keeps_review_and_provenance_as_separate_gates(tmp_path: Path) -> None:
    root = tmp_path / "references_candidate"
    (root / "pho_bo").mkdir(parents=True)
    (root / "banh_can").mkdir(parents=True)
    (root / "pho_bo" / "pho.jpg").write_bytes(b"image")
    (root / "banh_can" / "can.jpg").write_bytes(b"image")

    audit_path = tmp_path / "audit.json"
    _write_json(
        audit_path,
        {
            "approved_paths": ["banh_can/can.jpg", "pho_bo/pho.jpg"],
            "audit": {"counts_by_class": {"banh_can": 1, "pho_bo": 1}},
        },
    )
    provenance_path = root / "_provenance.jsonl"
    provenance_path.write_text(
        json.dumps(
            {
                "path": "pho_bo/pho.jpg",
                "source_url": "https://example.test/pho.jpg",
                "license_status": "cc_by",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    reviewed_path = tmp_path / "reviewed.json"
    _write_json(
        reviewed_path,
        {
            "reviewed_paths": ["pho_bo/pho.jpg"],
            "provenance_records": [
                {
                    "path": "pho_bo/pho.jpg",
                    "source_url": "https://example.test/pho.jpg",
                    "license_status": "cc_by",
                }
            ],
        },
    )

    report = build_review_queue(
        root,
        audit_path,
        provenance_path=provenance_path,
        reviewed_manifest_path=reviewed_path,
    )

    assert report["summary"] == {
        "total": 2,
        "reviewed": 1,
        "pending_review": 1,
        "provenance_ready": 1,
        "provenance_missing_record": 1,
        "provenance_missing_license": 0,
        "review_status": "pending",
        "provenance_status": "pending",
    }
    rows = {row["path"]: row for row in report["items"]}
    assert rows["pho_bo/pho.jpg"]["review_status"] == "reviewed"
    assert rows["pho_bo/pho.jpg"]["provenance_status"] == "ready"
    assert rows["banh_can/can.jpg"]["review_status"] == "pending"
    assert rows["banh_can/can.jpg"]["provenance_status"] == "missing_record"


def test_queue_marks_url_without_license_as_incomplete_provenance(tmp_path: Path) -> None:
    root = tmp_path / "references_candidate"
    class_dir = root / "pho_bo"
    class_dir.mkdir(parents=True)
    (class_dir / "pho.jpg").write_bytes(b"image")
    audit_path = tmp_path / "audit.json"
    _write_json(audit_path, {"approved_paths": ["pho_bo/pho.jpg"]})
    provenance_path = root / "_provenance.jsonl"
    provenance_path.write_text(
        json.dumps(
            {
                "path": "pho_bo/pho.jpg",
                "source_url": "https://example.test/pho.jpg",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = build_review_queue(root, audit_path, provenance_path=provenance_path)

    assert report["summary"]["provenance_missing_license"] == 1
    assert report["items"][0]["provenance_status"] == "missing_license"
