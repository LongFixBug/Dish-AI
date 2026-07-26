"""Clean the catalog and enforce durable quality guards.

Revision ID: 0008_catalog_quality_guards
Revises: 0007_qdrant_vector_store
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_catalog_quality_guards"
down_revision = "0007_qdrant_vector_store"
branch_labels = None
depends_on = None

CANONICAL_DISH_NAME = (
    "lower(regexp_replace(btrim(normalize(dish_name, NFC)), '\\s+', ' ', 'g'))"
)
CANONICAL_INGREDIENT_NAME = (
    "lower(regexp_replace(btrim(normalize(ingredient_name, NFC)), '\\s+', ' ', 'g'))"
)


def _create_cleanup_log() -> None:
    op.create_table(
        "catalog_cleanup_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=False),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(200), nullable=False),
        sa.Column("survivor_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column(
            "changes",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("qdrant_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_catalog_cleanup_log_unsynced",
        "catalog_cleanup_log",
        ["action", "qdrant_synced_at"],
    )


def _archive_and_remove_duplicates() -> None:
    op.execute(f"""
        CREATE TEMP TABLE catalog_ingredient_duplicate_map ON COMMIT DROP AS
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER (
                       PARTITION BY source, {CANONICAL_INGREDIENT_NAME}
                       ORDER BY
                           ((calories_per_g < 0)::int + (protein_per_g < 0)::int
                            + (fat_per_g < 0)::int + (carbs_per_g < 0)::int
                            + (fiber_per_g < 0)::int),
                           abs(calories_per_g - (
                               4 * protein_per_g + 9 * fat_per_g + 4 * carbs_per_g
                           )) / greatest(calories_per_g, 0.000001),
                           -((calories_per_g > 0)::int + (protein_per_g > 0)::int
                             + (fat_per_g > 0)::int + (carbs_per_g > 0)::int
                             + (fiber_per_g > 0)::int),
                           id
                   ) AS survivor_id,
                   row_number() OVER (
                       PARTITION BY source, {CANONICAL_INGREDIENT_NAME}
                       ORDER BY
                           ((calories_per_g < 0)::int + (protein_per_g < 0)::int
                            + (fat_per_g < 0)::int + (carbs_per_g < 0)::int
                            + (fiber_per_g < 0)::int),
                           abs(calories_per_g - (
                               4 * protein_per_g + 9 * fat_per_g + 4 * carbs_per_g
                           )) / greatest(calories_per_g, 0.000001),
                           -((calories_per_g > 0)::int + (protein_per_g > 0)::int
                             + (fat_per_g > 0)::int + (carbs_per_g > 0)::int
                             + (fiber_per_g > 0)::int),
                           id
                   ) AS rank
            FROM vn_ingredients
        )
        SELECT id AS loser_id, survivor_id FROM ranked WHERE rank > 1
    """)
    op.execute("""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, survivor_id, snapshot, changes
        )
        SELECT 'ingredient', ingredient.id, 'archive_duplicate',
               'case_or_whitespace_duplicate', duplicate.survivor_id,
               to_jsonb(ingredient), '{}'::jsonb
        FROM catalog_ingredient_duplicate_map AS duplicate
        JOIN vn_ingredients AS ingredient ON ingredient.id = duplicate.loser_id
    """)
    op.execute("""
        DELETE FROM vn_ingredients AS ingredient
        USING catalog_ingredient_duplicate_map AS duplicate
        WHERE ingredient.id = duplicate.loser_id
    """)

    op.execute(f"""
        CREATE TEMP TABLE catalog_dish_duplicate_map ON COMMIT DROP AS
        WITH ranked AS (
            SELECT id,
                   first_value(id) OVER (
                       PARTITION BY {CANONICAL_DISH_NAME}
                       ORDER BY
                           ((total_calories < 0)::int + (total_protein_g < 0)::int
                            + (total_fat_g < 0)::int + (total_carbs_g < 0)::int
                            + (total_fiber_g < 0)::int),
                           CASE WHEN typical_grams > 0 AND (
                               total_calories / typical_grams > 9
                               OR total_protein_g + total_fat_g + total_carbs_g
                                  + total_fiber_g > typical_grams * 1.25
                           ) THEN 1 ELSE 0 END,
                           abs(total_calories - (
                               4 * total_protein_g + 9 * total_fat_g + 4 * total_carbs_g
                           )) / greatest(total_calories, 0.000001),
                           -((total_calories > 0)::int + (total_protein_g > 0)::int
                             + (total_fat_g > 0)::int + (total_carbs_g > 0)::int
                             + (total_fiber_g > 0)::int),
                           -typical_grams_confidence,
                           id
                   ) AS survivor_id,
                   row_number() OVER (
                       PARTITION BY {CANONICAL_DISH_NAME}
                       ORDER BY
                           ((total_calories < 0)::int + (total_protein_g < 0)::int
                            + (total_fat_g < 0)::int + (total_carbs_g < 0)::int
                            + (total_fiber_g < 0)::int),
                           CASE WHEN typical_grams > 0 AND (
                               total_calories / typical_grams > 9
                               OR total_protein_g + total_fat_g + total_carbs_g
                                  + total_fiber_g > typical_grams * 1.25
                           ) THEN 1 ELSE 0 END,
                           abs(total_calories - (
                               4 * total_protein_g + 9 * total_fat_g + 4 * total_carbs_g
                           )) / greatest(total_calories, 0.000001),
                           -((total_calories > 0)::int + (total_protein_g > 0)::int
                             + (total_fat_g > 0)::int + (total_carbs_g > 0)::int
                             + (total_fiber_g > 0)::int),
                           -typical_grams_confidence,
                           id
                   ) AS rank
            FROM vn_dishes
        )
        SELECT id AS loser_id, survivor_id FROM ranked WHERE rank > 1
    """)
    op.execute("""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, survivor_id, snapshot, changes
        )
        SELECT 'dish', dish.id, 'archive_duplicate',
               'case_or_whitespace_duplicate', duplicate.survivor_id,
               to_jsonb(dish), '{}'::jsonb
        FROM catalog_dish_duplicate_map AS duplicate
        JOIN vn_dishes AS dish ON dish.id = duplicate.loser_id
    """)
    op.execute("""
        UPDATE dish_candidates AS candidate
        SET approved_dish_id = duplicate.survivor_id
        FROM catalog_dish_duplicate_map AS duplicate
        WHERE candidate.approved_dish_id = duplicate.loser_id
    """)
    op.execute("""
        DELETE FROM vn_dishes AS dish
        USING catalog_dish_duplicate_map AS duplicate
        WHERE dish.id = duplicate.loser_id
    """)


def _repair_conservative_quality_errors() -> None:
    op.execute("""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, snapshot, changes
        )
        SELECT 'ingredient', id, 'clamp_tiny_negative', 'rounding_artifact',
               to_jsonb(ingredient),
               jsonb_strip_nulls(jsonb_build_object(
                   'calories_per_g', CASE WHEN calories_per_g < 0 THEN 0 END,
                   'protein_per_g', CASE WHEN protein_per_g < 0 THEN 0 END,
                   'fat_per_g', CASE WHEN fat_per_g < 0 THEN 0 END,
                   'carbs_per_g', CASE WHEN carbs_per_g < 0 THEN 0 END,
                   'fiber_per_g', CASE WHEN fiber_per_g < 0 THEN 0 END
               ))
        FROM vn_ingredients AS ingredient
        WHERE (calories_per_g >= -0.001 AND calories_per_g < 0)
           OR (protein_per_g >= -0.001 AND protein_per_g < 0)
           OR (fat_per_g >= -0.001 AND fat_per_g < 0)
           OR (carbs_per_g >= -0.001 AND carbs_per_g < 0)
           OR (fiber_per_g >= -0.001 AND fiber_per_g < 0)
    """)
    op.execute("""
        UPDATE vn_ingredients SET
            calories_per_g = CASE WHEN calories_per_g >= -0.001 AND calories_per_g < 0 THEN 0 ELSE calories_per_g END,
            protein_per_g = CASE WHEN protein_per_g >= -0.001 AND protein_per_g < 0 THEN 0 ELSE protein_per_g END,
            fat_per_g = CASE WHEN fat_per_g >= -0.001 AND fat_per_g < 0 THEN 0 ELSE fat_per_g END,
            carbs_per_g = CASE WHEN carbs_per_g >= -0.001 AND carbs_per_g < 0 THEN 0 ELSE carbs_per_g END,
            fiber_per_g = CASE WHEN fiber_per_g >= -0.001 AND fiber_per_g < 0 THEN 0 ELSE fiber_per_g END
        WHERE (calories_per_g >= -0.001 AND calories_per_g < 0)
           OR (protein_per_g >= -0.001 AND protein_per_g < 0)
           OR (fat_per_g >= -0.001 AND fat_per_g < 0)
           OR (carbs_per_g >= -0.001 AND carbs_per_g < 0)
           OR (fiber_per_g >= -0.001 AND fiber_per_g < 0)
    """)

    physical_condition = """
        typical_grams > 0 AND (
            total_calories / typical_grams > 9
            OR total_protein_g + total_fat_g + total_carbs_g + total_fiber_g
               > typical_grams * 1.25
        )
    """
    op.execute(f"""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, snapshot, changes
        )
        SELECT 'dish', id, 'quarantine_serving_weight',
               concat_ws(',',
                   CASE WHEN total_calories / typical_grams > 9
                        THEN 'implausible_energy_density' END,
                   CASE WHEN total_protein_g + total_fat_g + total_carbs_g + total_fiber_g
                                  > typical_grams * 1.25
                        THEN 'implausible_macro_mass' END
               ),
               to_jsonb(dish),
               jsonb_build_object(
                   'typical_grams', NULL,
                   'typical_grams_source', 'catalog_audit_quarantine',
                   'typical_grams_confidence', 0,
                   'typical_grams_rule', 'physical_limit'
               )
        FROM vn_dishes AS dish
        WHERE {physical_condition}
    """)
    op.execute(f"""
        UPDATE vn_dishes SET
            typical_grams = NULL,
            typical_grams_source = 'catalog_audit_quarantine',
            typical_grams_confidence = 0,
            typical_grams_rule = 'physical_limit'
        WHERE {physical_condition}
    """)

    op.execute("""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, snapshot, changes
        )
        SELECT 'candidate', id, 'reject_invalid_candidate',
               'missing_positive_weight_or_calories', to_jsonb(candidate),
               jsonb_build_object('status', 'rejected')
        FROM dish_candidates AS candidate
        WHERE status = 'pending'
          AND (typical_grams IS NULL OR typical_grams <= 0 OR total_calories <= 0)
    """)
    op.execute("""
        UPDATE dish_candidates SET status = 'rejected', reviewed_at = now()
        WHERE status = 'pending'
          AND (typical_grams IS NULL OR typical_grams <= 0 OR total_calories <= 0)
    """)
    _quarantine_remaining_violations()


def _quarantine_remaining_violations() -> None:
    """Dọn nốt mọi hàng còn vi phạm CHECK sắp tạo ở ``_add_guards``.

    Các bước sửa ở trên cố ý bảo thủ (chỉ clamp số âm cực nhỏ của
    ``vn_ingredients``, chỉ NULL ``typical_grams`` khi nó dương). Phần còn lại —
    số âm ở ``vn_dishes``/``dish_candidates``, ``typical_grams <= 0``,
    ``observation_count <= 0`` — vẫn đủ để ``CREATE ... CHECK`` fail và rollback
    cả migration. Đưa chúng về giá trị hợp lệ và ghi lại vào catalog_cleanup_log
    để không mất dấu vết.
    """
    negative_columns = {
        "vn_ingredients": (
            "calories_per_g", "protein_per_g", "fat_per_g", "carbs_per_g", "fiber_per_g",
        ),
        "vn_dishes": (
            "total_calories", "total_protein_g", "total_fat_g",
            "total_carbs_g", "total_fiber_g",
        ),
        "dish_candidates": (
            "total_calories", "total_protein_g", "total_fat_g",
            "total_carbs_g", "total_fiber_g",
        ),
    }
    entity_types = {
        "vn_ingredients": "ingredient",
        "vn_dishes": "dish",
        "dish_candidates": "candidate",
    }
    for table, columns in negative_columns.items():
        condition = " OR ".join(f"{column} < 0" for column in columns)
        assignments = ", ".join(f"{column} = GREATEST({column}, 0)" for column in columns)
        op.execute(f"""
            INSERT INTO catalog_cleanup_log (
                entity_type, record_id, action, reason, snapshot, changes
            )
            SELECT '{entity_types[table]}', id, 'clamp_negative_nutrient',
                   'pre_constraint_cleanup', to_jsonb(entry), '{{}}'::jsonb
            FROM {table} AS entry
            WHERE {condition}
        """)
        op.execute(f"UPDATE {table} SET {assignments} WHERE {condition}")

    for table in ("vn_dishes", "dish_candidates"):
        op.execute(f"""
            INSERT INTO catalog_cleanup_log (
                entity_type, record_id, action, reason, snapshot, changes
            )
            SELECT '{entity_types[table]}', id, 'null_invalid_typical_grams',
                   'pre_constraint_cleanup', to_jsonb(entry), '{{}}'::jsonb
            FROM {table} AS entry
            WHERE typical_grams IS NOT NULL AND typical_grams <= 0
        """)
        op.execute(f"""
            UPDATE {table} SET typical_grams = NULL
            WHERE typical_grams IS NOT NULL AND typical_grams <= 0
        """)

    op.execute("""
        UPDATE dish_candidates SET observation_count = 1
        WHERE observation_count <= 0
    """)


def _add_guards() -> None:
    op.create_check_constraint(
        "ck_vn_ingredients_nonnegative_nutrients",
        "vn_ingredients",
        "calories_per_g >= 0 AND protein_per_g >= 0 AND fat_per_g >= 0 "
        "AND carbs_per_g >= 0 AND fiber_per_g >= 0",
    )
    op.create_check_constraint(
        "ck_vn_dishes_nonnegative_nutrients",
        "vn_dishes",
        "total_calories >= 0 AND total_protein_g >= 0 AND total_fat_g >= 0 "
        "AND total_carbs_g >= 0 AND total_fiber_g >= 0",
    )
    op.create_check_constraint(
        "ck_vn_dishes_positive_typical_grams",
        "vn_dishes",
        "typical_grams IS NULL OR typical_grams > 0",
    )
    op.create_check_constraint(
        "ck_dish_candidates_nonnegative_nutrients",
        "dish_candidates",
        "total_calories >= 0 AND total_protein_g >= 0 AND total_fat_g >= 0 "
        "AND total_carbs_g >= 0 AND total_fiber_g >= 0",
    )
    op.create_check_constraint(
        "ck_dish_candidates_positive_typical_grams",
        "dish_candidates",
        "typical_grams IS NULL OR typical_grams > 0",
    )
    op.create_check_constraint(
        "ck_dish_candidates_positive_observation_count",
        "dish_candidates",
        "observation_count > 0",
    )
    op.create_index(
        "uq_vn_ingredients_name_source_ci",
        "vn_ingredients",
        [sa.text(CANONICAL_INGREDIENT_NAME), "source"],
        unique=True,
    )
    op.create_index(
        "uq_vn_dishes_name_ci",
        "vn_dishes",
        [sa.text(CANONICAL_DISH_NAME)],
        unique=True,
    )


def upgrade() -> None:
    """Archive, repair, and then make the repaired invariants permanent."""
    _create_cleanup_log()
    _archive_and_remove_duplicates()
    _repair_conservative_quality_errors()
    _add_guards()


def downgrade() -> None:
    """Remove guards and restore archived values and duplicate rows."""
    op.drop_index("uq_vn_dishes_name_ci", table_name="vn_dishes")
    op.drop_index("uq_vn_ingredients_name_source_ci", table_name="vn_ingredients")
    for constraint, table in (
        ("ck_dish_candidates_positive_observation_count", "dish_candidates"),
        ("ck_dish_candidates_positive_typical_grams", "dish_candidates"),
        ("ck_dish_candidates_nonnegative_nutrients", "dish_candidates"),
        ("ck_vn_dishes_positive_typical_grams", "vn_dishes"),
        ("ck_vn_dishes_nonnegative_nutrients", "vn_dishes"),
        ("ck_vn_ingredients_nonnegative_nutrients", "vn_ingredients"),
    ):
        op.drop_constraint(constraint, table, type_="check")

    op.execute("""
        INSERT INTO vn_ingredients
        SELECT (jsonb_populate_record(NULL::vn_ingredients, snapshot)).*
        FROM catalog_cleanup_log
        WHERE action = 'archive_duplicate' AND entity_type = 'ingredient'
    """)
    op.execute("""
        INSERT INTO vn_dishes
        SELECT (jsonb_populate_record(NULL::vn_dishes, snapshot)).*
        FROM catalog_cleanup_log
        WHERE action = 'archive_duplicate' AND entity_type = 'dish'
    """)
    op.execute("""
        UPDATE vn_ingredients AS ingredient SET
            calories_per_g = (log.snapshot->>'calories_per_g')::float,
            protein_per_g = (log.snapshot->>'protein_per_g')::float,
            fat_per_g = (log.snapshot->>'fat_per_g')::float,
            carbs_per_g = (log.snapshot->>'carbs_per_g')::float,
            fiber_per_g = (log.snapshot->>'fiber_per_g')::float
        FROM catalog_cleanup_log AS log
        WHERE log.action = 'clamp_tiny_negative' AND ingredient.id = log.record_id
    """)
    op.execute("""
        UPDATE vn_dishes AS dish SET
            typical_grams = (log.snapshot->>'typical_grams')::float,
            typical_grams_source = log.snapshot->>'typical_grams_source',
            typical_grams_confidence = (log.snapshot->>'typical_grams_confidence')::float,
            typical_grams_rule = log.snapshot->>'typical_grams_rule'
        FROM catalog_cleanup_log AS log
        WHERE log.action = 'quarantine_serving_weight' AND dish.id = log.record_id
    """)
    op.execute("""
        UPDATE dish_candidates AS candidate SET
            status = log.snapshot->>'status',
            reviewed_at = (log.snapshot->>'reviewed_at')::timestamptz
        FROM catalog_cleanup_log AS log
        WHERE log.action = 'reject_invalid_candidate' AND candidate.id = log.record_id
    """)
    op.drop_index("ix_catalog_cleanup_log_unsynced", table_name="catalog_cleanup_log")
    op.drop_table("catalog_cleanup_log")
