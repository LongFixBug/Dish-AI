"""SQLAlchemy ORM models cho FoodAI database.

Tất cả model kế thừa từ Base. Hiện tại:
    - NutritionIngredient: bảng lưu dinh dưỡng per-gram từ USDA/ViFood.

Map với Pydantic schema NutritionPerGram trong schemas/nutrition.py.
"""

from datetime import datetime
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, String, text
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
