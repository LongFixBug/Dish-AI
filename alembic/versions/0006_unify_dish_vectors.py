"""Store dish embeddings in PostgreSQL beside their catalog rows.

Revision ID: 0006_unify_dish_vectors
Revises: 0005_restore_serving_totals
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa

revision = "0006_unify_dish_vectors"
down_revision = "0005_restore_serving_totals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add a nullable vector; exact lookup remains available until backfill."""
    op.add_column(
        "vn_dishes",
        sa.Column(
            "embedding",
            Vector(1024),
            nullable=True,
            comment="Vector 1024 chiều (Qwen3-Embedding) cho semantic dish lookup",
        ),
    )


def downgrade() -> None:
    """Remove the dish vector column when rolling back the refactor."""
    op.drop_column("vn_dishes", "embedding")
