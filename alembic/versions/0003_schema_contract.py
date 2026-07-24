"""Align catalog nullability and comments with the ORM contract.

Revision ID: 0003_schema_contract
Revises: 0002_dish_candidates
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_schema_contract"
down_revision = "0002_dish_candidates"
branch_labels = None
depends_on = None

NUTRITION_COLUMNS = (
    "calories_per_g",
    "protein_per_g",
    "fat_per_g",
    "carbs_per_g",
    "fiber_per_g",
)
DISH_TOTAL_COLUMNS = (
    "total_calories",
    "total_protein_g",
    "total_fat_g",
    "total_carbs_g",
    "total_fiber_g",
)


def _set_nullable(
    table: str,
    columns: tuple[str, ...],
    nullable: bool,
) -> None:
    for column in columns:
        op.alter_column(
            table,
            column,
            existing_type=sa.Float(),
            nullable=nullable,
        )


def upgrade() -> None:
    """Backfill defaults, then make required ORM fields non-nullable."""
    op.execute("""
        UPDATE vn_ingredients SET
            calories_per_g = coalesce(calories_per_g, 0),
            protein_per_g = coalesce(protein_per_g, 0),
            fat_per_g = coalesce(fat_per_g, 0),
            carbs_per_g = coalesce(carbs_per_g, 0),
            fiber_per_g = coalesce(fiber_per_g, 0),
            source = coalesce(source, 'vnfood'),
            item_type = coalesce(item_type, 'ingredient'),
            created_at = coalesce(created_at, now())
    """)
    op.execute("""
        UPDATE vn_dishes SET
            total_calories = coalesce(total_calories, 0),
            total_protein_g = coalesce(total_protein_g, 0),
            total_fat_g = coalesce(total_fat_g, 0),
            total_carbs_g = coalesce(total_carbs_g, 0),
            total_fiber_g = coalesce(total_fiber_g, 0),
            source = coalesce(source, 'vnmeal'),
            created_at = coalesce(created_at, now())
    """)
    _set_nullable("vn_ingredients", NUTRITION_COLUMNS, False)
    _set_nullable("vn_dishes", DISH_TOTAL_COLUMNS, False)

    op.alter_column("vn_ingredients", "source", existing_type=sa.String(50), nullable=False)
    op.alter_column("vn_ingredients", "item_type", existing_type=sa.String(20), nullable=False)
    op.alter_column("vn_ingredients", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.alter_column("vn_dishes", "source", existing_type=sa.String(50), nullable=False)
    op.alter_column("vn_dishes", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.alter_column("vn_ingredients", "id", comment="UUID v4 — khóa chính")
    op.alter_column("vn_ingredients", "ingredient_name", comment="Tên thực phẩm tiếng Việt")
    op.alter_column(
        "vn_ingredients",
        "embedding",
        comment="Vector 1024 chiều (Qwen3-Embedding) cho semantic search",
    )


def downgrade() -> None:
    """Restore the permissive legacy catalog contract."""
    op.alter_column("vn_ingredients", "id", comment=None)
    op.alter_column("vn_ingredients", "ingredient_name", comment=None)
    op.alter_column("vn_ingredients", "embedding", comment=None)

    op.alter_column("vn_dishes", "created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("vn_dishes", "source", existing_type=sa.String(50), nullable=True)
    op.alter_column("vn_ingredients", "created_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.alter_column("vn_ingredients", "item_type", existing_type=sa.String(20), nullable=True)
    op.alter_column("vn_ingredients", "source", existing_type=sa.String(50), nullable=True)
    _set_nullable("vn_dishes", DISH_TOTAL_COLUMNS, True)
    _set_nullable("vn_ingredients", NUTRITION_COLUMNS, True)
