"""Add recognition decision telemetry and feedback correlation.

Revision ID: 0017_recognition_events
Revises: 0016_meal_logs
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_recognition_events"
down_revision = "0016_meal_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recognition_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("submitted_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("final_dish_name", sa.String(length=300), nullable=True),
        sa.Column("cv_dish_name", sa.String(length=300), nullable=True),
        sa.Column("cv_confidence", sa.Float(), nullable=True),
        sa.Column("album_dish_name", sa.String(length=300), nullable=True),
        sa.Column("album_score", sa.Float(), nullable=True),
        sa.Column("album_margin", sa.Float(), nullable=True),
        sa.Column("model_version", sa.String(length=300), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cv_confidence IS NULL OR (cv_confidence >= 0 AND cv_confidence <= 1)",
            name="ck_recognition_events_cv_confidence",
        ),
        sa.CheckConstraint(
            "album_score IS NULL OR (album_score >= 0 AND album_score <= 1)",
            name="ck_recognition_events_album_score",
        ),
        sa.CheckConstraint(
            "album_margin IS NULL OR album_margin >= 0",
            name="ck_recognition_events_album_margin",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by"],
            ["users.id"],
            name="fk_recognition_events_submitted_by_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recognition_events_submitted_by", "recognition_events", ["submitted_by"]
    )
    op.create_index(
        "ix_recognition_events_source_created",
        "recognition_events",
        ["source", "created_at"],
    )
    op.add_column(
        "feedback_submissions",
        sa.Column("recognition_event_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_index(
        "ix_feedback_submissions_recognition_event_id",
        "feedback_submissions",
        ["recognition_event_id"],
    )
    op.create_foreign_key(
        "fk_feedback_submissions_recognition_event",
        "feedback_submissions",
        "recognition_events",
        ["recognition_event_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_feedback_submissions_recognition_event",
        "feedback_submissions",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_feedback_submissions_recognition_event_id",
        table_name="feedback_submissions",
    )
    op.drop_column("feedback_submissions", "recognition_event_id")
    op.drop_index("ix_recognition_events_source_created", table_name="recognition_events")
    op.drop_index("ix_recognition_events_submitted_by", table_name="recognition_events")
    op.drop_table("recognition_events")
