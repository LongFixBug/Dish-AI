"""Sync descriptive comments for the feedback review columns.

Revision ID: 0024_feedback_review_comments
Revises: 0023_feedback_review_workflow
"""

from alembic import op


revision = "0024_feedback_review_comments"
down_revision = "0023_feedback_review_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "feedback_submissions",
        "capture_source",
        comment="Nguồn ảnh: camera thật hoặc file upload; chỉ camera tính vào gate ML.",
    )
    op.alter_column(
        "feedback_submissions",
        "reviewed_dish_slug",
        comment="Nhãn canonical do reviewer xác nhận; không tin label người gửi.",
    )


def downgrade() -> None:
    op.alter_column("feedback_submissions", "reviewed_dish_slug", comment=None)
    op.alter_column("feedback_submissions", "capture_source", comment=None)
