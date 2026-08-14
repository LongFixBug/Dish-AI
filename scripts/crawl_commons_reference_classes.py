"""Collect open-license Wikimedia Commons images into reference candidates.

The output remains staging data.  Commons license metadata is recorded, but a
reviewer still has to confirm that the image matches the folder label before a
candidate manifest can be indexed.

Usage:
    uv run python scripts/crawl_commons_reference_classes.py --per-class 10
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_reference_album import (  # noqa: E402
    CANDIDATE_DIR,
    GOLDEN_DIR,
    PROVENANCE_FILENAME,
    REFERENCES_DIR,
    TEST_DIR,
    TRAIN_DIR,
    VAL_DIR,
    collect_blocked_hashes,
    hash_directory_images,
)
from scripts.build_test_split import save_survivors, select_survivors  # noqa: E402
from backend.services.menu_vocabulary import accent_tokens  # noqa: E402

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
COMMONS_USER_AGENT = "FoodAI/0.1 reference-candidate research"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

TARGET_CLASSES: dict[str, str] = {
    "banh_can": "Bánh căn",
    "banh_canh": "Bánh canh",
    "banh_chung": "Bánh chưng",
    "banh_khot": "Bánh khọt",
    "banh_tet": "Bánh tét",
    "banh_trang_nuong": "Bánh tráng nướng",
    "banh_xeo": "Bánh xèo",
    "bun_bo_hue": "Bún bò Huế",
    "chao_long": "Cháo lòng",
    "hu_tieu": "Hủ tiếu",
    "pho_bo": "Phở bò",
}


@dataclass(frozen=True)
class CommonsCandidate:
    """One Commons file with reusable license metadata."""

    title: str
    image_url: str
    source_url: str
    license_name: str
    license_status: str
    artist: str


def _metadata_value(metadata: Mapping[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, Mapping):
        return ""
    raw = value.get("value", "")
    if not isinstance(raw, str):
        return ""
    return re.sub(r"<[^>]+>", "", raw).strip()


def normalize_license_status(license_name: str) -> str | None:
    """Map Commons short names to the small license allow-list."""
    normalized = " ".join(license_name.casefold().split())
    if normalized in {"cc0", "cc0 1.0"}:
        return "cc0"
    if normalized.startswith("public domain"):
        return "public_domain"
    if normalized.startswith("cc by-sa ") or normalized.startswith("cc by "):
        return "cc_by"
    return None


def parse_commons_candidates(
    payload: Mapping[str, object], *, limit: int
) -> list[CommonsCandidate]:
    """Parse stable, licensed image records from one Commons API response."""
    query = payload.get("query")
    pages = query.get("pages") if isinstance(query, Mapping) else None
    if not isinstance(pages, Mapping):
        return []
    candidates: list[CommonsCandidate] = []
    for page in sorted(
        (page for page in pages.values() if isinstance(page, Mapping)),
        key=lambda value: (int(value.get("pageid", 0)), str(value.get("title", ""))),
    ):
        title = page.get("title")
        imageinfo = page.get("imageinfo")
        info = imageinfo[0] if isinstance(imageinfo, list) and imageinfo else None
        if not isinstance(title, str) or not isinstance(info, Mapping):
            continue
        license_name = _metadata_value(
            info.get("extmetadata", {})
            if isinstance(info.get("extmetadata"), Mapping)
            else {},
            "LicenseShortName",
        )
        license_status = normalize_license_status(license_name)
        image_url = info.get("thumburl") or info.get("url")
        source_url = info.get("descriptionurl") or info.get("url")
        if (
            license_status is None
            or not isinstance(image_url, str)
            or not isinstance(source_url, str)
        ):
            continue
        candidates.append(
            CommonsCandidate(
                title=title,
                image_url=image_url,
                source_url=source_url,
                license_name=license_name,
                license_status=license_status,
                artist=_metadata_value(
                    info.get("extmetadata", {})
                    if isinstance(info.get("extmetadata"), Mapping)
                    else {},
                    "Artist",
                ),
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def fetch_json(params: Mapping[str, object], *, endpoint: str = COMMONS_API) -> dict:
    """Fetch JSON from Commons with a descriptive user agent."""
    url = f"{endpoint}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": COMMONS_USER_AGENT})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed Commons endpoint
        return json.loads(response.read().decode("utf-8"))


def query_commons(
    query: str,
    *,
    limit: int,
    fetch: Callable[[Mapping[str, object]], dict] = fetch_json,
) -> list[CommonsCandidate]:
    """Search Commons namespace 6 and retain only reusable image licenses."""
    payload = fetch(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": max(1, limit),
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "iiurlwidth": 1024,
            "format": "json",
        }
    )
    return parse_commons_candidates(payload, limit=limit)


def fetch_image(url: str) -> bytes:
    """Download one Commons thumbnail."""
    request = Request(url, headers={"User-Agent": COMMONS_USER_AGENT})
    with urlopen(request, timeout=30) as response:  # noqa: S310 - URL came from Commons API
        return response.read()


def provenance_record(relative_path: str, candidate: CommonsCandidate) -> dict[str, str]:
    """Build a record that can later satisfy the candidate index gate."""
    return {
        "path": relative_path,
        "source_url": candidate.source_url,
        "license_status": candidate.license_status,
        "license_name": candidate.license_name,
        "source_title": candidate.title,
        "artist": candidate.artist,
    }


def is_candidate_title_relevant(candidate: CommonsCandidate, dish_name: str) -> bool:
    """Fail closed when Commons search returns an unrelated title.

    Commons search is broad and can return visually unrelated files after the
    first few results.  Requiring the first two Vietnamese menu tokens in the
    file title prevents a high ``search_limit`` from filling a class with
    Big-Mac, dessert, or other accidental results.  The image still needs
    human visual review after this lexical filter.
    """
    required = set(accent_tokens(dish_name)[:2])
    title_tokens = set(accent_tokens(candidate.title))
    return bool(required) and required <= title_tokens


def _append_provenance(
    output_root: Path,
    accepted: list[Path],
    saved_paths: list[Path],
    metadata: Mapping[str, CommonsCandidate],
) -> None:
    if len(accepted) != len(saved_paths):
        raise RuntimeError("Không map được Commons provenance với ảnh đã lưu")
    records = []
    for source, target in zip(accepted, saved_paths, strict=True):
        candidate = metadata[source.name]
        records.append(
            provenance_record(target.relative_to(output_root).as_posix(), candidate)
            | {"downloaded_at": datetime.now(UTC).isoformat()}
        )
    if not records:
        return
    with (output_root / PROVENANCE_FILENAME).open("a", encoding="utf-8") as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def _selected_classes(raw: str | None) -> dict[str, str]:
    if not raw:
        return dict(TARGET_CLASSES)
    slugs = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = sorted(slugs - TARGET_CLASSES.keys())
    if unknown:
        raise ValueError(f"Class không hỗ trợ: {', '.join(unknown)}")
    return {slug: TARGET_CLASSES[slug] for slug in sorted(slugs)}


def run(
    *,
    per_class: int = 10,
    search_limit: int = 50,
    sleep_seconds: float = 1.0,
    candidate_root: Path = CANDIDATE_DIR,
    requested_classes: str | None = None,
    query: Callable[..., list[CommonsCandidate]] = query_commons,
    download: Callable[[str], bytes] = fetch_image,
) -> dict[str, int]:
    """Download licensed Commons candidates without promoting or indexing."""
    if per_class < 1 or search_limit < per_class or sleep_seconds < 0:
        raise ValueError("per-class/search-limit/sleep không hợp lệ")
    candidate_root.mkdir(parents=True, exist_ok=True)
    selected = _selected_classes(requested_classes)
    blocked = collect_blocked_hashes(
        (TRAIN_DIR, VAL_DIR, TEST_DIR, GOLDEN_DIR, REFERENCES_DIR, candidate_root)
    )
    counts: dict[str, int] = {}
    for index, (slug, dish_name) in enumerate(selected.items(), start=1):
        candidates = [
            candidate
            for candidate in query(dish_name, limit=search_limit)
            if is_candidate_title_relevant(candidate, dish_name)
        ]
        with tempfile.TemporaryDirectory(prefix=f"commons_{slug}_") as temp:
            staging = Path(temp)
            metadata: dict[str, CommonsCandidate] = {}
            for candidate_index, candidate in enumerate(candidates):
                filename = f"commons_{candidate_index:04d}.jpg"
                try:
                    data = download(candidate.image_url)
                    path = staging / filename
                    path.write_bytes(data)
                    metadata[filename] = candidate
                except (OSError, ValueError):
                    continue
            result = select_survivors(
                staging,
                blocked,
                per_class=per_class,
                max_distance=6,
            )
            class_dir = candidate_root / slug
            before = set(class_dir.glob("*") if class_dir.exists() else ())
            saved = save_survivors(result.accepted, class_dir, f"{slug}_commons")
            saved_paths = sorted(
                path for path in class_dir.iterdir() if path.is_file() and path not in before
            )
            _append_provenance(candidate_root, result.accepted, saved_paths, metadata)
            blocked.extend(hash_directory_images(class_dir))
            counts[slug] = saved
        print(
            f"[{index}/{len(selected)}] {dish_name}: Commons +{saved}/"
            f"{per_class} (trùng {result.rejected_duplicate}, lỗi {result.rejected_invalid})"
        )
        if index < len(selected) and sleep_seconds:
            time.sleep(sleep_seconds)
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl open-license Commons candidates")
    parser.add_argument("--per-class", type=int, default=10)
    parser.add_argument("--search-limit", type=int, default=50)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--classes", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    counts = run(
        per_class=args.per_class,
        search_limit=args.search_limit,
        sleep_seconds=args.sleep,
        requested_classes=args.classes,
    )
    print(json.dumps(counts, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
