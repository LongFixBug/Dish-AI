"""Add reviewed catalog uniqueness and a Vision staging table.

Revision ID: 0002_dish_candidates
Revises: 0001_existing_schema
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_dish_candidates"
down_revision = "0001_existing_schema"
branch_labels = None
depends_on = None


def _create_candidate_table() -> None:
    op.create_table(
        "dish_candidates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("dish_name", sa.String(300), nullable=False),
        sa.Column("dish_name_key", sa.String(300), nullable=False),
        sa.Column("typical_grams", sa.Float()),
        sa.Column("total_calories", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("total_protein_g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("total_fat_g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("total_carbs_g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("total_fiber_g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("observation_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("approved_dish_id", postgresql.UUID(as_uuid=False)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_dish_candidates_status",
        ),
        sa.ForeignKeyConstraint(
            ["approved_dish_id"],
            ["vn_dishes.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dish_name_key", name="uq_dish_candidates_dish_name_key"),
    )


def _move_unreviewed_vision_rows() -> None:
    op.execute("""
        WITH normalized AS (
            SELECT
                *,
                lower(regexp_replace(btrim(dish_name), '[[:space:]]+', ' ', 'g')) AS name_key,
                row_number() OVER (
                    PARTITION BY lower(regexp_replace(btrim(dish_name), '[[:space:]]+', ' ', 'g'))
                    ORDER BY created_at DESC, id
                ) AS row_number,
                count(*) OVER (
                    PARTITION BY lower(regexp_replace(btrim(dish_name), '[[:space:]]+', ' ', 'g'))
                ) AS observations
            FROM vn_dishes
            WHERE source = 'vision_auto'
        )
        INSERT INTO dish_candidates (
            dish_name, dish_name_key, typical_grams,
            total_calories, total_protein_g, total_fat_g,
            total_carbs_g, total_fiber_g, observation_count,
            created_at, last_seen_at
        )
        SELECT
            dish_name, name_key, typical_grams,
            coalesce(total_calories, 0), coalesce(total_protein_g, 0),
            coalesce(total_fat_g, 0), coalesce(total_carbs_g, 0),
            coalesce(total_fiber_g, 0), observations, created_at, created_at
        FROM normalized
        WHERE row_number = 1
    """)
    op.execute("DELETE FROM vn_dishes WHERE source = 'vision_auto'")


def upgrade() -> None:
    """Quarantine unreviewed rows before enforcing catalog uniqueness."""
    _create_candidate_table()
    _move_unreviewed_vision_rows()
    op.execute("""
        DELETE FROM vn_dishes AS duplicate
        USING (
            SELECT id, row_number() OVER (
                PARTITION BY dish_name
                ORDER BY (total_calories > 0) DESC, created_at, id
            ) AS position
            FROM vn_dishes
        ) AS ranked
        WHERE duplicate.id = ranked.id AND ranked.position > 1
    """)
    op.create_unique_constraint(
        "uq_vn_dishes_dish_name",
        "vn_dishes",
        ["dish_name"],
    )


def downgrade() -> None:
    """Restore staged names as legacy Vision rows before dropping staging."""
    op.execute("""
        INSERT INTO vn_dishes (
            dish_name, typical_grams, total_calories, total_protein_g,
            total_fat_g, total_carbs_g, total_fiber_g, source, created_at
        )
        SELECT
            dish_name, typical_grams, total_calories, total_protein_g,
            total_fat_g, total_carbs_g, total_fiber_g, 'vision_auto', created_at
        FROM dish_candidates
        ON CONFLICT (dish_name) DO NOTHING
    """)
    op.drop_constraint("uq_vn_dishes_dish_name", "vn_dishes", type_="unique")
    op.drop_table("dish_candidates")
