"""SQLAlchemy models for the Vietnamese ingredient and dish catalogs."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    def __repr__(self) -> str:
        return f"<VnIngredient(id={self.id!r}, name={self.ingredient_name!r})>"


# ── Bảng: Món ăn Việt ─────────────────────────────────────────────────────────


class VnDish(Base):
    """Bảng dinh dưỡng món ăn Việt — dữ liệu từ Viện Dinh Dưỡng.

    Dinh dưỡng được lưu theo khẩu phần của nguồn viện. ``typical_grams`` là
    trọng lượng khẩu phần tương ứng, có provenance rõ ràng để scale theo ảnh.
    Chỉ chứa dữ liệu đã được chấp nhận vào catalog. Kết quả Vision chưa duyệt
    được lưu riêng trong ``dish_candidates``.
    """

    __tablename__ = "vn_dishes"
    __table_args__ = (
        UniqueConstraint("dish_name", name="uq_vn_dishes_dish_name"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        default=lambda: str(uuid4()), server_default=text("gen_random_uuid()"),
    )
    dish_name: Mapped[str] = mapped_column(String(300), nullable=False)

    total_calories: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_protein_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_fat_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_carbs_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))
    total_fiber_g: Mapped[float] = mapped_column(Float, default=0.0, server_default=text("0.0"))

    typical_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    typical_grams_source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="unestimated", server_default=text("'unestimated'")
    )
    typical_grams_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )
    typical_grams_rule: Mapped[str | None] = mapped_column(String(100), nullable=True)

    source: Mapped[str] = mapped_column(String(50), default="vnmeal", server_default=text("'vnmeal'"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    def __repr__(self) -> str:
        return f"<VnDish(id={self.id!r}, name={self.dish_name!r}, source={self.source!r})>"


class DishCandidate(Base):
    """Vision-derived dish awaiting explicit catalog review."""

    __tablename__ = "dish_candidates"
    __table_args__ = (
        UniqueConstraint(
            "dish_name_key",
            name="uq_dish_candidates_dish_name_key",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_dish_candidates_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    dish_name: Mapped[str] = mapped_column(String(300), nullable=False)
    dish_name_key: Mapped[str] = mapped_column(String(300), nullable=False)

    typical_grams: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_calories: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )
    total_protein_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )
    total_fat_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )
    total_carbs_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )
    total_fiber_g: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0, server_default=text("0.0")
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    observation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    approved_dish_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("vn_dishes.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<DishCandidate(id={self.id!r}, name={self.dish_name!r}, "
            f"status={self.status!r})>"
        )
