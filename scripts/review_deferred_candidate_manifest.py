"""Apply a second, conservative visual review to the deferred crawl queue.

This artifact is intentionally allowlist-based.  A new crawl image is never
promoted merely because it exists in a class folder; only paths explicitly
checked as a clear example are moved to ``approved_paths``.  Everything else
stays deferred for the project owner to inspect.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data/eval/reference_candidate_demo_reviewed.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/eval/reference_candidate_demo_reviewed_v2.json"
DEFAULT_CV_OUTPUT = PROJECT_ROOT / "data/eval/reference_candidate_demo_cv_reviewed.json"

CV_COMPATIBLE_CLASSES = frozenset(
    {
        "banh_can",
        "banh_canh",
        "banh_chung",
        "banh_khot",
        "banh_tet",
        "banh_trang_nuong",
        "banh_xeo",
        "bun_bo_hue",
        "hu_tieu",
        "pho_bo",
    }
)

# These are the only deferred paths promoted by this pass.  The list is based
# on a visual inspection of the 332-image queue on 2026-08-06.  Recipe cards,
# ingredient photos, shop signs, collages, packaging and ambiguous lookalikes
# remain deferred.
DEFERRED_PROMOTIONS = frozenset(
    {
        "banh_khot/banh_khot_31.jpg",
        "banh_khot/banh_khot_32.jpg",
        "banh_khot/banh_khot_34.jpg",
        "banh_tet/banh_tet_11.jpg",
        "banh_tet/banh_tet_15.jpg",
        "banh_tet/banh_tet_16.jpg",
        "banh_tet/banh_tet_33.jpg",
        "banh_trang_nuong/banh_trang_nuong_27.jpg",
        "banh_trang_nuong/banh_trang_nuong_31.jpg",
        "banh_xeo/banh_xeo_1.jpg",
        "chocolate/chocolate_19.jpg",
        "ga_ran/ga_ran_18.jpg",
        "ga_ran/ga_ran_28.jpg",
        "hamburger/hamburger_48.jpg",
        "pho_bo/462330833_18466521532018389_6520092656924746845_n.jpg",
        "pho_bo/625345927_18110828233660184_6560664182158143813_n.jpg",
        "pho_bo/730125195_17909367336430505_9160933955397957050_n.jpg",
        "pho_bo/747409068_17940267258256097_8463814875903451502_n.jpg",
        "pho_bo/747573070_17940267246256097_7371627522357461352_n.jpg",
        "pho_bo/756610100_17976447996119855_8478735266994271726_n.jpg",
        "pho_bo/757331365_17988481632111594_5603650536268943341_n.jpg",
        "pho_bo/758016679_17978837481114538_4421965989495029524_n.jpg",
        "pho_bo/764365322_17913392679430666_6999180789664562527_n.jpg",
        "pho_bo/764720007_28497089906549426_8373078004367641302_n.jpg",
        "pho_bo/765620430_17936725302303460_8961466964019262504_n.jpg",
        "pho_bo/765929367_37158460423797619_7572507541767863993_n.jpg",
        "pho_bo/767002319_2080598662667713_3847968462715262771_n.jpg",
        "pho_bo/Ảnh màn hình 2026-08-05 lúc 14.21.44.png",
        "pho_bo/Ảnh màn hình 2026-08-05 lúc 14.21.57.png",
        "pho_bo/Ảnh màn hình 2026-08-05 lúc 14.29.12.png",
        "pho_bo/Ảnh màn hình 2026-08-05 lúc 14.30.52.png",
        "pho_bo/Ảnh màn hình 2026-08-05 lúc 14.31.26.png",
        "pho_bo/Ảnh màn hình 2026-08-05 lúc 14.32.25.png",
        "pho_bo/Ảnh màn hình 2026-08-05 lúc 14.35.16.png",
        "pizza/pizza_23.jpg",
        "pizza/pizza_39.jpg",
        "sau_rieng/sau_rieng_43.jpg",
        "tra_trai_cay/tra_trai_cay_24.jpg",
        "tra_trai_cay/tra_trai_cay_31.jpg",
        "tra_trai_cay/tra_trai_cay_5.jpg",
        "trung_chien/trung_chien_15.jpg",
        "trung_chien/trung_chien_25.jpg",
        "trung_chien/trung_chien_31.jpg",
        "uc_ga/uc_ga_13.jpg",
        "uc_ga/uc_ga_20.jpg",
        "xoi_man/xoi_man_22.jpg",
        "xoi_man/xoi_man_26.jpg",
        "xoi_man/xoi_man_42.jpg",
        "xuc_xich_nuong/xuc_xich_nuong_17.jpg",
    }
)

DEFERRED_CLASS_NOTES = {
    "banh_can": "Giữ lại: phần lớn ảnh là tô bún/bánh canh, không thấy rõ bánh căn.",
    "banh_canh": "Giữ lại: nhiều tô nước dùng giống hủ tiếu/bún, chưa đủ chắc là bánh canh.",
    "banh_chung": "Giữ lại: nhiều ảnh quy trình, collage hoặc món khác; chưa phải ảnh món rõ.",
    "banh_mi_khong": "Giữ lại: phần lớn là bánh mì có nhân, không khớp lớp bánh mì không.",
    "coca_cola": "Giữ lại: chủ yếu là ảnh sự kiện/quảng cáo, không phải ảnh chai/lon rõ.",
    "ga_ran": "Giữ lại ảnh sống, nguyên liệu và công thức; chỉ promote 2 ảnh gà rán rõ.",
    "khoai_luoc": "Giữ lại: phần lớn là khoai chiên/khoai sấy, không phải khoai luộc.",
    "sua_milo": "Giữ lại: nhiều ảnh là đồ uống cacao/trà sữa, chưa xác nhận được Milo.",
    "trung_chien": "Giữ lại ảnh nguyên liệu/dụng cụ; chỉ promote vài ảnh trứng chiên rõ.",
    "trung_luoc": "Giữ lại: không có ảnh trứng luộc đủ rõ trong queue này.",
    "uc_ga": "Giữ lại ảnh mì/thịt khác; chỉ promote 2 ảnh ức gà rõ.",
}


def _class_slug(path: str) -> str:
    return path.split("/", 1)[0]


def _sorted_paths(paths: set[str] | list[str]) -> list[str]:
    return sorted(paths, key=lambda value: (value.split("/", 1)[0], value))


def _summary(approved_paths: list[str], deferred_paths: list[str]) -> dict[str, object]:
    return {
        "candidate_images": len(approved_paths) + len(deferred_paths),
        "approved_images": len(approved_paths),
        "deferred_images": len(deferred_paths),
        "approved_by_class": dict(sorted(Counter(map(_class_slug, approved_paths)).items())),
        "deferred_by_class": dict(sorted(Counter(map(_class_slug, deferred_paths)).items())),
    }


def build_reviewed_manifest(
    base_manifest: dict[str, object],
    *,
    promoted_paths: set[str],
    reviewed_at: str,
) -> dict[str, object]:
    """Return a deterministic manifest after reviewing the old deferred queue."""
    base_deferred = {
        path for path in base_manifest.get("deferred_paths", []) if isinstance(path, str)
    }
    invalid = promoted_paths - base_deferred
    if invalid:
        raise ValueError(f"Path không nằm trong deferred queue: {sorted(invalid)}")

    approved = {
        path for path in base_manifest.get("approved_paths", []) if isinstance(path, str)
    }
    approved |= promoted_paths
    deferred = base_deferred - promoted_paths
    result = dict(base_manifest)
    result.update(
        {
            "review_method": "codex_visual_review_v2",
            "reviewed_at": reviewed_at,
            "approved_paths": _sorted_paths(approved),
            "reviewed_paths": _sorted_paths(approved),
            "deferred_paths": _sorted_paths(deferred),
            "reviewed_deferred_paths": _sorted_paths(base_deferred),
            "deferred_review_promotions": _sorted_paths(promoted_paths),
            "deferred_review_notes": DEFERRED_CLASS_NOTES,
            "summary": _summary(_sorted_paths(approved), _sorted_paths(deferred)),
        }
    )
    return result


def filter_manifest_to_classes(
    manifest: dict[str, object],
    classes: set[str] | frozenset[str],
) -> dict[str, object]:
    """Keep only classes the current CV checkpoint can represent."""
    result = dict(manifest)
    approved = [
        path
        for path in manifest.get("approved_paths", [])
        if isinstance(path, str) and _class_slug(path) in classes
    ]
    deferred = [
        path
        for path in manifest.get("deferred_paths", [])
        if isinstance(path, str) and _class_slug(path) in classes
    ]
    result["approved_paths"] = _sorted_paths(approved)
    result["reviewed_paths"] = _sorted_paths(approved)
    result["deferred_paths"] = _sorted_paths(deferred)
    result["summary"] = _summary(result["approved_paths"], result["deferred_paths"])
    result["staged_classes"] = sorted(
        {
            _class_slug(path)
            for path in manifest.get("approved_paths", [])
            if isinstance(path, str) and _class_slug(path) not in classes
        }
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Review deferred image candidates")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cv-output", type=Path, default=DEFAULT_CV_OUTPUT)
    args = parser.parse_args()

    base = json.loads(args.input.read_text(encoding="utf-8"))
    manifest = build_reviewed_manifest(
        base,
        promoted_paths=set(DEFERRED_PROMOTIONS),
        reviewed_at=date.today().isoformat(),
    )
    cv_manifest = filter_manifest_to_classes(manifest, CV_COMPATIBLE_CLASSES)
    for output, payload in ((args.output, manifest), (args.cv_output, cv_manifest)):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {output}")
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
