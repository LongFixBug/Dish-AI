"""Contract for the manually curated reference-candidate class folders."""

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

REQUESTED_CANDIDATE_CLASSES = {
    "tra_sua": "Trà sữa",
    "banh_kem": "Bánh kem",
    "sau_rieng": "Sầu riêng",
    "tra_trai_cay": "Trà trái cây",
    "xuc_xich_nuong": "Xúc xích nướng",
    "uc_ga": "Ức gà",
    "banh_mi_khong": "Bánh mì không",
    "ga_ran": "Gà rán",
    "khoai_luoc": "Khoai luộc",
    "com_trang": "Cơm trắng",
    "xoi_man": "Xôi mặn",
    "pizza": "Pizza",
    "hamburger": "Hamburger",
    "coca_cola": "Coca-Cola",
    "sua_milo": "Sữa Milo",
    "chocolate": "Chocolate",
    "trung_luoc": "Trứng luộc",
    "trung_chien": "Trứng chiên",
}



def test_requested_candidate_classes_have_display_names_and_folders() -> None:
    class_names_path = ROOT / "data/eval/class_names.json"
    class_names = json.loads(class_names_path.read_text(encoding="utf-8"))
    candidate_root = ROOT / "data/images/references_candidate"

    if not candidate_root.is_dir():
        pytest.skip("Reference-candidate images are local data and intentionally excluded from Git.")

    for slug, display_name in REQUESTED_CANDIDATE_CLASSES.items():
        assert class_names[slug] == display_name
        assert (candidate_root / slug).is_dir()
