"""Restore serving-total nutrition semantics for institute dishes.

Revision ID: 0005_restore_serving_totals
Revises: 0004_dish_nutrition_basis
"""

from alembic import op

revision = "0005_restore_serving_totals"
down_revision = "0004_dish_nutrition_basis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Restore the source API's per-dish serving-total column names."""
    renames = (
        ("calories_per_100g", "total_calories"),
        ("protein_per_100g", "total_protein_g"),
        ("fat_per_100g", "total_fat_g"),
        ("carbs_per_100g", "total_carbs_g"),
        ("fiber_per_100g", "total_fiber_g"),
    )
    for old_name, new_name in renames:
        op.alter_column("vn_dishes", old_name, new_column_name=new_name)


def downgrade() -> None:
    """Reapply the per-100 g naming used by revision 0004."""
    renames = (
        ("total_calories", "calories_per_100g"),
        ("total_protein_g", "protein_per_100g"),
        ("total_fat_g", "fat_per_100g"),
        ("total_carbs_g", "carbs_per_100g"),
        ("total_fiber_g", "fiber_per_100g"),
    )
    for old_name, new_name in renames:
        op.alter_column("vn_dishes", old_name, new_column_name=new_name)
