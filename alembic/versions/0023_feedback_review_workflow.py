"""Add camera provenance and explicit reviewer label for feedback training rows.

Revision ID: 0023_feedback_review_workflow
Revises: 0022_demo_canonical_dishes
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0023_feedback_review_workflow"
down_revision = "0022_demo_canonical_dishes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "feedback_submissions",
        sa.Column(
            "capture_source",
            sa.String(length=20),
            server_default=sa.text("'upload'"),
            nullable=False,
            comment="Nguồn ảnh: camera thật hoặc file upload; chỉ camera tính vào gate ML.",
        ),
    )
    op.add_column(
        "feedback_submissions",
        sa.Column(
            "reviewed_dish_slug",
            sa.String(length=300),
            nullable=True,
            comment="Nhãn canonical do reviewer xác nhận; không tin label người gửi.",
        ),
    )
    op.add_column(
        "feedback_submissions",
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.add_column(
        "feedback_submissions",
        sa.Column("reviewer_note", sa.String(length=500), nullable=True),
    )
    op.create_check_constraint(
        "ck_feedback_submissions_capture_source",
        "feedback_submissions",
        "capture_source IN ('camera', 'upload')",
    )
    op.create_index(
        "ix_feedback_submissions_capture_source_status",
        "feedback_submissions",
        ["capture_source", "status"],
    )
    op.create_index(
        "ix_feedback_submissions_reviewed_dish_slug",
        "feedback_submissions",
        ["reviewed_dish_slug"],
    )
    op.create_index(
        "ix_feedback_submissions_reviewed_by",
        "feedback_submissions",
        ["reviewed_by"],
    )
    op.create_foreign_key(
        "fk_feedback_submissions_reviewed_by_users",
        "feedback_submissions",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_feedback_submissions_reviewed_by_users",
        "feedback_submissions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_feedback_submissions_reviewed_by",
        table_name="feedback_submissions",
    )
    op.drop_index(
        "ix_feedback_submissions_reviewed_dish_slug",
        table_name="feedback_submissions",
    )
    op.drop_index(
        "ix_feedback_submissions_capture_source_status",
        table_name="feedback_submissions",
    )
    op.drop_constraint(
        "ck_feedback_submissions_capture_source",
        "feedback_submissions",
        type_="check",
    )
    op.drop_column("feedback_submissions", "reviewer_note")
    op.drop_column("feedback_submissions", "reviewed_by")
    op.drop_column("feedback_submissions", "reviewed_dish_slug")
    op.drop_column("feedback_submissions", "capture_source")
