"""Response schemas for dish-level food-image analysis."""

from typing import Literal

from pydantic import BaseModel, Field

from schemas.nutrition import NutritionTotals


class AnalyzeDish(BaseModel):
    """Một món sau khi đã đối chiếu Vision với DB."""

    dish_name: str = Field(description="Tên chuẩn trong DB nếu match, nếu không là tên Vision")
    vision_dish_name: str | None = Field(
        default=None,
        description="Tên gốc Vision trả, chỉ có giá trị khi khác tên chuẩn trong DB",
    )
    grams: float = Field(
        default=0.0, ge=0, description="Khối lượng ước lượng (gram) từ Vision"
    )
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
    portion_source: Literal["vision", "catalog_default", "unknown"] = Field(
        default="unknown",
        description="Nguồn gram hiển thị cho item.",
    )
    serving_label: str | None = Field(
        default=None,
        max_length=30,
        description="Đơn vị khẩu phần Vision nhìn thấy, ví dụ '1 tô' hoặc '1 ly'.",
    )


class AnalyzeResponse(BaseModel):
    """Response cho POST /api/v1/analyze.

    - source='local_consensus': EfficientNet + album cùng resolve về một UUID
      catalog, không cần gọi Vision.
    - source='cv_local': EfficientNet qua solo gate đã calibration, album yếu.
    - source='image_knn': ảnh match album ảnh tham chiếu (SigLIP + Qdrant),
      không cần gọi Vision.
    - source='cv_local_not_found_vision': CV family prior + Qdrant shortlist +
      Vision visual selection.
    - source='vision': Vision nhận diện + lookup vn_dishes/vn_ingredients.
    - nutrition: NutritionTotals (dish-level, không có per-ingredient list).
    - dishes: list món Vision trả (tên + gram).
    - staged_dishes: món mới được lưu ở khu vực chờ duyệt.
    - missing_items: item dùng Vision nhưng staging thất bại.
    """

    dish_name: str | None = Field(default=None, description="Tên món chính / bữa ăn")
    source: Literal[
        "local_consensus",
        "cv_local",
        "vision",
        "cv_local_not_found_vision",
        "image_knn",
    ]
    model_version: str | None = Field(
        default=None,
        description="Version của CV checkpoint hoặc tên cloud Vision model.",
    )
    cv_confidence: float | None = Field(
        default=None, description="Confidence CV local (0-1), None nếu CV disabled"
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
    error: str | None = None
    recognition_event_id: str | None = Field(
        default=None,
        description="ID metadata-only để feedback liên kết với lượt nhận diện của chính user.",
    )
