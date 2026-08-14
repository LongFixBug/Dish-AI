"""Add the four explicitly reviewed demo canonical dish names.

The nutrition values are copied from the existing Institute rows.  A fresh
database runs this migration before the JSON seed, so ``recreate_vn_dishes``
re-applies the same idempotent copies after seeding.
"""

from alembic import op
import sqlalchemy as sa

revision = "0022_demo_canonical_dishes"
down_revision = "0021_recognition_telemetry"
branch_labels = None
depends_on = None

DEMO_CANONICAL_COPIES = (
    ("Bánh canh thịt heo", "Bánh canh"),
    ("Canh cá lóc (Các quả) nấu chua", "Canh chua"),
    ("Bún nem nướng", "Bún thịt nướng"),
    ("Cá chày kho", "Cá kho tộ"),
)


def _copy_canonical_row(source_name: str, target_name: str) -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO vn_dishes (
                id,
                dish_name,
                total_calories,
                total_protein_g,
                total_fat_g,
                total_carbs_g,
                total_fiber_g,
                typical_grams,
                typical_grams_source,
                typical_grams_confidence,
                typical_grams_rule,
                source
            )
            SELECT
                gen_random_uuid(),
                :target_name,
                source_row.total_calories,
                source_row.total_protein_g,
                source_row.total_fat_g,
                source_row.total_carbs_g,
                source_row.total_fiber_g,
                source_row.typical_grams,
                source_row.typical_grams_source,
                source_row.typical_grams_confidence,
                source_row.typical_grams_rule,
                'demo_alias'
            FROM vn_dishes AS source_row
            WHERE source_row.dish_name = :source_name
              AND NOT EXISTS (
                  SELECT 1
                  FROM vn_dishes AS existing
                  WHERE lower(existing.dish_name) = lower(:target_name)
              )
            """
        ).bindparams(source_name=source_name, target_name=target_name)
    )


def upgrade() -> None:
    """Create canonical demo aliases only when their source row exists."""
    for source_name, target_name in DEMO_CANONICAL_COPIES:
        _copy_canonical_row(source_name, target_name)


def downgrade() -> None:
    """Remove only rows created by this demo-only migration."""
    for _, target_name in DEMO_CANONICAL_COPIES:
        op.execute(
            sa.text(
                """
                DELETE FROM vn_dishes
                WHERE dish_name = :target_name AND source = 'demo_alias'
                """
            ).bindparams(target_name=target_name)
        )
