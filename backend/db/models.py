"""SQLAlchemy ORM models cho FoodAI database.

Phiên bản Jul 23: chỉ giữ 2 bảng dữ liệu Việt Nam:
    - VnIngredient: dinh dưỡng nguyên liệu / đồ uống (per-gram) — Viện DD.
    - VnDish: dinh dưỡng món ăn (total + typical_grams) — Viện DD.

Đã bỏ: NutritionIngredient (USDA), Dish/DishIngredient (user-recipe),
ConversionRate (mL→g) — flow analyze giờ chỉ dùng vn_dishes + vn_ingredients.
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


# ── Bảng: Nguyên liệu Việt ────────────────────────────────────────────────────


class VnIngredient(Base):
    """Bảng dinh dưỡng nguyên liệu Việt Nam (per-gram sẵn).

    Dữ liệu nguồn: Viện Dinh Dưỡng VN (viendinhduong.vn) — 853 thực phẩm.
    Dùng cho: món ăn kèm / đồ uống trong ảnh (sữa hộp, trà đá, xoài...).
    """

    __tablename__ = "vn_ingredients"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
        comment="UUID v4 — khóa chính",
    )

    ingredient_name: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Tên thực phẩm tiếng Việt"
    )
    calories_per_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    protein_per_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    fat_per_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    carbs_per_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    fiber_per_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))

    source: Mapped[str] = mapped_column(String(50), default="vnfood", server_default=text("'vnfood'"))
    item_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ingredient", server_default=text("'ingredient'")
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024), nullable=True,
        comment="Vector 1024 chiều (Qwen3-Embedding) cho semantic search",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    def __repr__(self) -> str:
        return f"<VnIngredient(id={self.id!r}, name={self.ingredient_name!r})>"


# ── Bảng: Món ăn Việt ─────────────────────────────────────────────────────────


class VnDish(Base):
    """Bảng dinh dưỡng món ăn Việt — dữ liệu từ Viện Dinh Dưỡng.

    Giá trị RAW từ API (per-serving). typical_grams = trọng lượng 1 khẩu phần:
      - Có → tính được per-gram chính xác → scale theo gram Vision.
      - NULL → giữ RAW, KHÔNG scale theo gram ảnh (tránh sai số).
    Món mới Vision nhận (chưa có DB) → INSERT source='vision_auto' cùng nutrition Vision.
    """

    __tablename__ = "vn_dishes"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        default=lambda: str(uuid4()), server_default=text("gen_random_uuid()"),
    )
    dish_name: Mapped[str] = mapped_column(String(200), nullable=False)

    total_calories: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_protein_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_fat_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_carbs_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_fiber_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))

    typical_grams: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="vnmeal", server_default=text("'vnmeal'"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    def __repr__(self) -> str:
        return f"<VnDish(id={self.id!r}, name={self.dish_name!r}, source={self.source!r})>"
