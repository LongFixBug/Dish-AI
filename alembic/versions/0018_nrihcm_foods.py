"""Store the NRIHCM nutrition API as a separate source snapshot.

Revision ID: 0018_nrihcm_foods
Revises: 0017_recognition_events
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018_nrihcm_foods"
down_revision = "0017_recognition_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nrihcm_foods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("source_food_id", sa.Integer(), nullable=False),
        sa.Column("food_code", sa.String(length=50), nullable=False),
        sa.Column("name_vi", sa.String(length=500), nullable=False),
        sa.Column("name_en", sa.String(length=500), nullable=True),
        sa.Column("group_name", sa.String(length=300), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("energy_kcal_per_100g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("energy_kj_per_100g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("edible_waste_percent", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("basis_grams", sa.Float(), server_default=sa.text("100.0"), nullable=False),
        sa.Column("water_g_per_100g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("protein_g_per_100g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("fat_g_per_100g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("carbs_g_per_100g", sa.Float(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("nutrition_facts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "source_food_id > 0 AND basis_grams > 0 AND edible_waste_percent >= 0 "
            "AND edible_waste_percent <= 100 AND energy_kcal_per_100g >= 0 "
            "AND energy_kj_per_100g >= 0 AND water_g_per_100g >= 0 "
            "AND protein_g_per_100g >= 0 AND fat_g_per_100g >= 0 "
            "AND carbs_g_per_100g >= 0",
            name="ck_nrihcm_foods_valid_nutrition",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_food_id", name="uq_nrihcm_foods_source_food_id"),
    )
    op.create_index("ix_nrihcm_foods_name_vi", "nrihcm_foods", ["name_vi"])
    op.create_index("ix_nrihcm_foods_group_id", "nrihcm_foods", ["group_id"])
    op.create_index(
        "ix_nrihcm_foods_fetched_at", "nrihcm_foods", ["fetched_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_nrihcm_foods_fetched_at", table_name="nrihcm_foods")
    op.drop_index("ix_nrihcm_foods_group_id", table_name="nrihcm_foods")
    op.drop_index("ix_nrihcm_foods_name_vi", table_name="nrihcm_foods")
    op.drop_table("nrihcm_foods")
