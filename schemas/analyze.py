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


class AnalyzeResponse(BaseModel):
    """Response cho POST /api/v1/analyze.

    - source='cv_local': CV local conf cao + DB có đủ nutrition và khẩu phần chuẩn.
    - source='vision': Vision nhận diện + lookup vn_dishes/vn_ingredients.
    - nutrition: NutritionTotals (dish-level, không có per-ingredient list).
    - dishes: list món Vision trả (tên + gram).
    - staged_dishes: món mới được lưu ở khu vực chờ duyệt.
    - missing_items: item dùng Vision nhưng staging thất bại.
    """

    dish_name: str | None = Field(default=None, description="Tên món chính / bữa ăn")
    source: Literal["cv_local", "vision", "cv_local_not_found_vision"]
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
    auto_added_dishes: list[str] = Field(
        default_factory=list,
        description="Deprecated compatibility field; always empty",
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
