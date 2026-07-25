"""Food-image analysis endpoints.

High-confidence local CV results use verified database nutrition directly. Other
requests fall back to Vision, then reconcile each detected menu item with the
local dish and ingredient catalogs.
"""

import asyncio
import logging
import uuid
from pathlib import Path

import httpx

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.postgres import get_session
from backend.api.upload_utils import (
    MAX_IMAGE_UPLOAD_BYTES,
    read_upload_limited,
    validate_image_content_type,
)
from backend.services.dishes import (
    _has_nutrition,
    _has_weight,
    _vn_dish_to_per_gram,
    _vn_ingredient_to_per_gram,
    lookup_dish,
    lookup_dish_exact,
    lookup_ingredient_text,
)
from backend.services.dish_candidates import stage_dish_candidate
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

CV_CONFIDENCE_THRESHOLD = 0.85
MAX_UPLOAD_BYTES = MAX_IMAGE_UPLOAD_BYTES


def _safe_filename(filename: str) -> str:
    """Chặn path traversal: chỉ lấy tên file, thay ký tự không an toàn."""
    safe = Path(filename).name
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in safe)
    return safe or "upload"


router = APIRouter(prefix="/api/v1", tags=["analyze"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("foodai")


def _is_cv_high_conf(cv_conf: float | None, cv_dish: str | None) -> bool:
    """Return whether a local prediction is safe to use without Vision."""
    return (
        cv_model.is_loaded
        and cv_conf is not None
        and cv_conf >= CV_CONFIDENCE_THRESHOLD
        and cv_dish is not None
    )


def _recognition_confidence(dish: dict) -> float | None:
    """Return one normalized item confidence when Vision supplied it."""
    value = dish.get("confidence")
    if value is None:
        return None
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return None


def _portion_source(requested_grams: float, item_grams: float) -> str:
    """Describe whether displayed grams came from Vision or catalog fallback."""
    if requested_grams > 0:
        return "vision"
    if item_grams > 0:
        return "catalog_default"
    return "unknown"


def _has_usable_vision_nutrition(item: NutritionPerIngredient) -> bool:
    """Reject zero-filled Vision rows that carry no usable serving evidence."""
    return item.grams > 0 and item.calories > 0


async def _analyze_cv_local(
    session: AsyncSession,
    dish_name: str,
    confidence: float,
) -> AnalyzeResponse | None:
    """Build a local-CV response when serving-size nutrition is complete."""
    vn = await lookup_dish(session, dish_name)
    if vn is None or not _has_nutrition(vn) or not _has_weight(vn):
        return None

    grams = float(vn.typical_grams)
    item = calculate_item_nutrition(
        vn.dish_name,
        grams,
        _vn_dish_to_per_gram(vn),
    )
    totals = calculate_totals(vn.dish_name, [item])

    return AnalyzeResponse(
        dish_name=vn.dish_name,
        source="cv_local",
        cv_confidence=confidence,
        recognition_confidence=confidence,
        nutrition=totals,
        dishes=[
            AnalyzeDish(
                dish_name=vn.dish_name,
                grams=grams,
                is_side=False,
                found_in_db=True,
                recognition_confidence=confidence,
                portion_source="catalog_default",
            )
        ],
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
        if _has_nutrition(vn) and _has_weight(vn):
            per_gram = _vn_dish_to_per_gram(vn)
            effective_grams = gram if gram > 0 else float(vn.typical_grams)
            return (
                calculate_item_nutrition(vn.dish_name, effective_grams, per_gram),
                vn.dish_name,
            )
        if _has_nutrition(vn):
            return NutritionPerIngredient(
                item_name=vn.dish_name,
                grams=gram,
                calories=round(vn.total_calories, 1),
                protein_g=round(vn.total_protein_g, 1),
                fat_g=round(vn.total_fat_g, 1),
                carbs_g=round(vn.total_carbs_g, 1),
                fiber_g=round(vn.total_fiber_g, 1),
                found_in_db=True,
                nutrition_basis="source_serving",
            ), vn.dish_name
        # Catalog rows without nutrition fall back to the Vision estimate.

    # ── Tier 2: vn_ingredients (chỉ khi is_side — đồ uống/món kèm) ───────
    if is_side:
        ing = await lookup_ingredient_text(session, dish_name)
        if ing is not None:
            per_gram = _vn_ingredient_to_per_gram(ing)
            return (
                calculate_item_nutrition(ing.ingredient_name, gram, per_gram),
                ing.ingredient_name,
            )

    # Unknown labels are staged by the caller; they are not trusted catalog rows.
    return None, resolved_name


async def _analyze_vision_dishes(
    session: AsyncSession,
    vision_dishes: list[dict],
) -> tuple[
    list[NutritionPerIngredient],   # items đã tính
    list[AnalyzeDish],              # dishes response (với is_side)
    list[str],                       # món mới staged để duyệt
    list[str],                       # missing items
]:
    """Resolve Vision dishes and stage unknown labels for later review."""
    items: list[NutritionPerIngredient] = []
    response_dishes: list[AnalyzeDish] = []
    staged: list[str] = []
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
                    grams=item.grams,
                    is_side=is_side,
                    found_in_db=True,
                    recognition_confidence=_recognition_confidence(d),
                    portion_source=_portion_source(gram, item.grams),
                )
            )
            continue

        # Unknown dishes remain usable in this response, but their estimates are
        # staged separately and never become trusted catalog data automatically.
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
                recognition_confidence=_recognition_confidence(d),
                portion_source="vision" if gram > 0 else "unknown",
            )
        )
        if not _has_usable_vision_nutrition(vision_item):
            missing.append(resolved_name)
            logger.warning(
                "Vision dish '%s' has no usable gram/nutrition estimate",
                resolved_name,
            )
            continue
        try:
            await stage_dish_candidate(
                session,
                resolved_name,
                gram if gram > 0 else None,
                nutrition=vision_item,
            )
            await session.commit()
            staged.append(resolved_name)
            items.append(vision_item)
            logger.info(
                "Staged Vision dish '%s' with estimated grams=%s",
                resolved_name,
                gram,
            )
        except Exception:
            await session.rollback()
            logger.exception("Failed to stage Vision dish '%s'", dish_name)
            missing.append(resolved_name)
            items.append(vision_item)

    return items, response_dishes, staged, missing


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_food(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AnalyzeResponse:
    """Upload ảnh món ăn → nhận diện + phân tích dinh dưỡng (dish-level)."""
    validate_image_content_type(file)
    safe_name = _safe_filename(file.filename or "upload")
    content = await read_upload_limited(file, max_bytes=MAX_UPLOAD_BYTES)
    temp_path = UPLOAD_DIR / f"upload_{uuid.uuid4().hex[:12]}_{safe_name}"
    await asyncio.to_thread(temp_path.write_bytes, content)

    try:
        # Use local inference first to avoid a cloud call for reliable classes.
        cv_conf: float | None = None
        cv_dish: str | None = None
        if cv_model.is_loaded:
            cv_result = await asyncio.to_thread(cv_model.predict, temp_path)
            cv_conf = cv_result["confidence"]
            cv_dish = cv_result["dish_name"]

        if _is_cv_high_conf(cv_conf, cv_dish):
            cv_response = await _analyze_cv_local(
                session,
                cv_dish,
                cv_conf,
            )
            if cv_response is not None:
                return cv_response

        # Vision handles low-confidence predictions and incomplete DB records.
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

        # Resolve nutrition and stage unknown labels for explicit review.
        items, response_dishes, staged, missing = await _analyze_vision_dishes(
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
            recognition_confidence=vision.get("confidence"),
            nutrition=totals,
            dishes=response_dishes,
            vision_reasoning=vision.get("reasoning"),
            staged_dishes=staged,
            missing_items=missing,
        )
    finally:
        await asyncio.to_thread(temp_path.unlink, missing_ok=True)


@router.post("/analyze/vision-only", response_model=AnalyzeResponse)
async def analyze_vision_only(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AnalyzeResponse:
    """Force Qwen Vision — bỏ qua CV local, gọi thẳng Vision."""
    validate_image_content_type(file)
    safe_name = _safe_filename(file.filename or "upload")
    content = await read_upload_limited(file, max_bytes=MAX_UPLOAD_BYTES)

    temp_path = UPLOAD_DIR / f"upload_vision_{uuid.uuid4().hex[:12]}_{safe_name}"
    await asyncio.to_thread(temp_path.write_bytes, content)

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

        items, response_dishes, staged, missing = await _analyze_vision_dishes(
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
            recognition_confidence=vision.get("confidence"),
            nutrition=totals,
            dishes=response_dishes,
            vision_reasoning=vision.get("reasoning"),
            staged_dishes=staged,
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
        await asyncio.to_thread(temp_path.unlink, missing_ok=True)
