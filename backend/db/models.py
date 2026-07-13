"""SQLAlchemy ORM models cho FoodAI database.

Tất cả model kế thừa từ Base. Hiện tại:
    - NutritionIngredient: bảng lưu dinh dưỡng per-gram từ USDA/ViFood.

Map với Pydantic schema NutritionPerGram trong schemas/nutrition.py.
"""

from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class cho tất cả ORM models."""
    pass


class NutritionIngredient(Base):
    """Bảng dinh dưỡng trên 1 gram của từng ingredient.

    Dữ liệu nguồn: USDA FoodData Central + Vietnam Food Composition Table.
    Mỗi hàng = 1 ingredient với giá trị dinh dưỡng per gram.
    """

    __tablename__ = "nutrition_ingredients"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
        comment="UUID v4 — khóa chính",
    )

    ingredient_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Tên thực phẩm, VD: 'Strawberries, raw'",
    )

    calories_per_g: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=text("0.0"),
        comment="Calo trên 1 gram (kcal/g)",
    )

    protein_per_g: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=text("0.0"),
        comment="Đạm trên 1 gram (g/g)",
    )

    fat_per_g: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=text("0.0"),
        comment="Chất béo trên 1 gram (g/g)",
    )

    carbs_per_g: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=text("0.0"),
        comment="Carbohydrate trên 1 gram (g/g)",
    )

    fiber_per_g: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        server_default=text("0.0"),
        comment="Chất xơ trên 1 gram (g/g)",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="unknown",
        server_default=text("'unknown'"),
        comment="Nguồn dữ liệu: 'usda', 'vnfood', 'manual'",
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024),
        nullable=True,
        comment="Vector embedding 1024 chiều (từ Qwen3-Embedding)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        comment="Thời điểm insert vào DB",
    )

    def __repr__(self) -> str:
        return (
            f"<NutritionIngredient(id={self.id!r}, "
            f"name={self.ingredient_name!r}, source={self.source!r})>"
        )


class Dish(Base):
    """Bảng danh sách món ăn.

    Mỗi hàng = 1 món ăn (cơm sườn, phở bò, bún chả...).
    Món ăn được ghép từ nhiều ingredient qua bảng dish_ingredients.
    """

    __tablename__ = "dishes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
        comment="UUID v4 — khóa chính",
    )

    dish_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        unique=True,
        comment="Tên món ăn, VD: 'cơm sườn', 'phở bò'",
    )

    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Mô tả ngắn về món ăn (tùy chọn)",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        comment="draft | verified — nền tảng trust-score pha 2",
    )

    contributor_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="UUID do client gen (anonymous, chưa có auth)",
    )

    usage_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="Số lần món được reuse — tăng dần, nền tảng confidence pha 2",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        comment="Thời điểm tạo món",
    )

    def __repr__(self) -> str:
        return f"<Dish(id={self.id!r}, name={self.dish_name!r}, status={self.status!r})>"


class DishIngredient(Base):
    """Bảng trung gian many-to-many: món ăn ↔ nguyên liệu.

    Mỗi hàng = 1 cặp (món, nguyên liệu) kèm số gram.
    Đây là "công thức" định nghĩa món gồm những gì và bao nhiêu.
    """

    __tablename__ = "dish_ingredients"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
        comment="UUID v4 — khóa chính",
    )

    dish_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("dishes.id", ondelete="CASCADE"),
        nullable=False,
        comment="Khóa ngoại tới dishes.id",
    )

    ingredient_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("nutrition_ingredients.id", ondelete="CASCADE"),
        nullable=False,
        comment="Khóa ngoại tới nutrition_ingredients.id",
    )

    grams: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Số gram nguyên liệu này dùng trong món",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        comment="Thời điểm tạo dòng",
    )

    def __repr__(self) -> str:
        return (
            f"<DishIngredient(dish_id={self.dish_id!r}, "
            f"ingredient_id={self.ingredient_id!r}, grams={self.grams!r})>"
        )


class ConversionRate(Base):
    """Bảng chuyển đổi đơn vị thể tích → gram theo từng nguyên liệu.

    VD: 1 mL sữa ≈ 1.03 g, 1 mL dầu ≈ 0.92 g.
    ingredient_id = NULL → rate chung (fallback nước = 1.0).
    """

    __tablename__ = "conversion_rates"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
        comment="UUID v4 — khóa chính",
    )

    ingredient_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("nutrition_ingredients.id", ondelete="CASCADE"),
        nullable=True,
        comment="NULL = rate chung fallback (nước). Có giá trị = rate riêng cho nguyên liệu đó",
    )

    unit_name: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Tên đơn vị, VD: 'ml'",
    )

    grams_per_unit: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Số gram tương đương 1 đơn vị, VD: 1 ml sữa = 1.03 g",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        comment="Thời điểm tạo",
    )

    def __repr__(self) -> str:
        return (
            f"<ConversionRate(ingredient_id={self.ingredient_id!r}, "
            f"unit={self.unit_name!r}, grams_per_unit={self.grams_per_unit!r})>"
        )
