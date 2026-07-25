"""Recover physically safe weights from coherent nutrition totals.

Revision ID: 0009_recover_serving_weights
Revises: 0008_catalog_quality_guards
"""

from alembic import op

revision = "0009_recover_serving_weights"
down_revision = "0008_catalog_quality_guards"
branch_labels = None
depends_on = None

MACRO_MASS = "total_protein_g + total_fat_g + total_carbs_g + total_fiber_g"
ATWATER_CALORIES = "4 * total_protein_g + 9 * total_fat_g + 4 * total_carbs_g"
PHYSICAL_FLOOR = f"ceil(greatest(total_calories / 8.5, {MACRO_MASS}) / 25) * 25"
IS_COHERENT = (
    f"abs(total_calories - ({ATWATER_CALORIES})) / "
    "greatest(total_calories, 0.000001) <= 0.5"
)
IS_QUARANTINED = (
    "typical_grams IS NULL "
    "AND typical_grams_source = 'catalog_audit_quarantine'"
)


def upgrade() -> None:
    """Recover quarantined rows with explicit confidence for source conflicts."""
    op.execute(f"""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, snapshot, changes
        )
        SELECT 'dish', id, 'recover_conflict_serving_floor',
               'energy_macro_mismatch_physical_floor', to_jsonb(dish),
               jsonb_build_object(
                   'typical_grams', {PHYSICAL_FLOOR},
                   'typical_grams_source', 'nutrition_conflict_floor_v1',
                   'typical_grams_confidence', 0.05,
                   'typical_grams_rule',
                       'physical_floor_energy_macro_mismatch'
               )
        FROM vn_dishes AS dish
        WHERE {IS_QUARANTINED} AND NOT ({IS_COHERENT})
          AND {PHYSICAL_FLOOR} <= 3000
    """)
    op.execute(f"""
        UPDATE vn_dishes SET
            typical_grams = {PHYSICAL_FLOOR},
            typical_grams_source = 'nutrition_conflict_floor_v1',
            typical_grams_confidence = 0.05,
            typical_grams_rule = 'physical_floor_energy_macro_mismatch'
        WHERE {IS_QUARANTINED} AND NOT ({IS_COHERENT})
          AND {PHYSICAL_FLOOR} <= 3000
    """)

    op.execute(f"""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, snapshot, changes
        )
        SELECT 'dish', id, 'recover_safe_serving_weight',
               'coherent_nutrition_physical_floor', to_jsonb(dish),
               jsonb_build_object(
                   'typical_grams', {PHYSICAL_FLOOR},
                   'typical_grams_source', 'nutrition_physical_floor_v1',
                   'typical_grams_confidence', 0.15,
                   'typical_grams_rule', 'physical_floor'
               )
        FROM vn_dishes AS dish
        WHERE {IS_QUARANTINED} AND {IS_COHERENT}
          AND {PHYSICAL_FLOOR} <= 3000
    """)
    op.execute(f"""
        UPDATE vn_dishes SET
            typical_grams = {PHYSICAL_FLOOR},
            typical_grams_source = 'nutrition_physical_floor_v1',
            typical_grams_confidence = 0.15,
            typical_grams_rule = 'physical_floor'
        WHERE {IS_QUARANTINED} AND {IS_COHERENT}
          AND {PHYSICAL_FLOOR} <= 3000
    """)

    op.execute(f"""
        INSERT INTO catalog_cleanup_log (
            entity_type, record_id, action, reason, snapshot, changes
        )
        SELECT 'dish', id, 'mark_nutrition_conflict',
               'energy_macro_mismatch', to_jsonb(dish),
               jsonb_build_object(
                   'typical_grams_source', 'nutrition_conflict',
                   'typical_grams_confidence', 0,
                   'typical_grams_rule', 'energy_macro_mismatch'
               )
        FROM vn_dishes AS dish
        WHERE {IS_QUARANTINED}
    """)
    op.execute(f"""
        UPDATE vn_dishes SET
            typical_grams_source = 'nutrition_conflict',
            typical_grams_confidence = 0,
            typical_grams_rule = 'energy_macro_mismatch'
        WHERE {IS_QUARANTINED}
    """)


def downgrade() -> None:
    """Restore the post-0008 quarantine state from the cleanup journal."""
    op.execute("""
        UPDATE vn_dishes AS dish SET
            typical_grams = (log.snapshot->>'typical_grams')::float,
            typical_grams_source = log.snapshot->>'typical_grams_source',
            typical_grams_confidence =
                (log.snapshot->>'typical_grams_confidence')::float,
            typical_grams_rule = log.snapshot->>'typical_grams_rule'
        FROM catalog_cleanup_log AS log
        WHERE log.action IN (
            'recover_safe_serving_weight', 'recover_conflict_serving_floor',
            'mark_nutrition_conflict'
        ) AND dish.id = log.record_id
    """)
    op.execute("""
        DELETE FROM catalog_cleanup_log
        WHERE action IN (
            'recover_safe_serving_weight', 'recover_conflict_serving_floor',
            'mark_nutrition_conflict'
        )
    """)
