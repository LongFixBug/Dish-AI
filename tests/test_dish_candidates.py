"""Contracts for staging Vision-only dishes before catalog approval."""

from types import SimpleNamespace

from sqlalchemy import CheckConstraint, UniqueConstraint

from backend.db.models import DishCandidate, VnDish
from backend.services import dish_candidates
from schemas.nutrition import NutritionPerIngredient


class FakeSession:
    def __init__(self, result: object | None = None) -> None:
        self.added: list[object] = []
        self.flushes = 0
        self.result = result
        self.executed: list[object] = []

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flushes += 1

    async def execute(self, statement: object):
        self.executed.append(statement)
        return SimpleNamespace(scalar_one=lambda: self.result)


def _vision_nutrition() -> NutritionPerIngredient:
    return NutritionPerIngredient(
        item_name="Phở thử nghiệm",
        grams=450.0,
        calories=380.0,
        protein_g=24.0,
        fat_g=10.0,
        carbs_g=52.0,
        fiber_g=3.0,
        found_in_db=False,
    )


def test_vn_dish_declares_exact_name_unique_constraint() -> None:
    constraint_names = {
        constraint.name
        for constraint in VnDish.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert "uq_vn_dishes_dish_name" in constraint_names


def test_candidate_declares_unique_key_and_status_check() -> None:
    unique_names = {
        constraint.name
        for constraint in DishCandidate.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_names = {
        constraint.name
        for constraint in DishCandidate.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "uq_dish_candidates_dish_name_key" in unique_names
    assert "ck_dish_candidates_status" in check_names


def test_candidate_key_preserves_tones_but_normalizes_case_and_spacing() -> None:
    assert dish_candidates.normalize_dish_name_key("  Mực   Xào Dứa ") == "mực xào dứa"
    assert dish_candidates.normalize_dish_name_key(
        "Mực xào dưa"
    ) != dish_candidates.normalize_dish_name_key(
        "Mực xào dứa"
    )


async def test_new_vision_dish_is_staged_as_pending() -> None:
    candidate = SimpleNamespace(status="pending")
    session = FakeSession(candidate)

    result = await dish_candidates.stage_dish_candidate(
        session,
        " Phở  Thử Nghiệm ",
        450.0,
        nutrition=_vision_nutrition(),
    )

    params = session.executed[0].compile().params
    assert result is candidate
    assert params["dish_name"] == "Phở Thử Nghiệm"
    assert params["dish_name_key"] == "phở thử nghiệm"
    assert params["observation_count"] == 1
    assert params["total_calories"] == 380.0
    assert session.added == []
    assert session.flushes == 0


async def test_candidate_without_nutrition_uses_zero_totals() -> None:
    candidate = SimpleNamespace(status="pending")
    session = FakeSession(candidate)

    result = await dish_candidates.stage_dish_candidate(
        session,
        "Món chưa rõ",
        None,
    )

    params = session.executed[0].compile().params
    assert result is candidate
    assert params["typical_grams"] is None
    assert params["total_calories"] == 0.0
    assert params["total_protein_g"] == 0.0


async def test_repeated_observation_updates_candidate_without_approving() -> None:
    candidate = SimpleNamespace(
        dish_name="Phở thử nghiệm",
        dish_name_key="phở thử nghiệm",
        status="pending",
        observation_count=2,
        typical_grams=400.0,
        total_calories=350.0,
        total_protein_g=20.0,
        total_fat_g=9.0,
        total_carbs_g=50.0,
        total_fiber_g=2.0,
    )

    session = FakeSession(candidate)

    result = await dish_candidates.stage_dish_candidate(
        session,
        "PHỞ THỬ NGHIỆM",
        450.0,
        nutrition=_vision_nutrition(),
    )

    assert result is candidate
    assert candidate.status == "pending"
    assert len(session.executed) == 1
    assert session.added == []
    assert session.flushes == 0


async def test_approve_candidate_publishes_reviewed_catalog_dish(monkeypatch) -> None:
    candidate = SimpleNamespace(
        id="candidate-id",
        dish_name="Phở thử nghiệm",
        status="pending",
        typical_grams=450.0,
        total_calories=380.0,
        total_protein_g=24.0,
        total_fat_g=10.0,
        total_carbs_g=52.0,
        total_fiber_g=3.0,
        approved_dish_id=None,
        reviewed_at=None,
    )

    async def fake_candidate(_session, _candidate_id):
        return candidate

    async def fake_catalog(_session, _dish_name):
        return None

    monkeypatch.setattr(dish_candidates, "_lookup_candidate_by_id", fake_candidate)
    monkeypatch.setattr(dish_candidates, "_lookup_catalog_by_name", fake_catalog)
    session = FakeSession()

    dish = await dish_candidates.approve_dish_candidate(session, "candidate-id")

    assert dish.source == "vision_reviewed"
    assert dish.dish_name == candidate.dish_name
    assert candidate.status == "approved"
    assert candidate.approved_dish_id == dish.id
    assert candidate.reviewed_at is not None
    assert session.added == [dish]
    assert session.flushes == 1


async def test_reject_candidate_keeps_it_out_of_catalog(monkeypatch) -> None:
    candidate = SimpleNamespace(
        id="candidate-id",
        status="pending",
        reviewed_at=None,
    )

    async def fake_candidate(_session, _candidate_id):
        return candidate

    monkeypatch.setattr(dish_candidates, "_lookup_candidate_by_id", fake_candidate)
    session = FakeSession()

    result = await dish_candidates.reject_dish_candidate(session, "candidate-id")

    assert result is candidate
    assert candidate.status == "rejected"
    assert candidate.reviewed_at is not None
    assert session.added == []
    assert session.flushes == 1
