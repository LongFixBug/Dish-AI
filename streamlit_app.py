"""Streamlit UI — FoodAI: nhận diện món ăn Việt + phân tích dinh dưỡng từ ảnh.

Phiên bản Jul 23: chỉ còn 1 tab Analyze.
  - Upload ảnh → CV local + Vision → dishes[{dish_name, gram, is_side, total_*}]
  - Mỗi món tra vn_dishes (+ Qdrant) + vn_ingredients (món ăn kèm) → scale gram
  - Món mới → dùng nutrition Vision cho response và đưa vào hàng chờ duyệt
  - KHÔNG còn per-ingredient edit / quick-add / Contribute / Search tab

Usage:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import os
import unicodedata

import httpx
import streamlit as st

from schemas.nutrition import calculate_adjusted_totals

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
    """Hiển thị control khẩu phần và tính lại nutrition riêng từng món."""

    items = totals.get("items", [])
    if not items:
        st.caption("_(Chưa có dữ liệu dinh dưỡng để tính)_")
        return

    st.markdown("#### 🔢 Điều chỉnh khẩu phần từng món")
    adjusted_amounts: list[float] = []
    selected_units: list[str] = []
    with st.expander(f"🍽️ Các món trong ảnh ({len(items)} món)", expanded=True):
        for index, item in enumerate(items):
            item_name = item.get("item_name", f"Món {index + 1}")
            original_grams = max(0.0, float(item.get("grams", 0) or 0))
            badge = "✅" if item.get("found_in_db") else "🆕"
            default_unit = _default_serving_unit(item_name)
            unit_options = [default_unit, "g" if default_unit == "ml" else "ml"]

            name_col, amount_col, unit_col = st.columns([3, 1.4, 1])
            with name_col:
                st.markdown(f"**{badge} {item_name}**")
                st.caption(f"Vision ước tính: {original_grams:.0f}g")
            with amount_col:
                amount = st.number_input(
                    f"Khẩu phần {item_name}",
                    min_value=0.0,
                    max_value=5000.0,
                    value=original_grams,
                    step=10.0,
                    key=_item_control_key("amount", index, item),
                    label_visibility="collapsed",
                    help=f"Tăng hoặc giảm riêng khẩu phần {item_name}.",
                )
            with unit_col:
                unit = st.selectbox(
                    f"Đơn vị {item_name}",
                    unit_options,
                    key=_item_control_key("unit", index, item),
                    label_visibility="collapsed",
                )
            adjusted_amounts.append(amount)
            selected_units.append(unit)

    if "ml" in selected_units:
        st.caption("Món lỏng được quy đổi gần đúng **1 ml ≈ 1 g** để tính dinh dưỡng.")

    adjusted = calculate_adjusted_totals(items, adjusted_amounts)
    st.markdown("#### 📊 Tổng dinh dưỡng theo khẩu phần đã chọn")
    metric_cols = st.columns(5)
    metric_cols[0].metric("🔥 Calories", f"{adjusted['total_calories']:.0f} kcal")
    metric_cols[1].metric("🥩 Protein", f"{adjusted['total_protein_g']:.1f} g")
    metric_cols[2].metric("🧈 Fat", f"{adjusted['total_fat_g']:.1f} g")
    metric_cols[3].metric("🍚 Carbs", f"{adjusted['total_carbs_g']:.1f} g")
    metric_cols[4].metric("🌿 Fiber", f"{adjusted['total_fiber_g']:.1f} g")
    st.caption(f"Tổng lượng quy đổi: **{adjusted['total_grams']:.0f}g**")

    # ── Confidence & missing ─────────────────────────────────────────────
    conf = totals.get("confidence_score")
    missing = totals.get("missing_ingredients", [])
    foot = []
    if conf is not None:
        foot.append(f"Độ phủ dữ liệu dinh dưỡng DB: **{conf:.0%}**")
    if missing:
        foot.append(f"Thiếu DB: {len(missing)} món (đang dùng nutrition Vision)")
    if foot:
        st.caption(" · ".join(foot))



def _default_serving_unit(item_name: str) -> str:
    """Món lỏng mặc định nhập thể tích, món đặc mặc định nhập khối lượng."""
    normalized = _normalize_dish_name(item_name).replace("_", " ")
    liquid_terms = ("canh", "sup", "nuoc", "tra", "ca phe", "sua")
    return "ml" if any(term in normalized for term in liquid_terms) else "g"


def _item_control_key(prefix: str, index: int, item: dict) -> str:
    """Key ổn định trong một kết quả, nhưng đổi khi gram gốc thay đổi."""
    name = _normalize_dish_name(str(item.get("item_name", index)))
    grams = float(item.get("grams", 0) or 0)
    return f"serving_{prefix}_{index}_{name}_{grams:.1f}"


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
    mime_type = uploaded_type or "image/jpeg"
    extension = {"image/png": "png", "image/webp": "webp"}.get(mime_type, "jpg")
    files = {"file": (f"{slug}.{extension}", uploaded_bytes, mime_type)}
    form = {"correct_dish_name": correct_name.strip()}
    r = _api("post", "/api/v1/feedback/training-data", files=files, data=form)
    if r.status_code == 200:
        total = r.json().get("total_images", "?")
        st.success(f"✅ Đã lưu ảnh '{correct_name}' vào training data ({total} ảnh)")
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
    "→ scale dinh dưỡng DB theo gram ảnh. Món chưa có DB → dùng Vision và tự thêm."
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
            for key in list(st.session_state):
                if key.startswith("serving_amount_") or key.startswith("serving_unit_"):
                    del st.session_state[key]
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

    staged = data.get("staged_dishes", [])
    if staged:
        st.info(
            f"🕒 **{len(staged)} món mới đang chờ duyệt:** " + ", ".join(staged)
            + " — dinh dưỡng Vision chỉ dùng tạm cho kết quả hiện tại."
        )

    if data.get("dish_name"):
        st.subheader(f"🍽️ {data['dish_name']}")

    # ── Danh sách món sau khi đối chiếu DB ──────────────────────────────
    dishes = data.get("dishes", [])
    if dishes:
        with st.expander(f"👁️ Kết quả đối chiếu {len(dishes)} món"):
            for d in dishes:
                tag = "🥢 món kèm" if d.get("is_side") else "🍚 món chính"
                source_tag = "DB" if d.get("found_in_db") else "Vision · món mới"
                vision_name = d.get("vision_dish_name")
                match_note = f" · Vision: {vision_name}" if vision_name else ""
                st.write(
                    f"- **{d['dish_name']}** — {d['grams']:.0f}g "
                    f"({tag} · {source_tag}{match_note})"
                )

    nutrition = data.get("nutrition")
    if nutrition:
        _nutrition_card(nutrition)
    elif not data.get("error"):
        st.info("Không có dữ liệu dinh dưỡng.")

    # ── Feedback: gửi ảnh đúng label để train CV sau ────────────────────
    st.markdown("---")
    with st.expander("📤 Gửi ảnh đúng tên (training data cho CV local)"):
        suggested = next(
            (
                dish.get("dish_name", "")
                for dish in data.get("dishes", [])
                if not dish.get("is_side")
            ),
            data.get("dish_name") or "",
        )
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
