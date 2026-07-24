"""Legacy migration: tạo SQL function vn_norm — normalize dấu tiếng Việt.

vn_norm(text) → text: bỏ dấu + lower, dùng `lower(translate(input, from, to))`
với 148 ký tự có dấu VN → không dấu (gồm đ→d, Đ→D, cả HOA + thường).

IMMUTABLE → dùng được trong WHERE + (sau này) expression index.
CREATE OR REPLACE → idempotent, chạy lại không lỗi.

Giả định: input NFC (1 codepoint/dấu). NFD (combining marks) sẽ KHÔNG match —
chấp nhận cho pha này (data qua asyncpg/Python thường NFC). Nếu sau này miss,
thêm unicodedata.normalize('NFC', q) ở app-layer trước khi truyền vào query.

Dùng ở 4 điểm ILIKE: bọc cột + pattern bằng func.vn_norm(...) rồi .op('ILIKE').
Xem plan: /Users/nguyenhailong/.claude/plans/cosmic-wibbling-horizon.md

Usage:
    DEBUG=false python scripts/migrate_normalize_vn.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from backend.db.postgres import engine  # noqa: E402


# ─── SQL ────────────────────────────────────────────────────────────────────

# 148 ký tự from / 148 ký tự to, 1-1, gồm cả HOA + thường, đ/Đ → d/D.
# Cấu trúc: 15 base letters × biến thể dấu, AĂÂ→A, D→D, Đ→D, EÊ→E, I→I,
# OÔƠ→O, UƯ→U, Y→Y. lower() chạy SAU translate → bắt buộc map cả HOA.
CREATE_VN_NORM_SQL = """
CREATE OR REPLACE FUNCTION vn_norm(input text) RETURNS text
LANGUAGE sql IMMUTABLE
AS $$
    SELECT lower(translate(
        input,
        'AÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬDĐEÉÈẺẼẸÊẾỀỂỄỆIÍÌỈĨỊOÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢUÚÙỦŨỤƯỨỪỬỮỰYÝỲỶỸỴaáàảãạăắằẳẵặâấầẩẫậdđeéèẻẽẹêếềểễệiíìỉĩịoóòỏõọôốồổỗộơớờởỡợuúùủũụưứừửữựyýỳỷỹỵ',
        'AAAAAAAAAAAAAAAAAADDEEEEEEEEEEEEIIIIIIOOOOOOOOOOOOOOOOOOUUUUUUUUUUUUYYYYYYaaaaaaaaaaaaaaaaaaddeeeeeeeeeeeeiiiiiioooooooooooooooooouuuuuuuuuuuuyyyyyy'
    ));
$$;
"""


async def migrate() -> None:
    """Tạo (hoặc thay) function vn_norm trong DB."""
    async with engine.begin() as conn:
        await conn.execute(text(CREATE_VN_NORM_SQL))
        print("✅ vn_norm(text) đã tạo (IMMUTABLE, 148 ký tự map)")

        # Smoke test ngay: verify vài case quan trọng
        checks = [
            ("Sườn lợn", "suon lon"),
            ("CƠM CHIÊN", "com chien"),
            ("bún chả Hà Nội", "bun cha ha noi"),
        ]
        for inp, expected in checks:
            result = await conn.execute(
                text("SELECT vn_norm(:v)"), {"v": inp}
            )
            got = result.scalar_one()
            status = "✅" if got == expected else "❌"
            print(f"  {status} vn_norm({inp!r}) = {got!r} (mong {expected!r})")

    print("\n👉 4 điểm ILIKE trong services/ cần bọc func.vn_norm(...).op('ILIKE')")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
