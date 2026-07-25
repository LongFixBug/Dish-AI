"""Add durable, consent-backed feedback metadata.

Revision ID: 0011_feedback
Revises: 0010_auth
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_feedback"
down_revision = "0010_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback_submissions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("dish_name_slug", sa.String(length=300), nullable=False),
        sa.Column("original_name", sa.String(length=300), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("content_type", sa.String(length=50), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("consent_to_training", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND width > 0 AND height > 0",
            name="ck_feedback_submissions_image_shape",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'deleted')",
            name="ck_feedback_submissions_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_key"),
    )
    op.create_index(
        "ix_feedback_submissions_dish_name_slug",
        "feedback_submissions",
        ["dish_name_slug"],
    )
    op.create_index(
        "ix_feedback_submissions_retention_status",
        "feedback_submissions",
        ["retention_until", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_feedback_submissions_retention_status",
        table_name="feedback_submissions",
    )
    op.drop_index(
        "ix_feedback_submissions_dish_name_slug",
        table_name="feedback_submissions",
    )
    op.drop_table("feedback_submissions")
