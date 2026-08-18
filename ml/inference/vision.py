"""Cloud Vision client for menu-level dish recognition and estimation."""

import asyncio
import base64
import json
import unicodedata
from collections.abc import Sequence
from pathlib import Path

import httpx

from backend.config import settings
from backend.services.resilience import CircuitOpenError, ResilientHttpClient


class VisionError(Exception):
    """Lỗi khi gọi Vision API."""


MAX_MENU_ITEMS = 3
MIN_MAIN_CONFIDENCE = 0.55
MIN_SIDE_CONFIDENCE = 0.80
# Model không trả confidence → coi như "vừa đủ tin cho món chính, chưa đủ cho món phụ".
# Tuyệt đối không mặc định 1.0: như vậy là bịa ra sự chắc chắn model chưa từng nói.
UNKNOWN_CONFIDENCE = MIN_MAIN_CONFIDENCE
MAX_REASONABLE_ITEM_GRAMS = 3000.0
MAX_REASONABLE_KCAL_PER_GRAM = 10.0
MAX_REASONABLE_MACRO_MASS_RATIO = 1.25
vision_http_client = ResilientHttpClient(
    service="vision",
    timeout_seconds=30,
    max_concurrency=settings.vision_max_concurrency,
    # Vision quota errors must never be retried: one user action = at most one
    # paid provider request. The analyze endpoint falls back to local evidence.
    max_attempts=1,
    failure_threshold=2,
    recovery_seconds=30,
)

INCLUDED_ACCOMPANIMENTS = (
    "do chua",
    "rau muong chua",
    "dua chua",
    "dua leo",
    "ca chua",
    "rau song",
    "rau thom",
    "mo hanh",
    "hanh phi",
    "nuoc cham",
    "nuoc mam",
    "sot an kem",
)


def _build_food_identification_prompt(
    candidate_names: Sequence[str] | None = None,
) -> str:
    """Prompt nhận diện ở cấp món trên menu, không tách vụn mọi thành phần."""
    prompt = (
        "Bạn là chuyên gia ẩm thực và dinh dưỡng Việt Nam.\n"
        "Hãy nhận diện món ở MỨC KHÁI QUÁT NHƯ TÊN GỌI TRÊN MENU, "
        "không làm object detection từng thứ ăn được.\n\n"
        "QUY TẮC NHÓM MÓN (ƯU TIÊN CAO NHẤT):\n"
        "- Một đĩa combo chỉ trả TỐI ĐA 3 món: 1 món chính và tối đa 2 món phụ.\n"
        "- Món chính phải gom tinh bột + phần đạm chính thành tên quen thuộc. "
        "Ví dụ cơm và sườn nướng trên cùng đĩa phải gọi là 'Cơm sườn'.\n"
        "- Chỉ tách món phụ khi đó là một món chế biến có tên riêng trên menu, "
        "rõ nét, nổi bật và được chụp có chủ ý như món chính.\n"
        "- Gộp các phần liên quan thành tên menu chung; ví dụ chả trứng và bì "
        "trên đĩa cơm tấm gọi chung là 'Chả bì'.\n"
        "- KHÔNG tách riêng cơm, thịt, nhân bên trong, topping nhỏ, dưa leo, "
        "đồ chua, rau muống chua, rau thơm, mỡ hành, nước chấm, sốt hoặc đồ "
        "trang trí. Các phần này đã thuộc khẩu phần món chính.\n"
        "- Bỏ qua thức ăn mờ ở hậu cảnh, bao bì và vật thể vô tình lọt vào ảnh.\n"
        "- Không suy diễn món lạ từ màu sắc/hình dạng; dùng tên Việt Nam phổ biến, ngắn gọn.\n\n"
        "QUY TẮC ĐỘ TIN CẬY:\n"
        "- Mỗi món phải có confidence từ 0 đến 1, phản ánh độ chắc chắn về đúng tên món.\n"
        "- Chỉ trả món phụ khi confidence >= 0.80; nếu chưa chắc thì BỎ QUA, không đoán.\n"
        "- Món chính confidence < 0.55 thì trả dishes=[] thay vì đoán tên món.\n"
        "- Không tăng confidence chỉ vì nhìn thấy một màu hoặc hình dạng giống món đó.\n\n"
        "VÍ DỤ BẮT BUỘC CHO CƠM TẤM COMBO:\n"
        "Nếu ảnh là một đĩa có cơm, sườn nướng, trứng ốp la, chả trứng, bì, "
        "một ít lạp xưởng và đồ chua thì chỉ trả 3 món: "
        "'Cơm sườn', 'Trứng ốp la', 'Chả bì'. "
        "Không tạo mục riêng cho cơm, sườn, lạp xưởng, bì hay đồ chua.\n\n"
        "Nếu đồng thời thấy miếng chả trứng và bì sợi, tên mục thứ ba BẮT BUỘC là "
        "'Chả bì', không được chỉ gọi là 'Chả trứng' và không tách 'Bì' riêng.\n"
        "Nếu là đĩa cơm tấm có thịt heo thái lát/sợi, bì, chả và trứng, "
        "phần thịt có thể là sườn đã cắt nhỏ: món chính BẮT BUỘC gọi là "
        "'Cơm sườn', không gọi là 'Cơm chả lụa trứng'. Bát canh đặt riêng "
        "vẫn được nhận là một món phụ.\n"
        "Ví dụ tên trong output: "
        '{"dishes": [{"dish_name": "Cơm sườn"}, '
        '{"dish_name": "Trứng ốp la"}, {"dish_name": "Chả bì"}]}\n\n'
        "BẮT BUỘC — OUTPUT CHÍNH XÁC:\n"
        "Trả về CHỈ JSON đúng cấu trúc:\n"
        '{"confidence": số từ 0 đến 1, "dishes": [{"dish_name": str, '
        '"gram": số, "gram_confidence": số từ 0 đến 1, "serving_label": str, "is_side": bool, '
        '"confidence": số từ 0 đến 1, '
        '"total_calories": số, "total_protein_g": số, "total_fat_g": số, '
        '"total_carbs_g": số, "total_fiber_g": số}]}\n'
        "- confidence ngoài cùng là độ tin cậy tổng thể của lần nhận diện.\n"
        "- confidence trong từng mục là độ tin cậy của riêng tên món đó.\n"
        "- Mục đầu tiên luôn là món chính và is_side=false.\n"
        "- Các mục sau là món phụ và is_side=true.\n"
        "- gram là khối lượng của đúng nhóm món đó; không tính trùng gram giữa các mục.\n"
        "- gram_confidence là độ chắc chắn riêng về khối lượng; nếu không chắc "
        "khối lượng thì dùng confidence thấp, nhất là khi không có vật chuẩn "
        "so sánh.\n"
        "- serving_label là đơn vị khẩu phần nhìn thấy ứng với đúng lượng gram. "
        "BẮT BUỘC ghi ngắn theo mẫu '1 tô', '1 chén', '1 ly', '1 đĩa', '1 phần' "
        "hoặc '1 cái'; chọn đơn vị phù hợp nhất. Không ghi dấu '/', không ghi gram hoặc calo.\n"
        "- total_calories dùng kcal; 4 trường còn lại dùng gram.\n"
        "- Các total là cho đúng lượng gram vừa ước tính, không phải trên 100g.\n"
        "- Không có trường ingredients. Nếu không thấy món nào thì dishes=[].\n"
        "Trả về CHỈ JSON, không markdown, không giải thích ngoài JSON."
    )
    if not candidate_names:
        return prompt

    unique_candidates = list(dict.fromkeys(
        name.strip() for name in candidate_names if isinstance(name, str) and name.strip()
    ))[:12]
    if not unique_candidates:
        return prompt
    candidate_block = "\n".join(f"- {name}" for name in unique_candidates)
    return (
        f"{prompt}\n\n"
        "DANH SÁCH ỨNG VIÊN TỪ CATALOG:\n"
        f"{candidate_block}\n"
        "Danh sách này chỉ là gợi ý ưu tiên do CV local, album ảnh và Qdrant "
        "đưa ra; nó có thể thiếu hoặc sai. Không được chọn một ứng viên chỉ vì "
        "nó có trong danh sách. Nếu dấu hiệu nhìn thấy trong ảnh mâu thuẫn với "
        "các ứng viên, hãy trả tên món đúng bằng tiếng Việt kể cả khi tên đó "
        "nằm ngoài danh sách. Ví dụ: danh sách chỉ có 'Phở gà' nhưng ảnh thấy "
        "rõ thịt bò thì phải trả 'Phở bò'. Chỉ trả dishes=[] khi ảnh không có "
        "món ăn hoặc không đủ dấu hiệu để nhận diện."
    )


async def identify_dish(
    image_path: str | Path,
    *,
    candidate_names: Sequence[str] | None = None,
) -> dict:
    """Nhận diện món ăn từ ảnh — trả về danh sách món + gram.

    Gửi ảnh lên Vision API, trả về:
        - dishes: [{dish_name, gram, is_side, total_*}, ...]
            + dish_name: tên món tiếng Việt (có dấu)
            + gram: khối lượng ước lượng (gram) cho món đó
            + is_side: True nếu là món ăn kèm / đồ uống (VD: quảy, soda, sữa hộp)
        - dish_name (top-level): món đầu tiên (backward-compat cho analyze.py cũ)

    KHÔNG phân tích nguyên liệu trong từng món. Món chưa có DB → backend tự thêm
    cùng gram và tổng dinh dưỡng Vision ước lượng.

    Raises:
        VisionError: nếu API lỗi hoặc response không hợp lệ.
    """
    image_path = Path(image_path)

    if not image_path.exists():
        raise VisionError(f"File không tồn tại: {image_path}")

    image_bytes = await asyncio.to_thread(image_path.read_bytes)
    image_data = base64.b64encode(image_bytes).decode("utf-8")

    # Xác định MIME type
    suffix = image_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    mime_type = mime_map.get(suffix, "image/jpeg")

    system_prompt = _build_food_identification_prompt(candidate_names)

    # OpenAI-compatible multimodal request. The output budget accommodates
    # providers that add reasoning metadata around the requested JSON.
    request_body = {
        "model": settings.vision_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                    },
                    {
                        "type": "text",
                        "text": (
                            "Nhận diện ở cấp tên món trên menu. Chỉ trả tối đa 3 món, "
                            "không tách nguyên liệu, topping hoặc đồ ăn kèm nhỏ. "
                            "Bỏ mọi món phụ có confidence dưới 0.80."
                            + (
                                " Ưu tiên chọn món chính trong danh sách catalog "
                                "được cung cấp ở system prompt."
                                if candidate_names
                                else ""
                            )
                        ),
                    },
                ],
            },
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        # Compatible providers may ignore this optional latency optimization.
        "chat_template_kwargs": {"enable_thinking": False},
    }

    headers = {
        "Authorization": f"Bearer {settings.vision_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = await vision_http_client.post(
            f"{settings.vision_api_base}/chat/completions",
            json=request_body,
            headers=headers,
        )
    except CircuitOpenError as exc:
        raise VisionError("Vision API tạm ngắt để bảo vệ hệ thống") from exc
    except httpx.HTTPStatusError as exc:
        raise VisionError(
            f"Vision API lỗi HTTP {exc.response.status_code}"
        ) from exc

    if response.status_code != 200:
        # Do not expose provider response bodies; they may contain internal details.
        raise VisionError(
            f"Vision API lỗi HTTP {response.status_code}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise VisionError("Vision API trả response không phải JSON") from exc
    content = _extract_message_content(data)

    # Providers may wrap the requested object in reasoning tags or code fences.
    try:
        result = _parse_json_response(content)
    except json.JSONDecodeError as exc:
        raise VisionError("Vision API trả nội dung JSON không hợp lệ") from exc

    if not isinstance(result, dict):
        raise VisionError("Vision API phải trả về một JSON object")

    # ── Validate + normalize: format mới (dishes[]) hoặc cũ (dish_name) ──
    if "dishes" not in result:
        if "dish_name" in result:
            result["dishes"] = [{"dish_name": result["dish_name"]}] if result["dish_name"] else []
        else:
            raise VisionError("Vision API thiếu field 'dishes' hoặc 'dish_name'")

    raw_dishes = result["dishes"]
    if not isinstance(raw_dishes, list):
        raise VisionError("Field 'dishes' phải là một JSON array")

    normalized = _normalize_dishes(
        raw_dishes,
        default_confidence=result.get("confidence"),
    )
    result["dishes"] = normalized
    result["dish_name"] = normalized[0]["dish_name"] if normalized else None
    result["confidence"] = _as_confidence(
        result.get("confidence"),
        default=UNKNOWN_CONFIDENCE if normalized else 0.0,
    )
    # reasoning là text tự do; provider có thể trả dict/list → ép về str|None
    # để Pydantic không làm hỏng cả response đã tính đúng.
    reasoning = result.get("reasoning")
    result["reasoning"] = reasoning if isinstance(reasoning, str) else None

    return result


async def close_vision_client() -> None:
    await vision_http_client.close()


def _as_non_negative_float(value: object) -> float:
    """Đổi output không ổn định của model sang số không âm an toàn."""
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _normalize_serving_label(value: object) -> str | None:
    """Keep a compact, display-safe Vietnamese serving unit from Vision."""
    if not isinstance(value, str):
        return None
    label = " ".join(value.strip().lstrip("/").split())
    return label[:30] or None


def _extract_message_content(data: object) -> str:
    """Extract text from an OpenAI-compatible response with schema checks."""
    if not isinstance(data, dict):
        raise VisionError("Vision API response không hợp lệ")
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise VisionError("Vision API response không hợp lệ") from exc

    if not isinstance(content, str) or not content.strip():
        raise VisionError("Vision API response không hợp lệ")
    return content


def _as_confidence(value: object, *, default: float) -> float:
    """Chuẩn hóa confidence về khoảng 0..1."""
    if value is None:
        return default
    try:
        return min(1.0, max(0.0, float(value)))
    except (TypeError, ValueError):
        return default


def _search_label(value: str) -> str:
    """Bỏ dấu để so tên garnish ổn định với mọi kiểu viết từ model."""
    decomposed = unicodedata.normalize("NFKD", value.casefold().replace("đ", "d"))
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _is_included_accompaniment(dish_name: str) -> bool:
    """True khi đây là garnish/đồ chua vốn đã nằm trong khẩu phần món chính."""
    label = _search_label(dish_name)
    return any(name in label for name in INCLUDED_ACCOMPANIMENTS)


def _has_plausible_food_values(
    gram: float,
    calories: float,
    protein: float,
    fat: float,
    carbs: float,
    fiber: float,
) -> bool:
    """Reject impossible Vision totals without pretending to medically validate food."""
    if gram <= 0:
        return True
    if gram > MAX_REASONABLE_ITEM_GRAMS:
        return False
    if calories > gram * MAX_REASONABLE_KCAL_PER_GRAM:
        return False
    macro_mass = protein + fat + carbs + fiber
    return macro_mass <= gram * MAX_REASONABLE_MACRO_MASS_RATIO


def _normalize_dishes(
    raw_dishes: list[object], *, default_confidence: object = None
) -> list[dict]:
    """Chuẩn hóa tên, gram, loại món và tổng dinh dưỡng từng món.

    Linh hoạt chấp nhận nhiều biến thể model có thể trả:
      - gram / grams / weight_grams / total_grams cho khối lượng
      - is_side hoặc is_main (đảo) cho loại món
      - nếu thiếu gram tổng mà có ingredients → tổng gram nguyên liệu (fallback)
    """
    normalized = []
    fallback_confidence = _as_confidence(default_confidence, default=UNKNOWN_CONFIDENCE)
    for d in raw_dishes:
        if not isinstance(d, dict):
            continue
        name = d.get("dish_name")
        if not name:
            continue
        gram = d.get("gram")
        if not gram:
            gram = d.get("grams") or d.get("weight_grams") or d.get("total_grams")
        gram = _as_non_negative_float(gram)
        if gram <= 0 and isinstance(d.get("ingredients"), list):
            gram = sum(
                _as_non_negative_float(i.get("gram", 0) or i.get("grams", 0))
                for i in d["ingredients"]
                if isinstance(i, dict)
            )
        is_first_valid_item = not normalized
        if is_first_valid_item:
            is_side = False
        elif "is_side" in d:
            is_side = bool(d["is_side"])
        elif "is_main" in d:
            is_side = not bool(d["is_main"])
        else:
            is_side = True

        confidence = _as_confidence(
            d.get("confidence", d.get("confidence_score")),
            default=fallback_confidence,
        )
        threshold = MIN_SIDE_CONFIDENCE if is_side else MIN_MAIN_CONFIDENCE
        if confidence < threshold:
            if is_first_valid_item:
                return []
            continue
        if is_side and normalized and _is_included_accompaniment(str(name)):
            continue

        total_calories = _as_non_negative_float(
            d.get("total_calories", d.get("total_calories_g", 0))
        )
        total_protein = _as_non_negative_float(d.get("total_protein_g"))
        total_fat = _as_non_negative_float(d.get("total_fat_g"))
        total_carbs = _as_non_negative_float(d.get("total_carbs_g"))
        total_fiber = _as_non_negative_float(d.get("total_fiber_g"))
        if not _has_plausible_food_values(
            gram,
            total_calories,
            total_protein,
            total_fat,
            total_carbs,
            total_fiber,
        ):
            # Số model đưa ra bất khả thi → chỉ bỏ CON SỐ, giữ lại TÊN món.
            # Catalog PostgreSQL mới là nguồn dinh dưỡng chính thức; vứt cả món
            # đi sẽ làm hỏng những món vốn tra được trong DB.
            if gram > MAX_REASONABLE_ITEM_GRAMS:
                gram = 0.0
            total_calories = 0.0
            total_protein = 0.0
            total_fat = 0.0
            total_carbs = 0.0
            total_fiber = 0.0

        normalized_item = {
            "dish_name": str(name).strip(),
            "gram": gram,
            "is_side": is_side,
            "confidence": confidence,
            "total_calories": total_calories,
            "total_protein_g": total_protein,
            "total_fat_g": total_fat,
            "total_carbs_g": total_carbs,
            "total_fiber_g": total_fiber,
        }
        serving_label = _normalize_serving_label(d.get("serving_label"))
        if serving_label:
            normalized_item["serving_label"] = serving_label
        if "gram_confidence" in d:
            normalized_item["gram_confidence"] = _as_confidence(
                d.get("gram_confidence"),
                default=0.0,
            )
        normalized.append(normalized_item)
    _canonicalize_com_tam_labels(normalized)
    return normalized[:MAX_MENU_ITEMS]


def _canonicalize_com_tam_labels(dishes: list[dict]) -> None:
    """Chuẩn hóa tên menu cho combo cơm tấm mà không đổi gram/nutrition."""
    if not dishes:
        return

    main_name = dishes[0]["dish_name"].casefold()
    if "cơm sườn" not in main_name and "cơm tấm" not in main_name:
        return

    for dish in dishes[1:]:
        side_name = dish["dish_name"].casefold()
        if "chả" in side_name and "trứng" in side_name:
            dish["dish_name"] = "Chả bì"


async def suggest_nutrition(ingredient_name: str) -> dict:
    """Tra cứu nutrition cho 10g từ Qwen text-only (không cần ảnh).

    Qwen được huấn luyện trên toàn bộ internet → có kiến thức về USDA,
    Bộ Y Tế VN, Viện Dinh Dưỡng. Dùng nó làm "search engine thông minh"
    thay vì tìm trong DB local (DB có thể không có hoặc match sai).

    Returns:
        {
            "ingredient_name": str,
            "sources": [
                {
                    "source_label": "USDA (Mỹ)",
                    "ingredient_en": "Rice flour, white",
                    "per_10g_calories": 36.6,
                    "per_10g_protein": 0.6,
                    "per_10g_fat": 0.1,
                    "per_10g_carbs": 8.0,
                    "per_10g_fiber": 0.2,
                },
                ...
            ]
        }
    """
    prompt = (
        f"Tra cứu giá trị dinh dưỡng cho **10 gram** của nguyên liệu: **{ingredient_name}**.\n\n"
        "QUY TẮC:\n"
        "- Trả về 2-3 nguồn khác nhau: USDA (Mỹ, tiêu chuẩn quốc tế), "
        "Bộ Y Tế / Viện Dinh Dưỡng Việt Nam, và/hoặc nguồn uy tín khác.\n"
        "- Mỗi nguồn phải ghi rõ: tên tiếng Anh CHUẨN của nguyên liệu (theo cách nguồn đó gọi), "
        "và 5 chỉ số dinh dưỡng cho ĐÚNG 10 gram.\n"
        "- Dùng kiến thức của bạn về USDA FoodData Central database và "
        "Vietnam Food Composition Table (Bộ Y Tế / Viện Dinh Dưỡng VN).\n"
        "- Nếu nguồn không có số liệu chính xác cho nguyên liệu này, hãy ghi chú "
        "\"ước lượng từ nguyên liệu tương tự\".\n"
        "- Calories = kcal. Tất cả giá trị là cho 10g (không phải 100g).\n\n"
        "Trả về CHỈ JSON (không markdown):\n"
        "{\n"
        '  "sources": [\n'
        '    {\n'
        '      "source_label": "USDA (Mỹ — tiêu chuẩn quốc tế)",\n'
        '      "ingredient_en": "tên tiếng Anh chuẩn trong DB nguồn",\n'
        '      "per_10g_calories": số,\n'
        '      "per_10g_protein": số,\n'
        '      "per_10g_fat": số,\n'
        '      "per_10g_carbs": số,\n'
        '      "per_10g_fiber": số,\n'
        '      "note": "chính xác từ USDA FoodData Central" hoặc "ước lượng từ..."\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "Nếu bạn thực sự không biết → trả về sources rỗng []."
    )

    request_body = {
        "model": settings.vision_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1024,
        # Qwen3.7 Plus mặc định bật "thinking" (reasoning_content) → 60-70s/câu,
        # vượt timeout → backend fallback DB → nguyên liệu mới về 0.
        # Tắt thinking → 3-5s/câu, đủ nhanh cho UX quick-add.
        "chat_template_kwargs": {"enable_thinking": False},
    }

    headers = {
        "Authorization": f"Bearer {settings.vision_api_key}",
        "Content-Type": "application/json",
    }

    # Timeout 30s (thinking tắt → Qwen trả <10s; 30s là biên an toàn).
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.vision_api_base}/chat/completions",
            json=request_body,
            headers=headers,
        )

    if response.status_code != 200:
        raise VisionError(
            f"Qwen suggest lỗi HTTP {response.status_code}"
        )

    try:
        data = response.json()
        content = _extract_message_content(data)
    except (ValueError, VisionError):
        return {"ingredient_name": ingredient_name, "sources": []}

    try:
        result = _parse_json_response(content)
    except json.JSONDecodeError:
        # Fallback: trả về rỗng nếu Qwen không trả JSON hợp lệ
        return {"ingredient_name": ingredient_name, "sources": []}

    if not isinstance(result, dict):
        return {"ingredient_name": ingredient_name, "sources": []}

    result["ingredient_name"] = ingredient_name
    return result


def _parse_json_response(content: str) -> dict:
    """Parse JSON từ LLM response — xử lý nhiều format khác nhau.

    - Markdown code block: ```json ... ```
    - Thinking tags: <think>...</think> (Minimax-M3, Qwen3.7)
    - JSON thuần: {"dish_name": "..."}

    Tránh dùng lines[1:-1] vì khi thiếu ``` đóng (LLM bị truncate do max_tokens),
    dòng JSON cuối cùng bị cắt mất → JSONDecodeError.
    """
    import re

    content = content.strip()

    # 1. Strip <think>...</think> tags (Minimax-M3, Qwen3.7 thinking mode)
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # 2. Dùng regex để trích JSON từ markdown code block
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
    if match:
        content = match.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as original_error:
        # Some providers append a short explanation despite the JSON-only prompt.
        # Decode the first complete object so harmless surrounding text does not
        # turn an otherwise usable vision result into a failed request.
        decoder = json.JSONDecoder()
        for index, character in enumerate(content):
            if character != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(content[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        raise original_error
