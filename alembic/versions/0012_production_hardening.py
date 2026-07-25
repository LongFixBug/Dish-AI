"""Add lifecycle indexes and feedback ownership integrity.

Revision ID: 0012_production_hardening
Revises: 0011_feedback
"""

from alembic import op

revision = "0012_production_hardening"
down_revision = "0011_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_refresh_tokens_expires_at",
        "refresh_tokens",
        ["expires_at"],
    )
    op.create_index(
        "ix_feedback_submissions_submitted_by",
        "feedback_submissions",
        ["submitted_by"],
    )
    op.create_foreign_key(
        "fk_feedback_submissions_submitted_by_users",
        "feedback_submissions",
        "users",
        ["submitted_by"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_feedback_submissions_submitted_by_users",
        "feedback_submissions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_feedback_submissions_submitted_by",
        table_name="feedback_submissions",
    )
    op.drop_index(
        "ix_refresh_tokens_expires_at",
        table_name="refresh_tokens",
    )
