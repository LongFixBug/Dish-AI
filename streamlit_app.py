"""Streamlit UI — FoodAI: nhận diện món ăn Việt + phân tích dinh dưỡng từ ảnh.

Ba tab chính:
  - Analyze: upload ảnh → CV local + Qwen3.7 vision → dinh dưỡng
  - Search: tìm món (lookup) + tìm nguyên liệu (autocomplete)
  - Contribute: đóng góp công thức món mới (Tier 2)

Gọi API backend qua httpx. Backend mặc định http://localhost:8000.

Usage:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx
import streamlit as st

# ─── Config ──────────────────────────────────────────────────────────────────

API_BASE = "http://localhost:8000"
st.set_page_config(
    page_title="FoodAI — Nhận diện món Việt",
    page_icon="🍜",
    layout="wide",
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _api(verb: str, path: str, **kwargs) -> httpx.Response:
    """Gọi API backend. Verb = POST, GET, etc. Path = /api/v1/..."""
    url = f"{API_BASE}{path}"
    try:
        r = getattr(httpx, verb)(url, **kwargs, timeout=40.0)
        return r
    except httpx.ConnectError:
        st.error(f"Không kết nối được backend ({API_BASE}). Chạy `uvicorn backend.main:app --port 8000`")
        st.stop()
    except httpx.ReadTimeout:
        st.error("Backend timeout — thử lại.")
        st.stop()


def _nutrition_card(totals: dict, title: str | None = None) -> None:
    """Hiển thị nutrition card với metrics."""

    cols = st.columns(5)
    cols[0].metric("🔥 Calories", f"{totals.get('total_calories', 0):.0f} kcal")
    cols[1].metric("🥩 Protein", f"{totals.get('total_protein_g', 0):.1f} g")
    cols[2].metric("🧈 Fat", f"{totals.get('total_fat_g', 0):.1f} g")
    cols[3].metric("🍚 Carbs", f"{totals.get('total_carbs_g', 0):.1f} g")
    cols[4].metric("🌿 Fiber", f"{totals.get('total_fiber_g', 0):.1f} g")

    # Confidence & missing
    conf = totals.get("confidence_score")
    missing = totals.get("missing_ingredients", [])
    foot = []
    if conf is not None:
        foot.append(f"Độ tin cậy: **{conf:.0%}**")
    if missing:
        foot.append(f"Thiếu DB: {', '.join(missing)}")
    if foot:
        st.caption(" · ".join(foot))

    # Ingredient table
    with st.expander(f"Nguyên liệu ({len(totals.get('ingredients', []))})"):
        rows = []
        for ing in totals.get("ingredients", []):
            rows.append({
                "Tên": ing["ingredient_name"],
                "Gram": f"{ing['grams']:.0f}",
                "Calo": f"{ing['calories']:.0f}",
                "Đạm": f"{ing['protein_g']:.1f}",
                "Béo": f"{ing['fat_g']:.1f}",
                "Carb": f"{ing['carbs_g']:.1f}",
            })
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)


# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.title("🍜 FoodAI")
st.sidebar.caption("AI nhận diện món ăn Việt + phân tích dinh dưỡng")

# Health check
try:
    r = httpx.get(f"{API_BASE}/health", timeout=5).json()
    health = r.get("status", "?")
    st.sidebar.success(f"🟢 Backend: {health}")
except Exception:
    st.sidebar.error("🔴 Backend offline")

tab = st.sidebar.radio("Chọn chức năng", ["📸 Analyze", "🔍 Search", "➕ Contribute"])

# ─── TAB 1: Analyze (ảnh → nutrition) ────────────────────────────────────────

if tab == "📸 Analyze":
    st.title("📸 Nhận diện món ăn từ ảnh")
    st.caption("Upload ảnh → CV local (EfficientNet-B0, 12 món) + Qwen3.7 Vision fallback → phân tích dinh dưỡng")

    uploaded = st.file_uploader("Chọn ảnh món ăn", type=["jpg", "jpeg", "png", "webp"])
    if uploaded and st.button("🔍 Phân tích", type="primary"):
        with st.spinner("Đang phân tích... (~10-30s nếu dùng Vision)"):
            files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
            r = _api("post", "/api/v1/analyze", files=files)
            if r.status_code != 200:
                st.error(f"API lỗi {r.status_code}: {r.text[:500]}")
            else:
                data = r.json()
                # Source badge
                source = data.get("source", "?")
                labels = {
                    "cv_local": ("✅ CV Local", "green"),
                    "vision": ("☁️ Vision (cloud)", "orange"),
                    "cv_local_not_found_vision": ("🔄 CV → Vision", "blue"),
                }
                lbl, color = labels.get(source, (source, "grey"))
                st.caption(f"Nguồn nhận diện: :{color}[{lbl}]")

                if data.get("error"):
                    st.warning(f"⚠️ {data['error']}")

                if data.get("cv_confidence") is not None:
                    st.metric("CV Confidence", f"{data['cv_confidence']:.0%}")

                if data.get("dish_name"):
                    st.subheader(f"🍽️ {data['dish_name']}")

                if data.get("nutrition"):
                    _nutrition_card(data["nutrition"])

                if data.get("ingredients"):
                    with st.expander("Vision ingredients"):
                        for ing in data["ingredients"]:
                            st.write(f"- {ing['name']}: {ing['grams']}g")

# ─── TAB 2: Search ───────────────────────────────────────────────────────────

elif tab == "🔍 Search":
    st.title("🔍 Tìm kiếm")

    sub = st.radio("Tìm gì?", ["🍽️ Món ăn (lookup)", "🥬 Nguyên liệu (autocomplete)"], horizontal=True)

    if "Món" in sub:
        q = st.text_input("Tên món (có dấu hoặc không dấu)", placeholder="vd: cơm sườn, pho bo, bun cha...")
        if q and st.button("Tìm món"):
            r = _api("get", "/api/v1/dishes/lookup", params={"name": q})
            if r.status_code != 200:
                st.error(f"Lỗi {r.status_code}: {r.text[:300]}")
            else:
                d = r.json()
                if not d.get("exists"):
                    st.warning("Món chưa có → chuyển tab **Contribute** để đóng góp")
                else:
                    st.success(f"🍽️ **{d['dish_name']}**   (nguồn: {d.get('source','?')})")
                    if d.get("trust_score"):
                        st.metric("Trust score", f"{d['trust_score']:.0%}")
                    if d.get("nutrition"):
                        _nutrition_card(d["nutrition"])

    else:
        q = st.text_input("Tên nguyên liệu", placeholder="vd: thịt bò, sua, trung ga...")
        if q and st.button("Tìm nguyên liệu"):
            r = _api("get", "/api/v1/ingredients/search", params={"q": q, "limit": 15})
            if r.status_code != 200:
                st.error(f"Lỗi {r.status_code}")
            else:
                results = r.json().get("results", [])
                if not results:
                    st.warning("Không tìm thấy")
                else:
                    st.success(f"{len(results)} kết quả")
                    for ing in results:
                        st.write(f"- `{ing['id'][:8]}...` **{ing['ingredient_name']}** ({ing['source']})")

# ─── TAB 3: Contribute ──────────────────────────────────────────────────────

else:
    st.title("➕ Đóng góp công thức mới")
    st.caption("Món chưa có trong DB? Thêm công thức tại đây.")

    with st.form("contribute_form"):
        name = st.text_input("Tên món *", placeholder="vd: Cơm tấm sườn bì chả")
        desc = st.text_area("Mô tả (tùy chọn)", placeholder="Món cơm đặc trưng Sài Gòn...")
        contributor = st.text_input("Tên bạn (tùy chọn)", placeholder="Anonymous")

        st.markdown("### Nguyên liệu")
        # Dynamic ingredient list
        n_ings = st.number_input("Số nguyên liệu", 1, 15, 3)
        items: list[dict] = []
        for i in range(int(n_ings)):
            c1, c2, c3 = st.columns([4, 2, 1])
            ing_name = c1.text_input(f"Nguyên liệu #{i+1}", key=f"ing_{i}", placeholder="vd: thịt bò")
            amount = c2.number_input(f"Gram #{i+1}", 1.0, 5000.0, 100.0, key=f"amt_{i}")
            unit = c3.selectbox("Đơn vị", ["g", "ml"], key=f"unit_{i}")
            if ing_name.strip():
                # Tự động search ingredient_id qua autocomplete
                items.append({"name": ing_name.strip(), "amount": amount, "unit": unit})

        submit = st.form_submit_button("💾 Đóng góp", type="primary", use_container_width=True)

    if submit:
        if not name.strip():
            st.error("Tên món là bắt buộc")
        elif not items:
            st.error("Cần ít nhất 1 nguyên liệu")
        else:
            # Resolve ingredient IDs
            ingredient_ids: list[dict] = []
            unresolved = []
            with st.spinner("Đang tìm nguyên liệu..."):
                for it in items:
                    r = _api("get", "/api/v1/ingredients/search", params={"q": it["name"], "limit": 1})
                    hits = r.json().get("results", []) if r.status_code == 200 else []
                    if hits:
                        ingredient_ids.append({"ingredient_id": hits[0]["id"], "amount": it["amount"], "unit": it["unit"]})
                    else:
                        unresolved.append(it["name"])

            if unresolved:
                st.warning(f"Không tìm thấy trong DB: {', '.join(unresolved)}. Vẫn thử gửi...")
                # Fallback: skip unresolved (compute sẽ set missing)

            if ingredient_ids:
                body = {
                    "dish_name": name.strip(),
                    "description": desc.strip() or None,
                    "items": ingredient_ids,
                    "contributor_id": contributor.strip() or None,
                }
                r = _api("post", "/api/v1/dishes", json=body)
                if r.status_code == 409:
                    st.error(f"Món '{name}' đã tồn tại. Dùng tên khác hoặc search lookup.")
                elif r.status_code == 200:
                    d = r.json()
                    st.success(f"✅ Đã tạo món `{name}` (status: {d.get('status')})")
                    st.caption(f"Dish ID: `{d.get('dish_id')}`")
                    if d.get("nutrition"):
                        _nutrition_card(d["nutrition"])
                    if d.get("conversion_assumed"):
                        st.info(f"⚠️ Ước lượng mL→g: {', '.join(d['conversion_assumed'])}")
                else:
                    st.error(f"Lỗi {r.status_code}: {r.text[:500]}")
            else:
                st.error("Không tìm thấy nguyên liệu nào trong DB. Không thể tạo món.")
