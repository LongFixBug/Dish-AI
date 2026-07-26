"""Persist one current nutrition goal per authenticated user.

Revision ID: 0013_nutrition_goals
Revises: 0012_production_hardening
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_nutrition_goals"
down_revision = "0012_production_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_nutrition_goals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("goal", sa.String(length=20), nullable=False),
        sa.Column("current_weight_kg", sa.Float(), nullable=False),
        sa.Column("target_weight_kg", sa.Float(), nullable=False),
        sa.Column("target_days", sa.Integer(), nullable=False),
        sa.Column("algorithm_version", sa.String(length=80), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(), nullable=False),
        sa.Column("result_payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "goal IN ('lose', 'maintain', 'gain')",
            name="ck_user_nutrition_goals_goal",
        ),
        sa.CheckConstraint(
            "current_weight_kg > 0 AND target_weight_kg > 0 AND target_days > 0",
            name="ck_user_nutrition_goals_positive_inputs",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_nutrition_goals_user_id"),
    )
    op.create_index(
        "ix_user_nutrition_goals_user_id",
        "user_nutrition_goals",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_nutrition_goals_user_id", table_name="user_nutrition_goals")
    op.drop_table("user_nutrition_goals")
