"""Add versioned Vietnamese nutrition reference rows.

Revision ID: 0014_nutrition_reference_targets
Revises: 0013_nutrition_goals
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_nutrition_reference_targets"
down_revision = "0013_nutrition_goals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nutrition_reference_targets",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("standard", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_endpoint", sa.String(length=500), nullable=False),
        sa.Column("source_fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("age_group_id", sa.String(length=100), nullable=False),
        sa.Column("age_group_name", sa.String(length=100), nullable=False),
        sa.Column("sex", sa.String(length=20), nullable=False),
        sa.Column("labor_level", sa.String(length=30), nullable=False),
        sa.Column("physiological_condition_id", sa.String(length=100), nullable=True),
        sa.Column("physiological_condition_name", sa.String(length=150), nullable=True),
        sa.Column("section", sa.String(length=150), nullable=False),
        sa.Column("nutrient_code", sa.String(length=100), nullable=False),
        sa.Column("nutrient_name", sa.String(length=200), nullable=False),
        sa.Column("unit", sa.String(length=100), nullable=False),
        sa.Column("value_text", sa.String(length=300), nullable=False),
        sa.Column("value_min", sa.Float(), nullable=True),
        sa.Column("value_max", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "standard",
            "age_group_id",
            "sex",
            "labor_level",
            "physiological_condition_id",
            "nutrient_code",
            "value_text",
            name="uq_nutrition_reference_target_variant",
        ),
    )
    op.create_index(
        "ix_nutrition_reference_targets_lookup",
        "nutrition_reference_targets",
        [
            "standard",
            "age_group_id",
            "sex",
            "labor_level",
            "physiological_condition_id",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_reference_targets_lookup",
        table_name="nutrition_reference_targets",
    )
    op.drop_table("nutrition_reference_targets")
