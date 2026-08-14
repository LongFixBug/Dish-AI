"""Tests for the public NRIHCM food nutrition importer."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from scripts.crawl_nrihcm_foods import fetch_all_foods, parse_food_item, upsert_rows


def sample_item(food_id: int = 1902) -> dict[str, object]:
    return {
        "thucPhamId": food_id,
        "maThucPham": "01001",
        "tenThucPham": "Gạo nếp cái",
        "tenThucPhamEn": "Glutinous rice, milled, raw",
        "nhomThucPham": "NGŨ CỐC VÀ SẢN PHẨM CHẾ BIẾN",
        "nhomThucPhamId": 1,
        "nangLuongKcal": 348.0,
        "nangLuongKJ": 1454.64,
        "tyLeThaiBo": 0.0,
        "khoiLuong": 100.0,
        "thanhPhanDinhDuong": [
            {"dinhDuongId": 1, "tenDinhDuong": "Nước", "maDonVi": "g", "hamLuong": 14.0},
            {"dinhDuongId": 2, "tenDinhDuong": "Chất Đạm", "maDonVi": "g", "hamLuong": 8.6},
            {"dinhDuongId": 3, "tenDinhDuong": "Chất Béo", "maDonVi": "g", "hamLuong": 1.5},
            {
                "dinhDuongId": 4,
                "tenDinhDuong": "Chất bột đường",
                "maDonVi": "g",
                "hamLuong": 75.1,
            },
        ],
    }


def test_parse_food_item_keeps_raw_data_and_normalizes_common_nutrients() -> None:
    fetched_at = datetime(2026, 8, 5, tzinfo=timezone.utc)

    row = parse_food_item(sample_item(), fetched_at=fetched_at)

    assert row["source_food_id"] == 1902
    assert row["food_code"] == "01001"
    assert row["name_vi"] == "Gạo nếp cái"
    assert row["energy_kcal_per_100g"] == 348.0
    assert row["water_g_per_100g"] == 14.0
    assert row["protein_g_per_100g"] == 8.6
    assert row["fat_g_per_100g"] == 1.5
    assert row["carbs_g_per_100g"] == 75.1
    assert row["raw_payload"] == sample_item()
    assert row["fetched_at"] == fetched_at


def test_parse_food_item_rejects_missing_source_id() -> None:
    item = sample_item()
    item.pop("thucPhamId")

    with pytest.raises(ValueError, match="thucPhamId"):
        parse_food_item(item)


def test_fetch_all_foods_follows_api_pagination() -> None:
    pages = {
        0: [sample_item(1), sample_item(2)],
        2: [sample_item(3)],
    }
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        payload = httpx.Response(200, content=body).json()
        requests.append(payload)
        skip_count = payload["skipCount"]
        return httpx.Response(
            200,
            json={"result": {"totalCount": 3, "items": pages[skip_count]}},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport) as client:
        rows = fetch_all_foods(client, page_size=2)

    assert [row["source_food_id"] for row in rows] == [1, 2, 3]
    assert [request["skipCount"] for request in requests] == [0, 2]
    assert all(request["maxResultCount"] == 2 for request in requests)


def test_fetch_all_foods_rejects_malformed_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"result": {"totalCount": 1}})
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(RuntimeError, match="items"):
            fetch_all_foods(client)


@pytest.mark.asyncio
async def test_upsert_rows_batches_large_snapshots() -> None:
    session = AsyncMock()
    rows = [parse_food_item(sample_item(food_id)) for food_id in range(1, 502)]

    stored = await upsert_rows(session, rows)

    assert stored == 501
    assert session.execute.await_count == 2
    session.commit.assert_awaited_once()
