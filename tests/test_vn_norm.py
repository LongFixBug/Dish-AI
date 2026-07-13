"""Unit tests cho SQL function vn_norm (normalize dấu tiếng Việt).

vn_norm(text) → text: bỏ dấu + lower. IMMUTABLE, dùng translate 148 ký tự.
Giả định input NFC (1 codepoint/dấu) — NFD (combining marks) sẽ không match.

Test gọi trực tiếp `SELECT vn_norm(:input)` qua async session thật (DB 5432).
"""

from sqlalchemy import text

from tests.conftest import db_session  # noqa: F401  (fixture)


async def _vn_norm(session, value: str | None) -> str | None:
    """Helper: gọi SELECT vn_norm(:v), trả kết quả (hoặc None khi input None)."""
    result = await session.execute(
        text("SELECT vn_norm(:v) AS norm"), {"v": value}
    )
    return result.scalar_one()


# ─── Bỏ dấu + lower ──────────────────────────────────────────────────────────


async def test_vn_norm_removes_diacritics_and_lowers(db_session) -> None:
    """'Sườn lợn' → 'suon lon' (bỏ dấu ư/ờ/ơ + lower)."""
    assert await _vn_norm(db_session, "Sườn lợn") == "suon lon"


async def test_vn_norm_preserves_no_diacritics(db_session) -> None:
    """Chuỗi không dấu giữ nguyên (chỉ lower nếu có hoa)."""
    assert await _vn_norm(db_session, "suon") == "suon"
    assert await _vn_norm(db_session, "com chin") == "com chin"


async def test_vn_norm_uppercase_to_lower(db_session) -> None:
    """'CƠM CHIÊN' (hoa + dấu) → 'com chien'."""
    assert await _vn_norm(db_session, "CƠM CHIÊN") == "com chien"


async def test_vn_norm_d_to_d(db_session) -> None:
    """'đ' → 'd' và 'Đ' → 'd' (chữ đ riêng, không phải d+combining)."""
    assert await _vn_norm(db_session, "bún chả Hà Nội") == "bun cha ha noi"
    assert await _vn_norm(db_session, "ĐỒNG Nai") == "dong nai"


async def test_vn_norm_mixed_diacritics(db_session) -> None:
    """Đủ loại dấu (ấ/ư/ễ/ự/ỷ) → base ASCII."""
    assert await _vn_norm(db_session, "ấưễựỷ") == "aueuy"


# ─── Edge cases ──────────────────────────────────────────────────────────────


async def test_vn_norm_empty_string(db_session) -> None:
    """Chuỗi rỗng → rỗng."""
    assert await _vn_norm(db_session, "") == ""


async def test_vn_norm_none(db_session) -> None:
    """NULL input → NULL (translate(NULL, ...) = NULL, không crash)."""
    assert await _vn_norm(db_session, None) is None


async def test_vn_norm_idempotent(db_session) -> None:
    """Áp 2 lần = áp 1 lần (đã không dấu thì bỏ dấu nữa không đổi)."""
    once = await _vn_norm(db_session, "Sườn lợn")
    twice = await _vn_norm(db_session, once)
    assert once == twice == "suon lon"
