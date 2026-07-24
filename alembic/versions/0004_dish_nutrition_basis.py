"""Store institute dish nutrition explicitly per 100 g.

Revision ID: 0004_dish_nutrition_basis
Revises: 0003_schema_contract
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_dish_nutrition_basis"
down_revision = "0003_schema_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Clarify nutrition units and retain serving-size provenance."""
    renames = (
        ("total_calories", "calories_per_100g"),
        ("total_protein_g", "protein_per_100g"),
        ("total_fat_g", "fat_per_100g"),
        ("total_carbs_g", "carbs_per_100g"),
        ("total_fiber_g", "fiber_per_100g"),
    )
    for old_name, new_name in renames:
        op.alter_column("vn_dishes", old_name, new_column_name=new_name)

    op.add_column(
        "vn_dishes",
        sa.Column(
            "typical_grams_source",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'unestimated'"),
        ),
    )
    op.add_column(
        "vn_dishes",
        sa.Column(
            "typical_grams_confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
    )
    op.add_column("vn_dishes", sa.Column("typical_grams_rule", sa.String(100)))
    op.execute("""
        UPDATE vn_dishes
        SET typical_grams_source = CASE
                WHEN typical_grams IS NULL THEN 'unestimated'
                ELSE 'legacy_keyword_rebuild'
            END,
            typical_grams_confidence = CASE
                WHEN typical_grams IS NULL THEN 0.0
                ELSE 0.2
            END
    """)
    op.create_check_constraint(
        "ck_vn_dishes_typical_grams_confidence",
        "vn_dishes",
        "typical_grams_confidence >= 0 AND typical_grams_confidence <= 1",
    )


def downgrade() -> None:
    """Restore legacy ambiguous dish nutrition column names."""
    op.drop_constraint(
        "ck_vn_dishes_typical_grams_confidence",
        "vn_dishes",
        type_="check",
    )
    op.drop_column("vn_dishes", "typical_grams_rule")
    op.drop_column("vn_dishes", "typical_grams_confidence")
    op.drop_column("vn_dishes", "typical_grams_source")

    renames = (
        ("calories_per_100g", "total_calories"),
        ("protein_per_100g", "total_protein_g"),
        ("fat_per_100g", "total_fat_g"),
        ("carbs_per_100g", "total_carbs_g"),
        ("fiber_per_100g", "total_fiber_g"),
    )
    for old_name, new_name in renames:
        op.alter_column("vn_dishes", old_name, new_column_name=new_name)
