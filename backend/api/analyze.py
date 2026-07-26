"""Food-image analysis endpoints.

Local CV supplies a broad dish-family prior. Qdrant builds a reviewed shortlist,
Vision chooses the best visual match, and PostgreSQL remains the nutrition
source of truth.
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
    validate_and_sanitize_image,
    validate_image_content_type,
)
from backend.api.dependencies import CurrentUser, require_user
from backend.config import settings
from backend.metrics import ANALYSIS_RESULTS
from backend.services.dishes import (
    _has_nutrition,
    _has_weight,
    _vn_dish_to_per_gram,
    _vn_ingredient_to_per_gram,
    dish_family_query,
    lookup_dish,
    lookup_dish_candidates,
    lookup_dish_exact,
    lookup_ingredient_text,
    resolve_catalog_portion_grams,
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

MAX_UPLOAD_BYTES = MAX_IMAGE_UPLOAD_BYTES
CV_FAMILY_MAX_PREDICTIONS = 3
CV_FAMILY_MIN_PROBABILITY = 0.15
#: Đủ số gợi ý cho Vision thì dừng, khỏi tốn thêm lượt embedding + Qdrant.
CV_FAMILY_MAX_CANDIDATES = 8


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


def _analysis_response(**values: object) -> AnalyzeResponse:
    source = values.get("source")
    # Mọi nhánh do CV dẫn dắt đều bắt đầu bằng "cv_local" ("cv_local",
    # "cv_local_not_found_vision", …) nên phải so bằng prefix, không so bằng nhau.
    values.setdefault(
        "model_version",
        cv_model.model_version
        if isinstance(source, str) and source.startswith("cv_local")
        else settings.vision_model,
    )
    response = AnalyzeResponse(**values)
    ANALYSIS_RESULTS.labels(
        source=response.source or "unknown",
        outcome="error" if response.error else "success",
    ).inc()
    return response


def _is_cv_high_conf(cv_conf: float | None, cv_dish: str | None) -> bool:
    """Return whether a local prediction is safe to use without Vision."""
    return (
        cv_model.is_loaded
        and cv_conf is not None
        and cv_conf >= cv_model.serving_threshold
        and cv_dish is not None
    )


def _cv_family_queries(
    cv_dish: str | None,
    predictions: list[dict] | None,
) -> list[str]:
    """Turn CV top-k labels into a small set of broad catalog queries."""
    names: list[str] = []
    if cv_dish:
        names.append(cv_dish)
    for prediction in (predictions or [])[:CV_FAMILY_MAX_PREDICTIONS]:
        name = prediction.get("class_name")
        try:
            probability = float(prediction.get("probability", 0) or 0)
        except (TypeError, ValueError):
            probability = 0.0
        if isinstance(name, str) and probability >= CV_FAMILY_MIN_PROBABILITY:
            names.append(name)

    queries: list[str] = []
    for name in names:
        family = dish_family_query(name)
        if family and family not in queries:
            queries.append(family)
    return queries


def _recognition_confidence(dish: dict) -> float | None:
    """Return one normalized item confidence when Vision supplied it."""
    value = dish.get("confidence")
    if value is None:
        return None
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return None


def _gram_confidence(dish: dict) -> float:
    """Return Vision's separate confidence for the estimated portion weight."""
    try:
        return min(1.0, max(0.0, float(dish.get("gram_confidence", 0) or 0)))
    except (TypeError, ValueError):
        return 0.0


def _has_usable_vision_nutrition(item: NutritionPerIngredient) -> bool:
    """Reject zero-filled Vision rows that carry no usable serving evidence."""
    return item.grams > 0 and item.calories > 0


async def _resolve_dish_item(
    session: AsyncSession,
    dish_name: str,
    gram: float,
    is_side: bool,
    gram_confidence: float = 0.0,
) -> tuple[NutritionPerIngredient | None, str, str]:
    """Resolve 1 dish vision → NutritionPerIngredient.

    Tra vn_dishes trước → nếu miss + is_side → tra vn_ingredients → nếu vẫn miss → None.

    Returns:
        (nutrition_item | None, canonical_name, portion_source).
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
            effective_grams, portion_source = resolve_catalog_portion_grams(
                vn.dish_name,
                float(vn.typical_grams),
                gram,
                gram_confidence,
            )
            return (
                calculate_item_nutrition(vn.dish_name, effective_grams, per_gram),
                vn.dish_name,
                portion_source,
            )
        if _has_nutrition(vn):
            # Catalog có tổng dinh dưỡng nhưng KHÔNG có khối lượng chuẩn.
            # Không gán gram của Vision vào đây: con số đó không tham gia phép
            # tính, gán vào sẽ tạo ra mật độ calo vô nghĩa và làm hỏng bộ chỉnh
            # khẩu phần (calculate_adjusted_totals từ chối basis này).
            return NutritionPerIngredient(
                item_name=vn.dish_name,
                grams=0.0,
                calories=round(vn.total_calories, 1),
                protein_g=round(vn.total_protein_g, 1),
                fat_g=round(vn.total_fat_g, 1),
                carbs_g=round(vn.total_carbs_g, 1),
                fiber_g=round(vn.total_fiber_g, 1),
                found_in_db=True,
                nutrition_basis="source_serving",
            ), vn.dish_name, "unknown"
        # Catalog rows without nutrition fall back to the Vision estimate.

    # ── Tier 2: vn_ingredients (chỉ khi is_side — đồ uống/món kèm) ───────
    # Nguyên liệu chỉ có số liệu theo gram, không có khẩu phần chuẩn để fallback.
    # Thiếu gram thì coi như chưa tra được, để caller đưa vào "missing" — nếu
    # không sẽ sinh ra item 0 kcal nhưng vẫn gắn cờ found_in_db=True.
    if is_side and gram > 0:
        ing = await lookup_ingredient_text(session, dish_name)
        if ing is not None:
            per_gram = _vn_ingredient_to_per_gram(ing)
            return (
                calculate_item_nutrition(ing.ingredient_name, gram, per_gram),
                ing.ingredient_name,
                "vision",
            )

    # Unknown labels are staged by the caller; they are not trusted catalog rows.
    return None, resolved_name, "unknown"


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
        item, resolved_name, portion_source = await _resolve_dish_item(
            session,
            dish_name,
            gram,
            is_side,
            _gram_confidence(d),
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
                    portion_source=portion_source,
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
            # Chỉ đếm MỘT lần: calculate_totals lấy tổng = len(items) + len(missing),
            # thêm vào cả hai chỗ sẽ làm confidence_score tụt sai.
            # Số liệu Vision vẫn dùng được nên giữ trong items.
            items.append(vision_item)

    return items, response_dishes, staged, missing


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_food(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    _current_user: CurrentUser = Depends(require_user),
) -> AnalyzeResponse:
    """Upload ảnh món ăn → nhận diện + phân tích dinh dưỡng (dish-level)."""
    validate_image_content_type(file)
    content = await read_upload_limited(file, max_bytes=MAX_UPLOAD_BYTES)
    image = await asyncio.to_thread(
        validate_and_sanitize_image,
        content,
        file.content_type,
    )
    temp_path = UPLOAD_DIR / f"upload_{uuid.uuid4().hex[:12]}{image.extension}"
    await asyncio.to_thread(temp_path.write_bytes, image.content)

    try:
        # Use local inference first to avoid a cloud call for reliable classes.
        cv_conf: float | None = None
        cv_dish: str | None = None
        cv_predictions: list[dict] = []
        catalog_candidates: list[str] = []
        if cv_model.is_loaded:
            cv_result = await asyncio.to_thread(cv_model.predict, temp_path)
            cv_conf = cv_result["confidence"]
            cv_dish = cv_result["dish_name"]
            cv_predictions = cv_result.get("all_predictions", [])

        family_queries = _cv_family_queries(cv_dish, cv_predictions)
        for family in family_queries:
            candidate_rows = await lookup_dish_candidates(session, family)
            new_names = [
                row.dish_name
                for row in candidate_rows
                if row.dish_name not in catalog_candidates
            ]
            catalog_candidates.extend(new_names)
            logger.info("CV family %r yielded catalog candidates: %s", family, new_names)
            # Mỗi vòng tốn 1 lượt embedding + 1 truy vấn Qdrant và nằm trên
            # critical path trước khi gọi Vision. Đủ gợi ý thì dừng sớm.
            if len(catalog_candidates) >= CV_FAMILY_MAX_CANDIDATES:
                break

        # CV is a family prior, not the final visual decision. Vision sees the
        # image and chooses among the reviewed candidates returned by Qdrant.
        vision_kwargs = (
            {"candidate_names": catalog_candidates}
            if catalog_candidates
            else {}
        )
        try:
            vision = await identify_dish(temp_path, **vision_kwargs)
        except VisionError as e:
            logger.warning("Vision analysis failed: %s", e)
            cv_high = _is_cv_high_conf(cv_conf, cv_dish)
            return _analysis_response(
                dish_name=cv_dish if cv_model.is_loaded and cv_dish else None,
                source="cv_local_not_found_vision" if cv_high else "vision",
                cv_confidence=cv_conf if cv_model.is_loaded else None,
                error="Dịch vụ nhận diện đang tạm gián đoạn. Vui lòng thử lại sau.",
            )
        except (httpx.ConnectError, httpx.TimeoutException, OSError):
            logger.exception("Vision analysis connection failed")
            cv_high = _is_cv_high_conf(cv_conf, cv_dish)
            return _analysis_response(
                dish_name=cv_dish if cv_model.is_loaded and cv_dish else None,
                source="cv_local_not_found_vision" if cv_high else "vision",
                cv_confidence=cv_conf if cv_model.is_loaded else None,
                error="Dịch vụ nhận diện đang tạm gián đoạn. Vui lòng thử lại sau.",
            )

        vision_dishes = vision.get("dishes", [])
        if not vision_dishes:
            return _analysis_response(
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
            return _analysis_response(
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

        return _analysis_response(
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
    _current_user: CurrentUser = Depends(require_user),
) -> AnalyzeResponse:
    """Force Qwen Vision — bỏ qua CV local, gọi thẳng Vision."""
    validate_image_content_type(file)
    content = await read_upload_limited(file, max_bytes=MAX_UPLOAD_BYTES)
    image = await asyncio.to_thread(
        validate_and_sanitize_image,
        content,
        file.content_type,
    )
    temp_path = UPLOAD_DIR / (
        f"upload_vision_{uuid.uuid4().hex[:12]}{image.extension}"
    )
    await asyncio.to_thread(temp_path.write_bytes, image.content)

    try:
        vision = await identify_dish(temp_path)

        vision_dishes = vision.get("dishes", [])
        if not vision_dishes:
            return _analysis_response(
                source="vision",
                cv_confidence=None,
                error="Vision không nhận diện được món ăn trong ảnh. "
                       "Hãy thử ảnh rõ hơn hoặc chụp cận cảnh món ăn.",
            )

        items, response_dishes, staged, missing = await _analyze_vision_dishes(
            session, vision_dishes
        )

        if not items:
            return _analysis_response(
                dish_name=vision.get("dish_name"),
                source="vision",
                cv_confidence=None,
                dishes=response_dishes,
                error="Không tính được nutrition cho món nào trong ảnh.",
            )

        all_names = [d.dish_name for d in response_dishes if d.dish_name]
        combined_name = " + ".join(all_names) if all_names else vision.get("dish_name")

        totals = calculate_totals(combined_name, items, missing if missing else None)

        return _analysis_response(
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
        logger.warning("Vision-only analysis failed: %s", e)
        return _analysis_response(
            source="vision",
            error="Dịch vụ nhận diện đang tạm gián đoạn. Vui lòng thử lại sau.",
        )
    except (httpx.ConnectError, httpx.TimeoutException, OSError):
        logger.exception("Vision-only analysis connection failed")
        return _analysis_response(
            source="vision",
            error="Dịch vụ nhận diện đang tạm gián đoạn. Vui lòng thử lại sau.",
        )
    finally:
        await asyncio.to_thread(temp_path.unlink, missing_ok=True)
