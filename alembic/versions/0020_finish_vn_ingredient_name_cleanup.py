"""Remove mixed English translation suffixes from Vietnamese ingredients.

Revision ID: 0020_vn_name_cleanup
Revises: 0019_clean_vn_ingredient_names
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.services.ingredient_names import clean_ingredient_name_batch

revision = "0020_vn_name_cleanup"
down_revision = "0019_clean_vn_ingredient_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    table = sa.table(
        "vn_ingredients",
        sa.column("id", postgresql.UUID(as_uuid=False)),
        sa.column("ingredient_name", sa.String()),
        sa.column("source", sa.String()),
    )
    connection = op.get_bind()
    rows = list(
        connection.execute(
            sa.select(table.c.id, table.c.ingredient_name, table.c.source)
        ).mappings()
    )
    cleaned_names = clean_ingredient_name_batch(
        (str(row["id"]), row["ingredient_name"], row["source"]) for row in rows
    )

    for row in rows:
        connection.execute(
            table.update()
            .where(table.c.id == row["id"])
            .values(ingredient_name=f"__cleaning__{row['id']}")
        )
    for row in rows:
        connection.execute(
            table.update()
            .where(table.c.id == row["id"])
            .values(ingredient_name=cleaned_names[str(row["id"])])
        )


def downgrade() -> None:
    # The original English aliases are not stored in vn_ingredients.
    pass
