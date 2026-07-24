"""Create the original ingredient and dish catalogs.

Revision ID: 0001_existing_schema
Revises: None
"""

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_existing_schema"
down_revision = None
branch_labels = None
depends_on = None


VN_NORM_SQL = """
CREATE OR REPLACE FUNCTION vn_norm(input_text TEXT)
RETURNS TEXT
LANGUAGE SQL
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
    SELECT translate(
        lower(input_text),
        'àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ',
        'aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd'
    );
$$
"""


def upgrade() -> None:
    """Create a complete schema for new installations."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(VN_NORM_SQL)
    op.create_table(
        "vn_ingredients",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("ingredient_name", sa.String(500), nullable=False),
        sa.Column("calories_per_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("protein_per_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("fat_per_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("carbs_per_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("fiber_per_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("source", sa.String(50), server_default=sa.text("'vnfood'")),
        sa.Column("item_type", sa.String(20), server_default=sa.text("'ingredient'")),
        sa.Column("embedding", Vector(1024)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "vn_dishes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("dish_name", sa.String(300), nullable=False),
        sa.Column("total_calories", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("total_protein_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("total_fat_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("total_carbs_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("total_fiber_g", sa.Float(), server_default=sa.text("0.0")),
        sa.Column("typical_grams", sa.Float()),
        sa.Column("source", sa.String(50), server_default=sa.text("'vnmeal'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Remove the catalogs while leaving the shared vector extension installed."""
    op.drop_table("vn_dishes")
    op.drop_table("vn_ingredients")
    op.execute("DROP FUNCTION IF EXISTS vn_norm(TEXT)")
