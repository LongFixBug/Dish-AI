"""Add nutrition basis grams and clean English ingredient suffixes.

Revision ID: 0019_clean_vn_ingredient_names
Revises: 0018_nrihcm_foods
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from backend.services.ingredient_names import clean_ingredient_name_batch

revision = "0019_clean_vn_ingredient_names"
down_revision = "0018_nrihcm_foods"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vn_ingredients",
        sa.Column(
            "gram",
            sa.Float(),
            server_default=sa.text("100.0"),
            nullable=False,
            comment="Khối lượng cơ sở của dữ liệu dinh dưỡng, theo nguồn là 100g ăn được",
        ),
    )
    op.create_check_constraint(
        "ck_vn_ingredients_positive_gram",
        "vn_ingredients",
        "gram > 0",
    )

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

    # Move every row to a unique temporary name first. This avoids violating
    # the existing unique index while two rows exchange/merge display names.
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
    op.drop_constraint(
        "ck_vn_ingredients_positive_gram",
        "vn_ingredients",
        type_="check",
    )
    op.drop_column("vn_ingredients", "gram")
