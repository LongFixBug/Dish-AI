"""Add user-owned meal snapshots for journal sync and chatbot tools.

Revision ID: 0016_meal_logs
Revises: 0015_google_identities
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_meal_logs"
down_revision = "0015_google_identities"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meal_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("client_entry_id", sa.String(length=200), nullable=False),
        sa.Column("eaten_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meal_type", sa.String(length=20), nullable=False),
        sa.Column("dish_name", sa.String(length=300), nullable=False),
        sa.Column("total_grams", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("calories", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("protein_g", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("fat_g", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("carbs_g", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column("fiber_g", sa.Float(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "source",
            sa.String(length=30),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column("analyze_source", sa.String(length=50), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
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
            "meal_type IN ('breakfast', 'lunch', 'dinner', 'snack')",
            name="ck_meal_logs_meal_type",
        ),
        sa.CheckConstraint(
            "total_grams >= 0 AND calories >= 0 AND protein_g >= 0 "
            "AND fat_g >= 0 AND carbs_g >= 0 AND fiber_g >= 0",
            name="ck_meal_logs_nonnegative_nutrients",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "client_entry_id",
            name="uq_meal_logs_user_client_entry",
        ),
    )
    op.create_index("ix_meal_logs_user_id", "meal_logs", ["user_id"])
    op.create_index(
        "ix_meal_logs_user_eaten_at",
        "meal_logs",
        ["user_id", "eaten_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_meal_logs_user_eaten_at", table_name="meal_logs")
    op.drop_index("ix_meal_logs_user_id", table_name="meal_logs")
    op.drop_table("meal_logs")
