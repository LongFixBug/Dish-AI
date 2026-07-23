"""Streamlit UI — FoodAI: nhận diện món ăn Việt + phân tích dinh dưỡng từ ảnh.

Phiên bản Jul 23: chỉ còn 1 tab Analyze.
  - Upload ảnh → CV local (giữ train sau) + Vision → dishes[{dish_name, gram, is_side}]
  - Mỗi món tra vn_dishes (+ Qdrant) + vn_ingredients (món ăn kèm) → scale gram
  - Món mới → tự thêm vào vn_dishes (source=vision_auto)
  - KHÔNG còn per-ingredient edit / quick-add / Contribute / Search tab

Usage:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import unicodedata

import httpx
import streamlit as st

# ─── Config ──────────────────────────────────────────────────────────────────

API_BASE = os.environ.get("FOODAI_API_BASE", "http://localhost:8000")
st.set_page_config(
    page_title="FoodAI — Nhận diện món Việt",
    page_icon="🍜",
    layout="wide",
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _api(verb: str, path: str, **kwargs) -> httpx.Response:
    """Gọi API backend."""
    url = f"{API_BASE}{path}"
    try:
        return getattr(httpx, verb)(url, **kwargs, timeout=60.0)
    except httpx.ConnectError:
        st.error(f"Không kết nối được backend ({API_BASE}). Chạy `uvicorn backend.main:app --port 8000`")
        st.stop()
    except httpx.ReadTimeout:
        st.error("Backend timeout — thử lại.")
        st.stop()


def _nutrition_card(totals: dict) -> None:
    """Hiển thị nutrition card: per-100g + user nhập khẩu phần + danh sách món."""

    total_grams = totals.get("total_grams", 0)
    per_100g_cal = totals.get("per_100g_calories", 0)
    per_100g_p = totals.get("per_100g_protein_g", 0)
    per_100g_f = totals.get("per_100g_fat_g", 0)
    per_100g_c = totals.get("per_100g_carbs_g", 0)
    per_100g_fb = totals.get("per_100g_fiber_g", 0)

    st.markdown("#### 📊 Dinh dưỡng trên 100g")
    cols = st.columns(5)
    cols[0].metric("🔥 Calories", f"{per_100g_cal:.0f} kcal")
    cols[1].metric("🥩 Protein", f"{per_100g_p:.1f} g")
    cols[2].metric("🧈 Fat", f"{per_100g_f:.1f} g")
    cols[3].metric("🍚 Carbs", f"{per_100g_c:.1f} g")
    cols[4].metric("🌿 Fiber", f"{per_100g_fb:.1f} g")

    if total_grams > 0:
        st.caption(f"(Dựa trên tổng khối lượng ước tính **{total_grams:.0f}g** từ ảnh)")
    else:
        st.caption("(Dựa trên dữ liệu dinh dưỡng từ DB)")

    # ── User nhập khẩu phần thực tế ─────────────────────────────────────
    st.markdown("#### 🔢 Bạn ăn/uống bao nhiêu?")
    c1, c2 = st.columns([3, 1])
    with c1:
        serving = st.number_input(
            "Khẩu phần", min_value=1.0, max_value=5000.0,
            value=float(total_grams) if total_grams > 0 else 100.0,
            step=10.0, key="serving_size",
            help="Nhập số gram (món ăn) hoặc ml (đồ uống) bạn đã dùng.",
        )
    with c2:
        serving_unit = st.selectbox("Đơn vị", ["gram", "ml"], key="serving_unit")

    if per_100g_cal > 0 or per_100g_p > 0 or per_100g_f > 0 or per_100g_c > 0 or per_100g_fb > 0:
        factor = serving / 100.0
        st.markdown(f"##### → Tổng cho **{serving:.0f} {serving_unit}**:")
        c2_ = st.columns(5)
        c2_[0].metric("🔥 Calories", f"{per_100g_cal * factor:.0f} kcal")
        c2_[1].metric("🥩 Protein", f"{per_100g_p * factor:.1f} g")
        c2_[2].metric("🧈 Fat", f"{per_100g_f * factor:.1f} g")
        c2_[3].metric("🍚 Carbs", f"{per_100g_c * factor:.1f} g")
        c2_[4].metric("🌿 Fiber", f"{per_100g_fb * factor:.1f} g")
    else:
        st.caption("_(Chưa có dữ liệu dinh dưỡng để tính)_")

    # ── Confidence & missing ─────────────────────────────────────────────
    conf = totals.get("confidence_score")
    missing = totals.get("missing_ingredients", [])
    foot = []
    if conf is not None:
        foot.append(f"Độ tin cậy: **{conf:.0%}**")
    if missing:
        foot.append(f"Thiếu DB: {len(missing)} món (Vision tự thêm, nutrition=0)")
    if foot:
        st.caption(" · ".join(foot))

    # ── Danh sách món trong ảnh ──────────────────────────────────────────
    items = totals.get("items", [])
    if items:
        with st.expander(f"🍽️ Các món trong ảnh ({len(items)} món)"):
            for it in items:
                badge = "✅" if it.get("found_in_db") else "🆕"
                st.write(
                    f"{badge} **{it['item_name']}** — {it['grams']:.0f}g | "
                    f"🔥 {it['calories']:.0f} kcal | 🥩 {it['protein_g']:.1f}g | "
                    f"🧈 {it['fat_g']:.1f}g | 🍚 {it['carbs_g']:.1f}g"
                )


def _normalize_dish_name(name: str) -> str:
    """Chuẩn hóa tên món → snake_case không dấu (cho training-data feedback)."""
    nfkd = unicodedata.normalize("NFKD", name)
    no_dia = "".join(c for c in nfkd if not unicodedata.combining(c))
    import re
    return re.sub(r"[^\w\s-]", "", no_dia).strip().lower().replace(" ", "_")


def _save_to_training(correct_name: str, uploaded_bytes: bytes, uploaded_type: str) -> None:
    """Gửi ảnh + label đúng → POST /feedback/training-data (train CV sau)."""
    if not correct_name.strip() or uploaded_bytes is None:
        return
    slug = _normalize_dish_name(correct_name)
    files = {
        "file": (f"{slug}.jpg", uploaded_bytes, uploaded_type or "image/jpeg"),
        "correct_dish_name": (None, correct_name.strip()),
    }
    r = _api("post", "/api/v1/feedback/training-data", files=files)
    if r.status_code == 200:
        st.success(f"✅ Đã lưu ảnh '{correct_name}' vào training data ({r.json().get('count', '?')} ảnh)")
    else:
        st.error(f"Lỗi feedback {r.status_code}: {r.text[:300]}")


# ─── Sidebar ─────────────────────────────────────────────────────────────────

st.sidebar.title("🍜 FoodAI")
st.sidebar.caption("AI nhận diện món ăn Việt + phân tích dinh dưỡng")

try:
    r = httpx.get(f"{API_BASE}/health", timeout=5).json()
    st.sidebar.success(f"🟢 Backend: {r.get('status', '?')}")
except Exception:
    st.sidebar.error("🔴 Backend offline")

# ─── TAB Analyze (tab duy nhất) ─────────────────────────────────────────────

st.title("📸 Nhận diện món ăn từ ảnh")
st.caption(
    "Upload ảnh → Vision nhận diện từng món + khối lượng → tra vn_dishes/vn_ingredients "
    "→ scale dinh dưỡng theo gram ảnh. Món chưa có DB → tự thêm."
)

if "analyze_result" not in st.session_state:
    st.session_state.analyze_result = None
if "uploaded_bytes" not in st.session_state:
    st.session_state.uploaded_bytes = None
if "uploaded_name" not in st.session_state:
    st.session_state.uploaded_name = None
if "uploaded_type" not in st.session_state:
    st.session_state.uploaded_type = None


def _store_upload(uploaded) -> None:
    """Lưu ảnh vào session_state; ảnh mới → reset kết quả cũ."""
    if uploaded is not None:
        new_bytes = uploaded.getvalue()
        if new_bytes != st.session_state.uploaded_bytes:
            st.session_state.analyze_result = None
        st.session_state.uploaded_bytes = new_bytes
        st.session_state.uploaded_name = uploaded.name
        st.session_state.uploaded_type = uploaded.type
    else:
        st.session_state.uploaded_bytes = None
        st.session_state.uploaded_name = None
        st.session_state.uploaded_type = None
        st.session_state.analyze_result = None


def _call_analyze(endpoint: str) -> dict | None:
    """Gọi API analyze (chuẩn hoặc vision-only)."""
    if st.session_state.uploaded_bytes is None:
        st.error("Chưa có ảnh. Upload ảnh trước.")
        return None
    files = {
        "file": (
            st.session_state.uploaded_name,
            st.session_state.uploaded_bytes,
            st.session_state.uploaded_type,
        )
    }
    r = _api("post", endpoint, files=files)
    if r.status_code != 200:
        st.error(f"API lỗi {r.status_code}: {r.text[:500]}")
        return None
    return r.json()


def _show_analyze_result(data: dict) -> None:
    """Hiển thị kết quả phân tích."""
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

    # ── Món mới tự thêm vào DB ──────────────────────────────────────────
    auto_added = data.get("auto_added_dishes", [])
    if auto_added:
        st.success(
            f"🆕 **Tự thêm {len(auto_added)} món mới vào DB:** " + ", ".join(auto_added)
            + " — nutrition=0 (chưa biết), lần sau vẫn nhận diện được tên."
        )

    if data.get("dish_name"):
        st.subheader(f"🍽️ {data['dish_name']}")

    # ── Danh sách món Vision nhận ───────────────────────────────────────
    dishes = data.get("dishes", [])
    if dishes:
        with st.expander(f"👁️ Vision nhận diện {len(dishes)} món"):
            for d in dishes:
                tag = "🥢 món kèm" if d.get("is_side") else "🍚 món chính"
                st.write(f"- **{d['dish_name']}** — {d['grams']:.0f}g ({tag})")

    nutrition = data.get("nutrition")
    if nutrition:
        _nutrition_card(nutrition)
    elif not data.get("error"):
        st.info("Không có dữ liệu dinh dưỡng.")

    # ── Feedback: gửi ảnh đúng label để train CV sau ────────────────────
    st.markdown("---")
    with st.expander("📤 Gửi ảnh đúng tên (training data cho CV local)"):
        suggested = data.get("dish_name") or ""
        correct_name = st.text_input(
            "Tên món chính xác", value=suggested,
            help="Dùng để train lại CV local sau này (giữ code CV sẵn sàng).",
        )
        if st.button("Lưu ảnh training", key="save_training"):
            _save_to_training(
                correct_name,
                st.session_state.uploaded_bytes,
                st.session_state.uploaded_type,
            )


# ─── Upload + nút analyze ────────────────────────────────────────────────────

uploaded = st.file_uploader("Chọn ảnh món ăn", type=["jpg", "jpeg", "png", "webp"])
if uploaded is not None:
    _store_upload(uploaded)

c1, c2, _ = st.columns([1, 1, 4])
with c1:
    if st.button("🔍 Phân tích", type="primary"):
        st.session_state.analyze_result = _call_analyze("/api/v1/analyze")
with c2:
    if st.button("☁️ Force Vision"):
        st.session_state.analyze_result = _call_analyze("/api/v1/analyze/vision-only")

# ── Hiển thị kết quả ─────────────────────────────────────────────────────────
if st.session_state.analyze_result is not None:
    _show_analyze_result(st.session_state.analyze_result)