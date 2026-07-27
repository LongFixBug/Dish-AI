"""End-to-end recognition eval cho POST /api/v1/analyze (Phase 0).

Đo top-1 accuracy của pipeline nhận diện (CV prior + Qdrant shortlist +
Vision) trên bộ ảnh có nhãn theo thư mục:

    data/images/golden/<class_slug>/*.jpg   (class_slug = ground truth)

Ground truth: data/eval/class_names.json (slug → tên hiển thị có dấu) và
data/eval/dish_aliases.json (slug → các tên chấp nhận thêm). Một prediction
đúng khi tên món chính (sau normalize bỏ dấu) trùng tên hiển thị hoặc alias.

Script độc lập — cần API chạy sẵn (uvicorn backend.main:app). Auth Bearer:
truyền --token, hoặc env FOODAI_EVAL_TOKEN, hoặc script tự mint token từ
backend settings local (chỉ hợp lệ khi server dùng cùng .env).

Usage:
    python -m ml.evaluation.recognition_eval --images-dir data/images/golden
"""

import argparse
import asyncio
import json
import os
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Chạy thẳng ``python ml/evaluation/recognition_eval.py`` (không qua -m) vẫn
# phải import được ``backend.*`` lúc tự mint token → thêm repo root vào path.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
CLASS_NAMES_PATH = PROJECT_ROOT / "data" / "eval" / "class_names.json"
ALIASES_PATH = PROJECT_ROOT / "data" / "eval" / "dish_aliases.json"
DEFAULT_IMAGES_DIR = PROJECT_ROOT / "data" / "images" / "golden"

ANALYZE_ROUTE = "/api/v1/analyze"
VISION_ONLY_ROUTE = "/api/v1/analyze/vision-only"
DEFAULT_ENDPOINT = "http://localhost:8000"
TOKEN_ENV_VAR = "FOODAI_EVAL_TOKEN"
NO_PREDICTION = "no_prediction"

IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


# ─── Pure helpers: normalize + ground truth ──────────────────────────────────


def normalize_name(name: str) -> str:
    """Casefold + bỏ dấu (NFD, drop combining) + đ→d + gộp khoảng trắng.

    Backend chỉ có normalize dạng SQL (``vn_norm``) hoặc token-set nội bộ,
    không import được — nên tự cài lại đúng cùng quy tắc ở đây.
    """
    decomposed = unicodedata.normalize("NFD", name.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.replace("đ", "d").split())


@dataclass(frozen=True)
class ClassTruth:
    """Một lớp ground truth: tên hiển thị + tập tên chấp nhận (đã normalize)."""

    slug: str
    display_name: str
    acceptable: frozenset[str]


def load_ground_truth(
    class_names_path: Path = CLASS_NAMES_PATH,
    aliases_path: Path = ALIASES_PATH,
) -> dict[str, ClassTruth]:
    """Đọc class_names.json + dish_aliases.json → map slug → ClassTruth."""
    class_names = json.loads(class_names_path.read_text(encoding="utf-8"))
    aliases: dict[str, list[str]] = (
        json.loads(aliases_path.read_text(encoding="utf-8"))
        if aliases_path.exists()
        else {}
    )
    return {
        slug: ClassTruth(
            slug=slug,
            display_name=display,
            acceptable=frozenset(
                normalize_name(n) for n in (display, *aliases.get(slug, []))
            ),
        )
        for slug, display in class_names.items()
    }


def is_correct(predicted: str | None, truth: ClassTruth) -> bool:
    """Prediction đúng khi tên normalize trùng display name hoặc alias."""
    return predicted is not None and normalize_name(predicted) in truth.acceptable


def collect_images(
    images_dir: Path, limit_per_class: int = 0
) -> list[tuple[str, Path]]:
    """Gom (class_slug, image_path) từ layout <class_slug>/*.jpg, sort ổn định."""
    if not images_dir.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục ảnh: {images_dir}")
    pairs: list[tuple[str, Path]] = []
    for class_dir in sorted(p for p in images_dir.iterdir() if p.is_dir()):
        files = sorted(
            f
            for f in class_dir.iterdir()
            if f.is_file() and f.suffix.lower() in IMAGE_CONTENT_TYPES
        )
        if limit_per_class > 0:
            files = files[:limit_per_class]
        pairs.extend((class_dir.name, f) for f in files)
    return pairs


# ─── Pure helpers: prediction + metrics ──────────────────────────────────────


@dataclass(frozen=True)
class Prediction:
    """Món chính rút từ AnalyzeResponse (dish đầu tiên không phải is_side)."""

    dish_name: str | None
    vision_dish_name: str | None
    found_in_db: bool


def extract_prediction(payload: Mapping) -> Prediction:
    """Rút món chính từ response /analyze; dishes rỗng → no_prediction."""
    for dish in payload.get("dishes") or []:
        if not isinstance(dish, Mapping) or dish.get("is_side"):
            continue
        name = dish.get("dish_name")
        if name:
            return Prediction(
                dish_name=name,
                vision_dish_name=dish.get("vision_dish_name"),
                found_in_db=bool(dish.get("found_in_db")),
            )
    return Prediction(dish_name=None, vision_dish_name=None, found_in_db=False)


@dataclass(frozen=True)
class ImageResult:
    """Kết quả eval 1 ảnh. error = lỗi request; detail = message từ API."""

    image: str
    truth_slug: str
    truth_name: str
    predicted: str | None
    vision_dish_name: str | None
    found_in_db: bool
    correct: bool
    error: str | None = None
    detail: str | None = None


def _per_class_metrics(results: Sequence[ImageResult]) -> dict[str, dict]:
    """Accuracy theo từng class slug (recall của class đó)."""
    per_class: dict[str, dict] = {}
    for slug in sorted({r.truth_slug for r in results}):
        rows = [r for r in results if r.truth_slug == slug]
        correct = sum(r.correct for r in rows)
        per_class[slug] = {
            "total": len(rows),
            "correct": correct,
            "accuracy": round(correct / len(rows), 3),
        }
    return per_class


def compute_metrics(results: Sequence[ImageResult]) -> dict:
    """Tổng hợp accuracy / macro recall / no_prediction / lỗi request."""
    total = len(results)
    correct = sum(r.correct for r in results)
    request_errors = sum(1 for r in results if r.error is not None)
    no_prediction = sum(
        1 for r in results if r.predicted is None and r.error is None
    )
    per_class = _per_class_metrics(results)
    accuracies = [row["accuracy"] for row in per_class.values()]

    def _rate(count: int) -> float:
        return round(count / total, 3) if total else 0.0

    return {
        "total_images": total,
        "correct": correct,
        "top1_accuracy": _rate(correct),
        "macro_recall": round(sum(accuracies) / len(accuracies), 3)
        if accuracies
        else 0.0,
        "no_prediction": no_prediction,
        "no_prediction_rate": _rate(no_prediction),
        "request_errors": request_errors,
        "found_in_db": sum(1 for r in results if r.found_in_db),
        "per_class": per_class,
    }


def confusion_counts(results: Sequence[ImageResult]) -> dict[str, dict[str, int]]:
    """Đếm truth → predicted (predicted normalize hiển thị nguyên văn)."""
    confusion: dict[str, dict[str, int]] = {}
    for r in results:
        predicted = r.predicted if r.predicted is not None else NO_PREDICTION
        row = confusion.setdefault(r.truth_name, {})
        row[predicted] = row.get(predicted, 0) + 1
    return confusion


# ─── HTTP calls ──────────────────────────────────────────────────────────────


MAX_RATE_LIMIT_RETRIES = 8
DEFAULT_RETRY_AFTER_SECONDS = 6.0


async def analyze_image(
    client: httpx.AsyncClient, url: str, image_path: Path
) -> dict:
    """POST 1 ảnh multipart (field ``file``) → JSON AnalyzeResponse.

    API dev giới hạn 10 request/phút cho /analyze; gặp 429 thì chờ đúng
    ``Retry-After`` rồi thử lại thay vì ghi nhận lỗi (harness tự pace).
    """
    content = await asyncio.to_thread(image_path.read_bytes)
    content_type = IMAGE_CONTENT_TYPES.get(image_path.suffix.lower(), "image/jpeg")
    files = {"file": (image_path.name, content, content_type)}
    for _attempt in range(MAX_RATE_LIMIT_RETRIES):
        response = await client.post(url, files=files)
        if response.status_code != 429:
            break
        retry_after = _retry_after_seconds(response)
        await asyncio.sleep(retry_after)
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Response không phải JSON object")
    return payload


def _retry_after_seconds(response: httpx.Response) -> float:
    """PURE-ish: đọc header Retry-After, hỏng/thiếu thì dùng mặc định."""
    raw = response.headers.get("Retry-After", "")
    try:
        return min(120.0, max(1.0, float(raw)))
    except ValueError:
        return DEFAULT_RETRY_AFTER_SECONDS


async def _evaluate_one(
    client: httpx.AsyncClient,
    url: str,
    slug: str,
    path: Path,
    truths: Mapping[str, ClassTruth],
    semaphore: asyncio.Semaphore,
) -> ImageResult:
    """Eval 1 ảnh; mọi lỗi request được ghi nhận, không làm sập cả run."""
    truth = truths.get(slug)
    truth_name = truth.display_name if truth else slug
    try:
        async with semaphore:
            payload = await analyze_image(client, url, path)
    except Exception as exc:  # noqa: BLE001 — lỗi từng ảnh không dừng run
        return ImageResult(
            image=str(path), truth_slug=slug, truth_name=truth_name,
            predicted=None, vision_dish_name=None, found_in_db=False,
            correct=False, error=f"{type(exc).__name__}: {exc}",
        )
    prediction = extract_prediction(payload)
    return ImageResult(
        image=str(path),
        truth_slug=slug,
        truth_name=truth_name,
        predicted=prediction.dish_name,
        vision_dish_name=prediction.vision_dish_name,
        found_in_db=prediction.found_in_db,
        correct=truth is not None and is_correct(prediction.dish_name, truth),
        detail=payload.get("error") if prediction.dish_name is None else None,
    )


async def run_eval(
    pairs: Sequence[tuple[str, Path]],
    truths: Mapping[str, ClassTruth],
    url: str,
    *,
    concurrency: int = 2,
    timeout: float = 60.0,
    token: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[ImageResult]:
    """Chạy eval toàn bộ ảnh; ``client`` inject được để test offline."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    owns_client = client is None
    active = client or httpx.AsyncClient(timeout=timeout, headers=headers)
    semaphore = asyncio.Semaphore(max(1, concurrency))
    try:
        return list(
            await asyncio.gather(
                *(
                    _evaluate_one(active, url, slug, path, truths, semaphore)
                    for slug, path in pairs
                )
            )
        )
    finally:
        if owns_client:
            await active.aclose()


# ─── Report ──────────────────────────────────────────────────────────────────


def build_report(
    results: Sequence[ImageResult], endpoint: str, images_dir: str, timestamp: str
) -> dict:
    """Gom kết quả thành report JSON-serializable."""
    return {
        "timestamp": timestamp,
        "suite": "recognition_eval",
        "endpoint": endpoint,
        "images_dir": images_dir,
        "metrics": compute_metrics(results),
        "confusion": confusion_counts(results),
        "errors": [
            {"image": r.image, "truth": r.truth_name, "predicted": r.predicted}
            for r in results
            if not r.correct
        ],
        "per_image": [asdict(r) for r in results],
    }


def render_markdown(report: dict) -> str:
    """Bảng tóm tắt gọn kiểu rag_eval — summary + per-class + lỗi."""
    metrics = report["metrics"]
    lines = [
        f"# Recognition Eval Report — {report['timestamp']}",
        "",
        f"**Endpoint**: {report['endpoint']}",
        f"**Images**: {metrics['total_images']} from `{report['images_dir']}`",
        "",
        "## Summary",
        "",
        f"- **Top-1 accuracy**: {metrics['top1_accuracy']}",
        f"- Macro recall: {metrics['macro_recall']}",
        f"- No-prediction rate: {metrics['no_prediction_rate']}"
        f" ({metrics['no_prediction']})",
        f"- Request errors: {metrics['request_errors']}",
        f"- Found in DB: {metrics['found_in_db']}/{metrics['total_images']}",
        "",
        "## Per-class",
        "",
        "| Class | Total | Correct | Accuracy |",
        "|-------|-------|---------|----------|",
    ]
    for slug, row in metrics["per_class"].items():
        lines.append(
            f"| {slug} | {row['total']} | {row['correct']} | {row['accuracy']} |"
        )
    lines += ["", "## Errors", "", "| Image | Truth | Predicted |", "|---|---|---|"]
    for err in report["errors"]:
        predicted = err["predicted"] or NO_PREDICTION
        lines.append(
            f"| {Path(err['image']).name} | {err['truth']} | {predicted} |"
        )
    return "\n".join(lines) + "\n"


def save_report(report: dict, timestamp: str) -> tuple[Path, Path]:
    """Lưu JSON + MD vào ml/evaluation/reports/. Trả (json_path, md_path)."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"recognition_eval_{timestamp}.json"
    md_path = REPORTS_DIR / f"recognition_eval_{timestamp}.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path


# ─── CLI ─────────────────────────────────────────────────────────────────────


def resolve_token(explicit: str | None) -> str | None:
    """--token → env FOODAI_EVAL_TOKEN → mint local từ backend settings."""
    if explicit:
        return explicit
    from_env = os.environ.get(TOKEN_ENV_VAR)
    if from_env:
        return from_env
    try:
        from backend.config import settings
        from backend.services.auth import TokenManager

        token, _ = TokenManager.from_settings(settings).create_access_token(
            user_id="recognition-eval", role="user"
        )
        return token
    except Exception:  # noqa: BLE001 — thiếu backend/env thì chạy không auth
        return None


def build_url(endpoint: str, vision_only: bool) -> str:
    """Ghép route analyze; endpoint chứa sẵn /api/ thì dùng nguyên văn."""
    if "/api/" in endpoint:
        return endpoint
    route = VISION_ONLY_ROUTE if vision_only else ANALYZE_ROUTE
    return endpoint.rstrip("/") + route


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="End-to-end recognition eval")
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--vision-only", action="store_true")
    parser.add_argument("--limit-per-class", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--token", default=None)
    return parser.parse_args(argv)


async def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    truths = load_ground_truth()
    pairs = collect_images(args.images_dir, args.limit_per_class)
    if not pairs:
        raise SystemExit(f"Không có ảnh nào trong {args.images_dir}")
    url = build_url(args.endpoint, args.vision_only)
    token = resolve_token(args.token)
    if token is None:
        print("⚠️  Không có token — request có thể bị 401 (dùng --token).")

    print(f"🔍 Recognition eval — {len(pairs)} ảnh → {url}")
    results = await run_eval(
        pairs, truths, url,
        concurrency=args.concurrency, timeout=args.timeout, token=token,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = build_report(results, url, str(args.images_dir), timestamp)
    print(render_markdown(report))
    json_path, md_path = save_report(report, timestamp)
    print(f"💾 Report saved:\n   JSON: {json_path}\n   MD:   {md_path}")


if __name__ == "__main__":
    asyncio.run(main())
