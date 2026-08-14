"""Response schemas for dish-level food-image analysis."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from schemas.nutrition import NutritionTotals


class AnalyzeDish(BaseModel):
    """Một món sau khi đã đối chiếu Vision với DB."""

    dish_name: str = Field(description="Tên chuẩn trong DB nếu match, nếu không là tên Vision")
    vision_dish_name: str | None = Field(
        default=None,
        description="Tên gốc Vision trả, chỉ có giá trị khi khác tên chuẩn trong DB",
    )
    grams: float = Field(default=0.0, ge=0, description="Khối lượng ước lượng (gram) từ Vision")
    is_side: bool = Field(
        default=False,
        description="True = món ăn kèm / đồ uống (tra cả vn_ingredients nếu vn_dishes thiếu)",
    )
    found_in_db: bool = Field(
        default=False,
        description="True nếu dùng tên và dinh dưỡng DB; False nếu dùng kết quả Vision",
    )
    recognition_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence nhận diện riêng của item, không phải độ phủ catalog.",
    )
    portion_source: Literal["vision", "catalog_default", "user_input", "unknown"] = Field(
        default="unknown",
        description="Nguồn gram hiển thị cho item.",
    )
    serving_label: str | None = Field(
        default=None,
        max_length=30,
        description="Đơn vị khẩu phần Vision nhìn thấy, ví dụ '1 tô' hoặc '1 ly'.",
    )


class AnalyzeMatch(BaseModel):
    """Candidate returned when a text name matches a nutrition catalog."""

    record_id: str
    canonical_name: str
    catalog_type: Literal["vn_dish", "vn_ingredient", "nrihcm_food"]
    source: str
    nutrition_basis: str
    review_status: Literal["reviewed", "raw"]


class TextAnalyzeRequest(BaseModel):
    """User-provided food name and actual amount to analyze."""

    food_name: str = Field(min_length=1, max_length=300)
    grams: float = Field(default=100.0, gt=0, le=10_000)

    @field_validator("food_name")
    @classmethod
    def normalize_food_name(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("Tên món không được để trống.")
        return cleaned


class AnalyzeResponse(BaseModel):
    """Response cho POST /api/v1/analyze.

    - source='vision': Vision nhận diện + lookup vn_dishes/vn_ingredients.
    - source='local_consensus' and 'cv_local_not_found_vision' are legacy
      response values kept only so old clients can deserialize history; the
      current API never emits them.
    - nutrition: NutritionTotals (dish-level, không có per-ingredient list).
    - dishes: list món Vision trả (tên + gram).
    - staged_dishes: món mới được lưu ở khu vực chờ duyệt.
    - missing_items: item dùng Vision nhưng staging thất bại.
    """

    dish_name: str | None = Field(default=None, description="Tên món chính / bữa ăn")
    source: Literal[
        "local_consensus",
        "vision",
        "cv_local_not_found_vision",
        "text_catalog",
        "text_nrihcm_raw",
        "text_ai_estimate",
        "text_ambiguous",
        "text_not_found",
    ]
    model_version: str | None = Field(
        default=None,
        description="Tên image encoder hoặc cloud Vision model đã tạo kết quả.",
    )
    cv_confidence: float | None = Field(
        default=None,
        description=(
            "Trường legacy giữ tương thích client; luôn None sau khi bỏ "
            "EfficientNet khỏi runtime."
        ),
    )
    recognition_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence nhận diện tổng thể của nhánh tạo kết quả cuối.",
    )
    nutrition: NutritionTotals | None = None
    dishes: list[AnalyzeDish] = Field(
        default_factory=list,
        description="Từng món trong ảnh (món chính + món ăn kèm) kèm gram",
    )
    vision_reasoning: str | None = Field(
        default=None,
        description="Giải thích ngắn do Vision API cung cấp, nếu có",
    )
    staged_dishes: list[str] = Field(
        default_factory=list,
        description="Món Vision mới đã được lưu vào dish_candidates để chờ duyệt",
    )
    missing_items: list[str] = Field(
        default_factory=list,
        description="Item không có trong cả vn_dishes + vn_ingredients",
    )
    matches: list[AnalyzeMatch] = Field(
        default_factory=list,
        description="Các ứng viên khi người dùng nhập tên món.",
    )
    reference_only: bool = Field(
        default=False,
        description="True khi dinh dưỡng là AI estimate, chỉ mang tính tham khảo.",
    )
    warning: str | None = Field(
        default=None,
        max_length=500,
        description="Cảnh báo nguồn hoặc chất lượng kết quả cho UI.",
    )
    error: str | None = None
    recognition_event_id: str | None = Field(
        default=None,
        description="ID metadata-only để feedback liên kết với lượt nhận diện của chính user.",
    )
