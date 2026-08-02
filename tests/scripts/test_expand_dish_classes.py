"""Contracts for expanding existing dish classes without split leakage."""

from pathlib import Path

from PIL import Image


def _write_image(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (120, 120), color=color).save(path)


def test_expansion_targets_are_balanced_for_a_46_class_release() -> None:
    from scripts.expand_dish_classes import CRAWL_SOURCE, EXPANSION_TARGETS

    assert CRAWL_SOURCE == "bing_legacy_query_pipeline"
    assert EXPANSION_TARGETS == {
        "train": 300,
        "val": 60,
        "test": 100,
        "references": 40,
    }


def test_expansion_reuses_legacy_bing_queries_and_not_hugging_face() -> None:
    from scripts.expand_dish_classes import _queries

    queries = _queries("Bánh tráng trộn")

    assert '"Bánh tráng trộn" Sài Gòn' in queries
    assert '"Bánh tráng trộn" món ăn Việt Nam' in queries
    assert all("huggingface" not in query.lower() for query in queries)


def test_queries_include_targeted_aliases_for_sparse_classes() -> None:
    from scripts.expand_dish_classes import _queries

    queries = _queries("Ức gà áp chảo")

    assert '"vietnamese pan seared chicken breast"' in queries
    assert '"vietnamese pan seared chicken breast"' not in _queries(
        "Há cảo"
    )


def test_bing_parser_keeps_original_and_thumbnail_fallback() -> None:
    from scripts.expand_dish_classes import parse_bing_image_tasks

    content = (
        b'<div class="imgpt"><a m="{&quot;murl&quot;:&quot;https://site.test/a.jpg&quot;,'
        b'&quot;turl&quot;:&quot;https://ts3.mm.bing.net/thumb.jpg&quot;}"></a></div>'
    )

    assert parse_bing_image_tasks(content) == [
        {
            "file_url": "https://site.test/a.jpg",
            "fallback_url": "https://ts3.mm.bing.net/thumb.jpg",
        }
    ]


def test_bing_parser_filters_results_without_dish_metadata() -> None:
    from scripts.expand_dish_classes import parse_bing_image_tasks

    content = (
        b'<div class="imgpt"><a m="{&quot;murl&quot;:&quot;https://site.test/food.jpg&quot;,'
        b'&quot;turl&quot;:&quot;https://ts3.mm.bing.net/food-thumb.jpg&quot;,'
        b'&quot;t&quot;:&quot;Banh trang tron Sai Gon&quot;,&quot;desc&quot;:&quot;Mon an Viet Nam&quot;}"></a></div>'
        b'<div class="imgpt"><a m="{&quot;murl&quot;:&quot;https://site.test/sports.jpg&quot;,'
        b'&quot;turl&quot;:&quot;https://ts3.mm.bing.net/sports-thumb.jpg&quot;,'
        b'&quot;t&quot;:&quot;Football match highlights&quot;,&quot;desc&quot;:&quot;Sports news&quot;}"></a></div>'
    )

    assert parse_bing_image_tasks(
        content,
        required_terms=("banh", "trang", "tron"),
    ) == [
        {
            "file_url": "https://site.test/food.jpg",
            "fallback_url": "https://ts3.mm.bing.net/food-thumb.jpg",
        }
    ]


def test_bing_parser_deduplicates_repeated_result_urls() -> None:
    from scripts.expand_dish_classes import parse_bing_image_tasks

    content = (
        b'<div class="imgpt"><a m="{&quot;murl&quot;:&quot;https://site.test/a.jpg&quot;,'
        b'&quot;turl&quot;:&quot;https://ts3.mm.bing.net/a-thumb.jpg&quot;,'
        b'&quot;t&quot;:&quot;Ha cao mon an Viet Nam&quot;}"></a></div>'
        b'<div class="imgpt"><a m="{&quot;murl&quot;:&quot;https://site.test/a.jpg&quot;,'
        b'&quot;turl&quot;:&quot;https://ts3.mm.bing.net/a-thumb.jpg&quot;,'
        b'&quot;t&quot;:&quot;Ha cao mon an Viet Nam&quot;}"></a></div>'
    )

    assert parse_bing_image_tasks(content, required_terms=("ha", "cao")) == [
        {
            "file_url": "https://site.test/a.jpg",
            "fallback_url": "https://ts3.mm.bing.net/a-thumb.jpg",
        }
    ]


def test_crawl_task_dedup_skips_urls_seen_by_earlier_queries() -> None:
    from scripts.expand_dish_classes import deduplicate_bing_tasks

    seen = {"https://site.test/already-seen.jpg"}
    tasks = [
        {"file_url": "https://site.test/already-seen.jpg"},
        {"file_url": "https://site.test/new.jpg"},
        {"file_url": "https://site.test/new.jpg"},
    ]

    assert deduplicate_bing_tasks(tasks, seen) == [
        {"file_url": "https://site.test/new.jpg"}
    ]
    assert seen == {
        "https://site.test/already-seen.jpg",
        "https://site.test/new.jpg",
    }


def test_query_offsets_advance_between_splits() -> None:
    from scripts.expand_dish_classes import next_query_offset

    offsets: dict[str, int] = {}

    assert next_query_offset("query", 120, offsets) == 0
    assert next_query_offset("query", 80, offsets) == 120
    assert next_query_offset("other query", 60, offsets) == 0
    assert next_query_offset("query", 120, offsets) == 200


def test_query_offset_state_round_trips(tmp_path: Path) -> None:
    from scripts.expand_dish_classes import load_query_offsets, save_query_offsets

    state_path = tmp_path / ".crawl_state.json"
    save_query_offsets(state_path, {"query": 240})

    assert load_query_offsets(state_path) == {"query": 240}


def test_missing_counts_only_include_the_shortfall(tmp_path: Path) -> None:
    from scripts.expand_dish_classes import EXPANSION_TARGETS, missing_counts

    _write_image(tmp_path / "train" / "ha_cao" / "old.jpg", (255, 0, 0))
    _write_image(tmp_path / "val" / "ha_cao" / "old.jpg", (0, 255, 0))
    _write_image(tmp_path / "test" / "ha_cao" / "old.jpg", (0, 0, 255))
    _write_image(tmp_path / "references" / "ha_cao" / "old.jpg", (120, 120, 120))

    assert missing_counts(tmp_path, "ha_cao") == {
        split: target - 1 for split, target in EXPANSION_TARGETS.items()
    }


def test_merge_staged_class_appends_without_overwriting_existing_images(tmp_path: Path) -> None:
    from scripts.expand_dish_classes import merge_staged_class

    live = tmp_path / "live"
    staged = tmp_path / "staged"
    _write_image(live / "train" / "ha_cao" / "ha_cao_0.jpg", (255, 0, 0))
    _write_image(staged / "train" / "ha_cao" / "ha_cao_0.jpg", (0, 255, 0))

    merged = merge_staged_class(staged, live, "ha_cao", {"train": 2})

    assert merged == {"train": 2}
    assert (live / "train" / "ha_cao" / "ha_cao_0.jpg").read_bytes()
    assert len(list((live / "train" / "ha_cao").glob("*.jpg"))) == 2
    assert not (staged / "train" / "ha_cao").exists()
