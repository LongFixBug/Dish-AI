"""Build a human-review queue for reference-album candidates.

This command is deliberately a queue builder, not an approval command.  It
never changes a candidate's review status and never turns a URL into a license
claim.  A path can enter the runtime album only after a reviewer writes a
separate manifest accepted by ``index_dish_images.py``.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "data/images/references_candidate"
DEFAULT_AUDIT = PROJECT_ROOT / "data/eval/reference_candidate_new_classes_audit.json"
DEFAULT_PROVENANCE = DEFAULT_ROOT / "_provenance.jsonl"
DEFAULT_REVIEWED = PROJECT_ROOT / "data/eval/reference_candidate_commons_reviewed.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/eval/reference_candidate_review_queue.json"
ALLOWED_LICENSE_STATUSES = frozenset(
    {"internal_permission", "user_consent", "public_domain", "cc0", "cc_by", "licensed"}
)


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} phải là JSON object")
    return value


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    records: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number} không phải JSON hợp lệ") from error
        if not isinstance(value, dict) or not isinstance(value.get("path"), str):
            raise ValueError(f"{path}:{line_number} thiếu path")
        records[value["path"]] = value
    return records


def _reviewed_data(path: Path | None) -> tuple[set[str], dict[str, dict[str, Any]]]:
    if path is None or not path.is_file():
        return set(), {}
    value = _load_object(path)
    reviewed_paths = value.get("reviewed_paths", [])
    records = value.get("provenance_records", [])
    if not isinstance(reviewed_paths, list) or not all(
        isinstance(item, str) for item in reviewed_paths
    ):
        raise ValueError(f"{path} thiếu reviewed_paths hợp lệ")
    if not isinstance(records, list):
        raise ValueError(f"{path} thiếu provenance_records hợp lệ")
    by_path = {
        record["path"]: record
        for record in records
        if isinstance(record, dict) and isinstance(record.get("path"), str)
    }
    return set(reviewed_paths), by_path


def _provenance_status(record: dict[str, Any] | None) -> str:
    if record is None:
        return "missing_record"
    source_url = record.get("source_url")
    license_status = record.get("license_status")
    if (
        not isinstance(source_url, str)
        or not source_url.startswith(("http://", "https://"))
        or license_status not in ALLOWED_LICENSE_STATUSES
    ):
        return "missing_license"
    return "ready"


def build_review_queue(
    root: Path,
    audit_path: Path,
    *,
    provenance_path: Path | None = None,
    reviewed_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Return a deterministic review queue without approving any path."""
    audit = _load_object(audit_path)
    approved_paths = audit.get("approved_paths")
    if not isinstance(approved_paths, list) or not all(
        isinstance(path, str) for path in approved_paths
    ):
        raise ValueError(f"{audit_path} thiếu approved_paths hợp lệ")

    sidecar_records = _load_jsonl(provenance_path or root / "_provenance.jsonl")
    reviewed_paths, reviewed_records = _reviewed_data(reviewed_manifest_path)
    records = {**sidecar_records, **reviewed_records}

    items: list[dict[str, Any]] = []
    for relative in sorted(set(approved_paths)):
        path = root / relative
        record = records.get(relative)
        items.append(
            {
                "path": relative,
                "class_slug": Path(relative).parent.name,
                "exists": path.is_file(),
                "review_status": "reviewed" if relative in reviewed_paths else "pending",
                "provenance_status": _provenance_status(record),
                "source_url": record.get("source_url") if record else None,
                "license_status": record.get("license_status") if record else None,
            }
        )

    reviewed_count = sum(item["review_status"] == "reviewed" for item in items)
    provenance_counts = {
        status: sum(item["provenance_status"] == status for item in items)
        for status in ("ready", "missing_record", "missing_license")
    }
    summary = {
        "total": len(items),
        "reviewed": reviewed_count,
        "pending_review": len(items) - reviewed_count,
        "provenance_ready": provenance_counts["ready"],
        "provenance_missing_record": provenance_counts["missing_record"],
        "provenance_missing_license": provenance_counts["missing_license"],
        "review_status": "reviewed" if reviewed_count == len(items) else "pending",
        "provenance_status": (
            "reviewed" if provenance_counts["ready"] == len(items) else "pending"
        ),
    }
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "root": str(root),
        "audit_manifest": str(audit_path),
        "summary": summary,
        "items": items,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a candidate review queue")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--provenance", type=Path, default=DEFAULT_PROVENANCE)
    parser.add_argument("--reviewed-manifest", type=Path, default=DEFAULT_REVIEWED)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = build_review_queue(
        args.root,
        args.audit,
        provenance_path=args.provenance,
        reviewed_manifest_path=args.reviewed_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Review queue: {args.output}")


if __name__ == "__main__":
    main()
