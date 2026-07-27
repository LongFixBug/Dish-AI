"""Xếp hạng món gợi ý theo khoảng trống dinh dưỡng còn lại trong ngày.

Cố tình dùng số học thay vì LLM: việc chọn món ở đây là bài toán "còn thiếu
bao nhiêu đạm, còn bao nhiêu calo, món nào lấp vừa nhất". Làm bằng phép tính
thì giải thích được cho người dùng, chạy tức thì, không tốn tiền, và test được
từng nhánh. LLM chỉ nên dùng ở tầng diễn đạt, không phải tầng quyết định.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.services.menu_vocabulary import accent_tokens

# Món vượt quá ngần này lần khoảng calo còn lại thì loại thẳng.
CALORIE_HEADROOM = 1.15

# Dưới ngưỡng này coi như đã hết khẩu phần trong ngày, không gợi ý bữa chính.
MIN_MEAL_CALORIES = 120.0

# Tỉ lệ calo đến từ chất béo, dùng cho sở thích "Ít dầu".
LOW_FAT_RATIO = 0.3

PREFERENCE_HIGH_PROTEIN = "Nhiều đạm"
PREFERENCE_LOW_FAT = "Ít dầu"


@dataclass(frozen=True)
class NutritionBudget:
    """Phần dinh dưỡng còn lại của ngày hôm nay."""

    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float

    @property
    def has_room(self) -> bool:
        return self.calories >= MIN_MEAL_CALORIES


@dataclass(frozen=True)
class DishOption:
    """Một món trong catalog, đã quy về khẩu phần chuẩn."""

    dish_name: str
    grams: float
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float


@dataclass(frozen=True)
class ScoredDish:
    """Món đã chấm điểm, kèm lý do đọc được cho người dùng."""

    dish: DishOption
    score: float
    reason: str


def remaining_budget(
    target_calories: float,
    target_protein_g: float,
    target_fat_g: float,
    target_carbs_g: float,
    consumed_calories: float,
    consumed_protein_g: float,
    consumed_fat_g: float,
    consumed_carbs_g: float,
) -> NutritionBudget:
    """Khoảng trống còn lại, không bao giờ âm.

    Ăn vượt mục tiêu thì phần vượt bị cắt về 0 chứ không mang dấu âm: một
    khoảng trống âm sẽ làm mọi phép so khớp bên dưới đảo chiều vô nghĩa.
    """
    return NutritionBudget(
        calories=max(0.0, target_calories - consumed_calories),
        protein_g=max(0.0, target_protein_g - consumed_protein_g),
        fat_g=max(0.0, target_fat_g - consumed_fat_g),
        carbs_g=max(0.0, target_carbs_g - consumed_carbs_g),
    )


def conflicts_with_allergies(dish_name: str, allergies: list[str]) -> bool:
    """True khi tên món có chứa từ khoá dị ứng của người dùng.

    CHỈ soi được cái tên. Món "bún riêu" không nói ra là có mắm tôm, nên đây
    là lưới lọc thô — phía trên phải luôn kèm cảnh báo để người dùng tự kiểm,
    tuyệt đối không được quảng cáo là đã lọc an toàn tuyệt đối.
    """
    dish_tokens = set(accent_tokens(dish_name))
    for allergy in allergies:
        tokens = [token for token in accent_tokens(allergy) if len(token) > 1]
        if tokens and all(token in dish_tokens for token in tokens):
            return True
    return False


def _macro_fit(dish: DishOption, budget: NutritionBudget) -> float:
    """0..1: món lấp đúng phần macro đang thiếu tới mức nào.

    So theo TỈ LỆ chứ không theo số tuyệt đối, để món nhỏ và món to được đánh
    giá công bằng: cái ta hỏi là "món này thiên về đạm hay tinh bột", không
    phải "món này to bao nhiêu".
    """
    gap_total = budget.protein_g + budget.fat_g + budget.carbs_g
    dish_total = dish.protein_g + dish.fat_g + dish.carbs_g
    if gap_total <= 0 or dish_total <= 0:
        return 0.5
    difference = (
        abs(budget.protein_g / gap_total - dish.protein_g / dish_total)
        + abs(budget.fat_g / gap_total - dish.fat_g / dish_total)
        + abs(budget.carbs_g / gap_total - dish.carbs_g / dish_total)
    )
    # difference chạy 0..2; đổi về 1..0.
    return max(0.0, 1 - difference / 2)


def _calorie_fit(dish: DishOption, budget: NutritionBudget) -> float:
    """0..1: khẩu phần món so với calo còn lại.

    Đỉnh điểm khi món chiếm khoảng 70% khoảng còn lại — chừa chỗ cho món phụ
    và đồ uống, thay vì đẩy người dùng ăn kịch trần ngay một bữa.
    """
    if budget.calories <= 0 or dish.calories <= 0:
        return 0.0
    ratio = dish.calories / budget.calories
    return max(0.0, 1 - abs(ratio - 0.7) / 0.7)


def _preference_bonus(dish: DishOption, preferences: list[str]) -> float:
    """Điểm cộng/trừ theo sở thích đã chọn."""
    if dish.calories <= 0:
        return 0.0
    bonus = 0.0
    protein_ratio = dish.protein_g * 4 / dish.calories
    fat_ratio = dish.fat_g * 9 / dish.calories
    if PREFERENCE_HIGH_PROTEIN in preferences:
        bonus += min(0.15, protein_ratio * 0.5)
    if PREFERENCE_LOW_FAT in preferences:
        bonus += 0.1 if fat_ratio <= LOW_FAT_RATIO else -0.15
    return bonus


def _reason_for(dish: DishOption, budget: NutritionBudget) -> str:
    """Một câu ngắn nói vì sao món này được gợi ý.

    Gợi ý nói được lý do thì người dùng tin và bấm; gợi ý im lặng thì bị lướt qua.
    """
    parts = [f"vừa {dish.calories:.0f} kcal trong {budget.calories:.0f} kcal còn lại"]
    if budget.protein_g > 0 and dish.protein_g >= budget.protein_g * 0.3:
        parts.append(f"bù {dish.protein_g:.0f}g đạm bạn đang thiếu")
    elif dish.calories > 0 and dish.fat_g * 9 / dish.calories <= LOW_FAT_RATIO:
        parts.append("ít dầu mỡ")
    return ", ".join(parts).capitalize()


def rank_dishes(
    dishes: list[DishOption],
    budget: NutritionBudget,
    *,
    preferences: list[str] | None = None,
    allergies: list[str] | None = None,
    exclude_names: list[str] | None = None,
    limit: int = 5,
) -> list[ScoredDish]:
    """Chọn ra vài món hợp nhất với khoảng trống còn lại.

    Hết khẩu phần trong ngày thì trả rỗng — thà không gợi ý gì còn hơn đẩy
    người dùng ăn thêm khi họ đã chạm mục tiêu.
    """
    if not budget.has_room:
        return []

    preferences = preferences or []
    allergies = allergies or []
    excluded = {
        " ".join(accent_tokens(name)) for name in (exclude_names or [])
    }

    scored: list[ScoredDish] = []
    for dish in dishes:
        if dish.calories <= 0:
            continue
        if dish.calories > budget.calories * CALORIE_HEADROOM:
            continue
        if " ".join(accent_tokens(dish.dish_name)) in excluded:
            continue
        if conflicts_with_allergies(dish.dish_name, allergies):
            continue
        score = (
            _macro_fit(dish, budget) * 0.5
            + _calorie_fit(dish, budget) * 0.5
            + _preference_bonus(dish, preferences)
        )
        scored.append(
            ScoredDish(dish=dish, score=score, reason=_reason_for(dish, budget))
        )

    # Sắp giảm dần theo điểm; hoà thì tên đứng trước để kết quả ổn định giữa
    # các lần gọi thay vì nhảy lung tung.
    scored.sort(key=lambda item: (-item.score, item.dish.dish_name))
    return scored[:limit]
