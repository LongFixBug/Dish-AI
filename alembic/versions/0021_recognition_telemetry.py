"""Persist raw local candidates and the reason an image deferred to Vision.

Revision ID: 0021_recognition_telemetry
Revises: 0020_vn_name_cleanup
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_recognition_telemetry"
down_revision = "0020_vn_name_cleanup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "recognition_events",
        sa.Column("cv_top1_name", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "recognition_events",
        sa.Column("cv_top2_name", sa.String(length=300), nullable=True),
    )
    op.add_column(
        "recognition_events",
        sa.Column("cv_top2_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "recognition_events",
        sa.Column("fusion_reason", sa.String(length=50), nullable=True),
    )
    op.create_check_constraint(
        "ck_recognition_events_cv_top2_confidence",
        "recognition_events",
        "cv_top2_confidence IS NULL OR (cv_top2_confidence >= 0 AND cv_top2_confidence <= 1)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_recognition_events_cv_top2_confidence",
        "recognition_events",
        type_="check",
    )
    op.drop_column("recognition_events", "fusion_reason")
    op.drop_column("recognition_events", "cv_top2_confidence")
    op.drop_column("recognition_events", "cv_top2_name")
    op.drop_column("recognition_events", "cv_top1_name")
