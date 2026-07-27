"""Pydantic cho tính năng gợi ý món."""

from pydantic import BaseModel, Field


class SuggestionRequest(BaseModel):
    """Phần đã ăn hôm nay do app gửi lên.

    Nhật ký nằm trên máy người dùng chứ không ở máy chủ, nên phần đã ăn phải
    do app khai; máy chủ chỉ giữ mục tiêu dinh dưỡng.
    """

    consumed_calories: float = Field(default=0, ge=0, le=20000)
    consumed_protein_g: float = Field(default=0, ge=0, le=2000)
    consumed_fat_g: float = Field(default=0, ge=0, le=2000)
    consumed_carbs_g: float = Field(default=0, ge=0, le=3000)
    exclude_dish_names: list[str] = Field(default_factory=list, max_length=50)
    allergies: list[str] = Field(default_factory=list, max_length=30)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=5, ge=1, le=20)


class SuggestedDish(BaseModel):
    """Một món được gợi ý, kèm lý do đọc được."""

    dish_name: str
    grams: float
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    reason: str
    score: float


class RemainingNutrition(BaseModel):
    """Khoảng trống còn lại của ngày."""

    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


class SuggestionResponse(BaseModel):
    """Kết quả gợi ý.

    ``allergy_filter_is_partial`` luôn bật khi người dùng khai dị ứng: bộ lọc
    chỉ soi được TÊN món, không biết thành phần bên trong, nên app phải nói rõ
    điều đó thay vì để người dùng tin là đã an toàn tuyệt đối.
    """

    remaining: RemainingNutrition
    suggestions: list[SuggestedDish]
    allergy_filter_is_partial: bool = False
