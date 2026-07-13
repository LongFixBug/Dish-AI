"""Analyze endpoint — upload ảnh món ăn → nutrition (2-tier CV + vision).

Giai đoạn A wire-up:
  ảnh → CV local (conf≥0.6) → lookup_dish → nutrition         (source=cv_local)
  ảnh → CV conf<0.6 / lookup miss / CV disabled → vision      (source=cv_local_not_found_vision | vision)
       → ingredients[{name,gram}] → map name→id → compute_nutrition → nutrition
"""

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.postgres import get_session
from backend.services.dishes import compute_nutrition, lookup_dish
from backend.services.ingredients import search_ingredients
from ml.inference.cv import cv_model
from ml.inference.vision import VisionError, identify_dish
from schemas.analyze import AnalyzeIngredient, AnalyzeResponse
from schemas.dish import RecipeItemInput

router = APIRouter(prefix="/api/v1", tags=["analyze"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def _resolve_ingredient_id(session: AsyncSession, name: str) -> str | None:
    """Map tên nguyên liệu (vision trả, có dấu) → ingredient_id (UUID trong DB).

    Dùng search_ingredients (ILIKE + vn_norm, lọc ingredient/fruit).
    vector_fallback=False — map name→id cần match tên thật, vector "gần nghĩa"
    gây false positive (vd móc Kiwifruit cho query vô nghĩa).
    Miss → None (analyze đưa vào missing_ingredients).
    """
    hits = await search_ingredients(session, name, limit=1, vector_fallback=False)
    return str(hits[0].id) if hits else None


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_food(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AnalyzeResponse:
    """Upload ảnh món ăn → nhận diện + phân tích dinh dưỡng.

    2-tier: CV local trước (rẻ, local), fallback Qwen3.7 vision cho món lạ/conf thấp.
    """
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {file.content_type}. Chỉ chấp nhận JPEG, PNG, WebP.",
        )

    # Save temp file
    temp_path = UPLOAD_DIR / f"upload_{file.filename}"
    content = await file.read()
    temp_path.write_bytes(content)

    try:
        # ─── Tier 1: CV local ────────────────────────────────────────────
        cv_result = cv_model.predict(temp_path)
        cv_conf = cv_result["confidence"]
        cv_dish = cv_result["dish_name"]

        if cv_model.is_loaded and cv_conf >= 0.6 and cv_dish is not None:
            lookup = await lookup_dish(session, cv_dish)
            if lookup["exists"]:
                return AnalyzeResponse(
                    dish_name=lookup["dish_name"],
                    source="cv_local",
                    cv_confidence=cv_conf,
                    nutrition=lookup["nutrition"],
                )
            # CV conf cao nhưng lookup miss → fallback vision
            # (source đánh dấu cv_local_not_found_vision bên dưới)

        # ─── Tier 2: Vision fallback ─────────────────────────────────────
        try:
            vision = await identify_dish(temp_path)
        except VisionError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e

        # Map ingredients name → ingredient_id, track missing
        items: list[RecipeItemInput] = []
        missing_names: list[str] = []
        for ing in vision["ingredients"]:
            ing_id = await _resolve_ingredient_id(session, ing["name"])
            if ing_id is not None:
                items.append(
                    RecipeItemInput(
                        ingredient_id=ing_id, amount=float(ing["gram"]), unit="g"
                    )
                )
            else:
                missing_names.append(ing["name"])

        # Compute nutrition (items có id). Nếu items rỗng → compute vẫn trả totals=0.
        totals, _assumed = await compute_nutrition(session, vision["dish_name"], items)
        # GAP FIX: compute_nutrition không truyền missing_ingredients → tự set
        # + recalc confidence_score bao gồm missing (found / (found + missing)).
        found_count = len(items)
        total_count = found_count + len(missing_names)
        confidence = found_count / max(total_count, 1)
        totals = totals.model_copy(
            update={
                "missing_ingredients": missing_names,
                "confidence_score": round(confidence, 2),
            }
        )

        # source: CV conf cao nhưng lookup miss → cv_local_not_found_vision;
        # còn lại (conf<0.6, CV disabled, dish None) → vision
        used_cv_high = cv_model.is_loaded and cv_conf >= 0.6 and cv_dish is not None
        source = "cv_local_not_found_vision" if used_cv_high else "vision"

        return AnalyzeResponse(
            dish_name=vision["dish_name"],
            source=source,
            cv_confidence=cv_conf if cv_model.is_loaded else None,
            nutrition=totals,
            ingredients=[
                AnalyzeIngredient(name=i["name"], grams=float(i["gram"]))
                for i in vision["ingredients"]
            ],
            missing_ingredients=missing_names,
        )
    finally:
        # Clean up temp file
        if temp_path.exists():
            temp_path.unlink()
