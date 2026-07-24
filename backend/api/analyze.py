"""Analyze endpoint — upload ảnh món ăn → nutrition (dish-level, không nguyên liệu).

Giai đoạn A wire-up (phiên bản Jul 23):
  ảnh → CV local → Vision → dishes[{dish_name, gram, is_side, total_*}]
       → mỗi item lookup vn_dishes (+ Qdrant fallback)
       → nếu miss + is_side → lookup vn_ingredients (đồ uống/món kèm)
       → match: bỏ nutrition Vision, scale gram_vision × per_g_db
       → miss: dùng nutrition Vision + auto-add vào vn_dishes
"""

import logging
import uuid
from pathlib import Path
import httpx

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.postgres import get_session
from backend.services.dishes import (
    _has_nutrition,
    _has_weight,
    _vn_dish_to_per_gram,
    _vn_ingredient_to_per_gram,
    auto_add_dish,
    auto_update_grams,
    lookup_dish,
    lookup_dish_exact,
    lookup_ingredient_text,
)
from ml.inference.cv import cv_model
from ml.inference.vision import VisionError, identify_dish
from schemas.analyze import AnalyzeDish, AnalyzeResponse
from schemas.nutrition import (
    NutritionPerIngredient,
    calculate_item_nutrition,
    calculate_totals,
    create_item_nutrition_from_vision,
)

# ─── Constants ─────────────────────────────────────────────────────────────

CV_CONFIDENCE_THRESHOLD = 0.85       # CV phải rất tự tin (≥85%) mới bỏ qua Vision
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB — chặn upload ảnh quá lớn gây OOM


def _safe_filename(filename: str) -> str:
    """Chặn path traversal: chỉ lấy tên file, thay ký tự không an toàn."""
    safe = Path(filename).name
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in safe)
    return safe or "upload"


router = APIRouter(prefix="/api/v1", tags=["analyze"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("foodai")


def _is_cv_high_conf(cv_conf: float | None, cv_dish: str | None) -> bool:
    """CV có confidence cao không (dùng chung)."""
    return (
        cv_model.is_loaded
        and cv_conf is not None
        and cv_conf >= CV_CONFIDENCE_THRESHOLD
        and cv_dish is not None
    )


async def _resolve_dish_item(
    session: AsyncSession,
    dish_name: str,
    gram: float,
    is_side: bool,
) -> tuple[NutritionPerIngredient | None, str]:
    """Resolve 1 dish vision → NutritionPerIngredient.

    Tra vn_dishes trước → nếu miss + is_side → tra vn_ingredients → nếu vẫn miss → None.

    Returns:
        (nutrition_item | None, canonical_name). canonical_name là tên chuẩn DB
        khi match, nếu miss thì giữ tên Vision.
    """
    gram = max(0.0, float(gram))

    # ── Tier 1: vn_dishes ────────────────────────────────────────────────
    vn = (
        await lookup_dish_exact(session, dish_name)
        if is_side
        else await lookup_dish(session, dish_name)
    )
    resolved_name = vn.dish_name if vn is not None else dish_name
    if vn is not None:
        per_gram = _vn_dish_to_per_gram(vn)
        if _has_nutrition(vn) and _has_weight(vn):
            # DB có typical_grams → per_g thật → scale đúng gram Vision.
            return calculate_item_nutrition(vn.dish_name, gram, per_gram), vn.dish_name
        if _has_nutrition(vn):
            # DB có nutrition nhưng thiếu typical_grams → coi gram ảnh là 1 khẩu phần.
            await auto_update_grams(session, vn, gram)
            await session.commit()
            return NutritionPerIngredient(
                item_name=vn.dish_name,
                grams=gram,
                calories=round(vn.total_calories, 1),
                protein_g=round(vn.total_protein_g, 1),
                fat_g=round(vn.total_fat_g, 1),
                carbs_g=round(vn.total_carbs_g, 1),
                fiber_g=round(vn.total_fiber_g, 1),
                found_in_db=True,
            ), vn.dish_name
        # Chỉ có tên/gram từ lần Vision cũ, chưa có nutrition → dùng Vision mới.

    # ── Tier 2: vn_ingredients (chỉ khi is_side — đồ uống/món kèm) ───────
    if is_side:
        ing = await lookup_ingredient_text(session, dish_name)
        if ing is not None:
            per_gram = _vn_ingredient_to_per_gram(ing)
            return (
                calculate_item_nutrition(ing.ingredient_name, gram, per_gram),
                ing.ingredient_name,
            )

    # ── Không có ở đâu cả → món mới (caller sẽ auto-add) ─────────────────
    return None, resolved_name


async def _analyze_vision_dishes(
    session: AsyncSession,
    vision_dishes: list[dict],
) -> tuple[
    list[NutritionPerIngredient],   # items đã tính
    list[AnalyzeDish],              # dishes response (với is_side)
    list[str],                       # món mới auto-added
    list[str],                       # missing items
]:
    """Xử lý list dishes Vision trả → nutrition từng món + auto-add món mới."""
    items: list[NutritionPerIngredient] = []
    response_dishes: list[AnalyzeDish] = []
    auto_added: list[str] = []
    missing: list[str] = []

    for d in vision_dishes:
        dish_name = d.get("dish_name")
        if not dish_name:
            continue
        gram = float(d.get("gram", 0) or 0)
        is_side = bool(d.get("is_side", False))
        item, resolved_name = await _resolve_dish_item(
            session, dish_name, gram, is_side
        )

        if item is not None:
            items.append(item)
            response_dishes.append(
                AnalyzeDish(
                    dish_name=resolved_name,
                    vision_dish_name=(dish_name if dish_name != resolved_name else None),
                    grams=gram,
                    is_side=is_side,
                    found_in_db=True,
                )
            )
            continue

        # Món mới → dùng toàn bộ nutrition Vision và lưu làm 1 khẩu phần chuẩn.
        vision_item = create_item_nutrition_from_vision(
            resolved_name,
            gram,
            total_calories=float(d.get("total_calories", 0) or 0),
            total_protein_g=float(d.get("total_protein_g", 0) or 0),
            total_fat_g=float(d.get("total_fat_g", 0) or 0),
            total_carbs_g=float(d.get("total_carbs_g", 0) or 0),
            total_fiber_g=float(d.get("total_fiber_g", 0) or 0),
        )
        response_dishes.append(
            AnalyzeDish(
                dish_name=resolved_name,
                vision_dish_name=(dish_name if dish_name != resolved_name else None),
                grams=gram,
                is_side=is_side,
                found_in_db=False,
            )
        )
        try:
            await auto_add_dish(
                session,
                resolved_name,
                gram if gram > 0 else None,
                nutrition=vision_item,
            )
            await session.commit()
            auto_added.append(resolved_name)
            items.append(vision_item)
            logger.info(
                "auto-add '%s' gram=%s với nutrition Vision → vn_dishes",
                resolved_name,
                gram,
            )
        except Exception as e:
            # Trùng tên (race) hoặc lỗi khác → rollback + báo missing
            await session.rollback()
            logger.warning("auto-add '%s' fail: %s", dish_name, e)
            missing.append(resolved_name)
            items.append(vision_item)

    return items, response_dishes, auto_added, missing


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_food(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AnalyzeResponse:
    """Upload ảnh món ăn → nhận diện + phân tích dinh dưỡng (dish-level)."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {file.content_type}. Chỉ JPEG, PNG, WebP.",
        )

    safe_name = _safe_filename(file.filename or "upload")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Ảnh quá lớn (>{MAX_UPLOAD_BYTES // (1024*1024)}MB).",
        )
    temp_path = UPLOAD_DIR / f"upload_{uuid.uuid4().hex[:12]}_{safe_name}"
    temp_path.write_bytes(content)

    try:
        # ─── Tier 1: CV local (giữ — user sẽ train sau) ─────────────────
        cv_conf: float | None = None
        cv_dish: str | None = None
        if cv_model.is_loaded:
            cv_result = cv_model.predict(temp_path)
            cv_conf = cv_result["confidence"]
            cv_dish = cv_result["dish_name"]

        # ─── Tier 2: Vision (luôn chạy để lấy gram thực tế từ ảnh) ──────
        try:
            vision = await identify_dish(temp_path)
        except VisionError as e:
            cv_high = _is_cv_high_conf(cv_conf, cv_dish)
            return AnalyzeResponse(
                dish_name=cv_dish if cv_model.is_loaded and cv_dish else None,
                source="cv_local_not_found_vision" if cv_high else "vision",
                cv_confidence=cv_conf if cv_model.is_loaded else None,
                error=f"Vision cloud offline: {str(e)[:200]}",
            )
        except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
            cv_high = _is_cv_high_conf(cv_conf, cv_dish)
            return AnalyzeResponse(
                dish_name=cv_dish if cv_model.is_loaded and cv_dish else None,
                source="cv_local_not_found_vision" if cv_high else "vision",
                cv_confidence=cv_conf if cv_model.is_loaded else None,
                error=f"Vision cloud unreachable: {e}",
            )

        vision_dishes = vision.get("dishes", [])
        if not vision_dishes:
            return AnalyzeResponse(
                source="vision",
                cv_confidence=cv_conf if cv_model.is_loaded else None,
                error="Vision không nhận diện được món ăn trong ảnh. "
                       "Hãy thử ảnh rõ hơn hoặc chụp cận cảnh món ăn.",
            )

        # ── Resolve từng dish → nutrition + auto-add món mới ─────────────
        items, response_dishes, auto_added, missing = await _analyze_vision_dishes(
            session, vision_dishes
        )

        if not items:
            return AnalyzeResponse(
                dish_name=vision.get("dish_name"),
                source="vision",
                cv_confidence=cv_conf if cv_model.is_loaded else None,
                dishes=response_dishes,
                error="Không tính được nutrition cho món nào trong ảnh.",
            )

        # Tên bữa ăn = các món ghép (VD "Phở bò + Quẩy")
        all_names = [d.dish_name for d in response_dishes if d.dish_name]
        combined_name = " + ".join(all_names) if all_names else vision.get("dish_name")

        source = (
            "cv_local_not_found_vision" if _is_cv_high_conf(cv_conf, cv_dish)
            else "vision"
        )

        totals = calculate_totals(
            combined_name, items, missing if missing else None
        )

        return AnalyzeResponse(
            dish_name=combined_name,
            source=source,
            cv_confidence=cv_conf if cv_model.is_loaded else None,
            nutrition=totals,
            dishes=response_dishes,
            vision_reasoning=vision.get("reasoning"),
            auto_added_dishes=auto_added,
            missing_items=missing,
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()


@router.post("/analyze/vision-only", response_model=AnalyzeResponse)
async def analyze_vision_only(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AnalyzeResponse:
    """Force Qwen Vision — bỏ qua CV local, gọi thẳng Vision."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {file.content_type}.",
        )

    safe_name = _safe_filename(file.filename or "upload")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Ảnh quá lớn (>{MAX_UPLOAD_BYTES // (1024*1024)}MB).",
        )

    temp_path = UPLOAD_DIR / f"upload_vision_{uuid.uuid4().hex[:12]}_{safe_name}"
    temp_path.write_bytes(content)

    try:
        vision = await identify_dish(temp_path)

        vision_dishes = vision.get("dishes", [])
        if not vision_dishes:
            return AnalyzeResponse(
                source="vision",
                cv_confidence=None,
                error="Vision không nhận diện được món ăn trong ảnh. "
                       "Hãy thử ảnh rõ hơn hoặc chụp cận cảnh món ăn.",
            )

        items, response_dishes, auto_added, missing = await _analyze_vision_dishes(
            session, vision_dishes
        )

        if not items:
            return AnalyzeResponse(
                dish_name=vision.get("dish_name"),
                source="vision",
                cv_confidence=None,
                dishes=response_dishes,
                error="Không tính được nutrition cho món nào trong ảnh.",
            )

        all_names = [d.dish_name for d in response_dishes if d.dish_name]
        combined_name = " + ".join(all_names) if all_names else vision.get("dish_name")

        totals = calculate_totals(combined_name, items, missing if missing else None)

        return AnalyzeResponse(
            dish_name=combined_name,
            source="vision",
            cv_confidence=None,
            nutrition=totals,
            dishes=response_dishes,
            vision_reasoning=vision.get("reasoning"),
            auto_added_dishes=auto_added,
            missing_items=missing,
        )
    except VisionError as e:
        return AnalyzeResponse(
            source="vision",
            error=f"Vision cloud offline: {str(e)[:200]}",
        )
    except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
        return AnalyzeResponse(
            source="vision",
            error=f"Vision cloud unreachable: {e}",
        )
    finally:
        if temp_path.exists():
            temp_path.unlink()
