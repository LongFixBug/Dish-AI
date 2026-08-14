"""Recognition decision telemetry must be durable but never block analysis."""

from types import SimpleNamespace


class FakeSession:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, value) -> None:
        if self.fail:
            raise RuntimeError("database unavailable")
        self.added.append(value)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


async def test_record_persists_metadata_without_any_image_bytes() -> None:
    from backend.services.recognition_events import record_recognition_event

    session = FakeSession()
    event_id = await record_recognition_event(
        session,
        user_id="00000000-0000-0000-0000-000000000001",
        response=SimpleNamespace(
            source="local_consensus",
            dish_name="Xôi xéo",
            model_version="cv+siglip",
        ),
        cv_dish_name="Xôi xéo",
        cv_confidence=0.9997,
        album_dish_name="Xôi xéo",
        album_score=0.8901,
        album_margin=0.0944,
        cv_top1_name="Xôi xéo",
        cv_top2_name="Xôi mặn",
        cv_top2_confidence=0.0002,
        fusion_reason="same_uuid",
    )

    assert event_id
    assert session.commits == 1
    event = session.added[0]
    assert event.source == "local_consensus"
    assert event.final_dish_name == "Xôi xéo"
    assert event.cv_confidence == 0.9997
    assert event.cv_top1_name == "Xôi xéo"
    assert event.cv_top2_name == "Xôi mặn"
    assert event.cv_top2_confidence == 0.0002
    assert event.fusion_reason == "same_uuid"
    assert not hasattr(event, "image_bytes")


async def test_record_failure_is_best_effort_and_rolls_back() -> None:
    from backend.services.recognition_events import record_recognition_event

    session = FakeSession(fail=True)
    event_id = await record_recognition_event(
        session,
        user_id="00000000-0000-0000-0000-000000000001",
        response=SimpleNamespace(source="vision", dish_name="Phở bò", model_version="qwen"),
        cv_dish_name=None,
        cv_confidence=0.0,
        album_dish_name=None,
        album_score=0.0,
        album_margin=0.0,
    )

    assert event_id is None
    assert session.rollbacks == 1


async def test_vision_only_event_keeps_retired_local_columns_null() -> None:
    from backend.services.recognition_events import record_recognition_event

    session = FakeSession()
    event_id = await record_recognition_event(
        session,
        user_id="00000000-0000-0000-0000-000000000001",
        response=SimpleNamespace(
            source="vision",
            dish_name="Phở bò",
            model_version="qwen3.5-plus",
        ),
        cv_dish_name=None,
        cv_confidence=None,
        album_dish_name=None,
        album_score=None,
        album_margin=None,
        fusion_reason="vision_only",
    )

    assert event_id
    event = session.added[0]
    assert event.cv_dish_name is None
    assert event.cv_confidence is None
    assert event.album_dish_name is None
    assert event.album_score is None
    assert event.album_margin is None
    assert event.fusion_reason == "vision_only"
