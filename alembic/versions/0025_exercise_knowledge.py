"""Add review-gated exercise knowledge and general workout templates.

Revision ID: 0025_exercise_knowledge
Revises: 0024_feedback_review_comments
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0025_exercise_knowledge"
down_revision = "0024_feedback_review_comments"
branch_labels = None
depends_on = None


_STATUS = "status IN ('pending', 'approved', 'rejected', 'retired')"


def upgrade() -> None:
    op.create_table(
        "exercise_knowledge_documents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("publisher", sa.String(length=300), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("license_note", sa.String(length=500), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False, server_default=sa.text("'en'")),
        sa.Column("version", sa.String(length=100), nullable=False, server_default=sa.text("'current'")),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("source_url", "version", name="uq_exercise_knowledge_document_source"),
        sa.CheckConstraint(_STATUS, name="ck_exercise_knowledge_document_status"),
    )
    op.create_table(
        "exercise_knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("heading", sa.String(length=300), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False, server_default=sa.text("'en'")),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["exercise_knowledge_documents.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_exercise_knowledge_chunk_ordinal"),
        sa.CheckConstraint("ordinal >= 0", name="ck_exercise_knowledge_chunk_ordinal"),
    )
    op.create_index("ix_exercise_knowledge_chunks_document_id", "exercise_knowledge_chunks", ["document_id"])
    op.create_table(
        "exercise_cards",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name_vi", sa.String(length=300), nullable=False),
        sa.Column("name_en", sa.String(length=300), nullable=False),
        sa.Column("primary_muscles", postgresql.JSONB(), nullable=False),
        sa.Column("secondary_muscles", postgresql.JSONB(), nullable=False),
        sa.Column("equipment", postgresql.JSONB(), nullable=False),
        sa.Column("level", sa.String(length=30), nullable=False),
        sa.Column("cues", postgresql.JSONB(), nullable=False),
        sa.Column("common_mistakes", postgresql.JSONB(), nullable=False),
        sa.Column("safety_note", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["exercise_knowledge_documents.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("slug", name="uq_exercise_cards_slug"),
        sa.CheckConstraint(_STATUS, name="ck_exercise_cards_status"),
    )
    op.create_index("ix_exercise_cards_document_id", "exercise_cards", ["document_id"])
    op.create_table(
        "workout_templates",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name_vi", sa.String(length=300), nullable=False),
        sa.Column("name_en", sa.String(length=300), nullable=False),
        sa.Column("training_days", sa.Integer(), nullable=False),
        sa.Column("schedule", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["exercise_knowledge_documents.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("slug", name="uq_workout_templates_slug"),
        sa.CheckConstraint("training_days >= 2 AND training_days <= 5", name="ck_workout_templates_days"),
        sa.CheckConstraint(_STATUS, name="ck_workout_templates_status"),
    )
    op.create_index("ix_workout_templates_document_id", "workout_templates", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_workout_templates_document_id", table_name="workout_templates")
    op.drop_table("workout_templates")
    op.drop_index("ix_exercise_cards_document_id", table_name="exercise_cards")
    op.drop_table("exercise_cards")
    op.drop_index("ix_exercise_knowledge_chunks_document_id", table_name="exercise_knowledge_chunks")
    op.drop_table("exercise_knowledge_chunks")
    op.drop_table("exercise_knowledge_documents")
