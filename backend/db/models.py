"""SQLAlchemy models for the Vietnamese ingredient and dish catalogs."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    literal_column,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
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
    __table_args__ = (
        CheckConstraint(
            "calories_per_g >= 0 AND protein_per_g >= 0 AND fat_per_g >= 0 "
            "AND carbs_per_g >= 0 AND fiber_per_g >= 0",
            name="ck_vn_ingredients_nonnegative_nutrients",
        ),
    )

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
        CheckConstraint(
            "total_calories >= 0 AND total_protein_g >= 0 AND total_fat_g >= 0 "
            "AND total_carbs_g >= 0 AND total_fiber_g >= 0",
            name="ck_vn_dishes_nonnegative_nutrients",
        ),
        CheckConstraint(
            "typical_grams IS NULL OR typical_grams > 0",
            name="ck_vn_dishes_positive_typical_grams",
        ),
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
        CheckConstraint(
            "total_calories >= 0 AND total_protein_g >= 0 AND total_fat_g >= 0 "
            "AND total_carbs_g >= 0 AND total_fiber_g >= 0",
            name="ck_dish_candidates_nonnegative_nutrients",
        ),
        CheckConstraint(
            "typical_grams IS NULL OR typical_grams > 0",
            name="ck_dish_candidates_positive_typical_grams",
        ),
        CheckConstraint(
            "observation_count > 0",
            name="ck_dish_candidates_positive_observation_count",
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


class CatalogCleanupLog(Base):
    """Recoverable journal for every automatic catalog mutation."""

    __tablename__ = "catalog_cleanup_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    record_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    survivor_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    changes: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    qdrant_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class User(Base):
    """Authenticated account used by the mobile application."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default=text("'user'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=func.now(),
    )


class RefreshToken(Base):
    """Rotating refresh token; only its SHA-256 digest is persisted."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class FeedbackSubmission(Base):
    """Consent-backed, reviewable training feedback metadata."""

    __tablename__ = "feedback_submissions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'deleted')",
            name="ck_feedback_submissions_status",
        ),
        CheckConstraint(
            "file_size_bytes > 0 AND width > 0 AND height > 0",
            name="ck_feedback_submissions_image_shape",
        ),
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4()),
        server_default=text("gen_random_uuid()"),
    )
    submitted_by: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    dish_name_slug: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    original_name: Mapped[str] = mapped_column(String(300), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    consent_to_training: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    retention_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


def _canonical_name_expression(column):
    normalized = func.normalize(column, literal_column("NFC"))
    return func.lower(func.regexp_replace(func.btrim(normalized), r"\s+", " ", "g"))


Index(
    "uq_vn_ingredients_name_source_ci",
    _canonical_name_expression(VnIngredient.ingredient_name),
    VnIngredient.source,
    unique=True,
)
Index(
    "uq_vn_dishes_name_ci",
    _canonical_name_expression(VnDish.dish_name),
    unique=True,
)
