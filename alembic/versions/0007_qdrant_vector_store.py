"""Move runtime vector storage from PostgreSQL to Qdrant.

Revision ID: 0007_qdrant_vector_store
Revises: 0006_unify_dish_vectors
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa

revision = "0007_qdrant_vector_store"
down_revision = "0006_unify_dish_vectors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove derived vectors after the Qdrant index has been built."""
    op.drop_column("vn_dishes", "embedding")
    op.drop_column("vn_ingredients", "embedding")
    op.execute("DROP EXTENSION IF EXISTS vector")


def downgrade() -> None:
    """Restore nullable pgvector columns without attempting a data backfill."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "vn_ingredients",
        sa.Column("embedding", Vector(1024), nullable=True),
    )
    op.add_column(
        "vn_dishes",
        sa.Column("embedding", Vector(1024), nullable=True),
    )
