"""Từ vựng thực đơn Việt dùng chung cho tra catalog và soi tên nhận diện.

Tách riêng vì hai tầng đều cần đúng một bộ luật "họ món": ``dishes`` lọc ứng
viên Qdrant, còn ``recognition_cascade`` soi xem tên catalog có phản bội tên
album/Vision không. Trước đây mỗi bên tự chuẩn hóa dấu một kiểu — bên tách
theo khoảng trắng nên nuốt luôn dấu ngoặc, bên tách theo regex thì không —
khiến cùng một cặp tên cho ra hai kết luận trái ngược.
"""

import re
import unicodedata

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")

# Từ mở đầu đủ để chia thực đơn Việt thành nhóm lớn.
DISH_FAMILY_TOKENS = frozenset({
    "banh", "bun", "canh", "chao", "com", "goi", "hu", "lau", "mi",
    "pho", "tieu", "xoi",
})

# Từ đệm không mang thông tin phân biệt món: "bánh mì kẹp thịt" và
# "bánh mì thịt" là một.
MENU_STOP_TOKENS = frozenset({"cac", "kem", "kep", "loai", "mon", "va", "voi"})

# Cặp từ mở đầu tạo thành một họ món trọn vẹn. Một mình "bánh" chưa nói lên
# món gì: "bánh mì" và "bánh cuốn" là hai họ khác hẳn nhau, nên phải so cả
# cặp thay vì so token đầu.
CANONICAL_FAMILY_NAMES = {
    ("banh", "beo"): "Bánh bèo",
    ("banh", "can"): "Bánh căn",
    ("banh", "canh"): "Bánh canh",
    ("banh", "chung"): "Bánh chưng",
    ("banh", "cuon"): "Bánh cuốn",
    ("banh", "duc"): "Bánh đúc",
    ("banh", "gio"): "Bánh giò",
    ("banh", "khot"): "Bánh khọt",
    ("banh", "mi"): "Bánh mì",
    ("banh", "pia"): "Bánh pía",
    ("banh", "tet"): "Bánh tét",
    ("banh", "trang"): "Bánh tráng",
    ("banh", "xeo"): "Bánh xèo",
    ("bun", "bo"): "Bún bò",
    ("bun", "cha"): "Bún chả",
    ("bun", "dau"): "Bún đậu",
    ("bun", "mam"): "Bún mắm",
    ("bun", "rieu"): "Bún riêu",
    ("canh", "chua"): "Canh chua",
    ("cao", "lau"): "Cao lầu",
    ("chao", "long"): "Cháo lòng",
    ("com", "tam"): "Cơm tấm",
    ("goi", "cuon"): "Gỏi cuốn",
    ("ha", "cao"): "Há cảo",
    ("hu", "tieu"): "Hủ tiếu",
    ("mi", "quang"): "Mì Quảng",
    ("nem", "chua"): "Nem chua",
    ("nem", "nuong"): "Nem nướng",
    ("pho", "bo"): "Phở bò",
    ("pho", "ga"): "Phở gà",
    ("xoi", "xeo"): "Xôi xéo",
}


def accent_tokens(name: str) -> list[str]:
    """Tách tên món thành token thường, bỏ dấu, bỏ ký tự không phải chữ/số.

    Bỏ dấu câu là điều bắt buộc: "Bún bò giò heo (Huế)" phải cho ra token
    ``hue`` chứ không phải ``(hue)``, nếu không tên đúng lại bị coi là lệch.
    """
    decomposed = unicodedata.normalize("NFKD", name.casefold().replace("đ", "d"))
    stripped = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return _TOKEN_PATTERN.findall(stripped)


def menu_tokens(name: str) -> set[str]:
    """Tập token mang nghĩa của tên món (đã bỏ dấu và bỏ từ đệm)."""
    return set(accent_tokens(name)) - MENU_STOP_TOKENS


def family_pair(name: str) -> tuple[str, ...]:
    """Cặp token mở đầu, dùng để so họ món giữa hai tên."""
    return tuple(accent_tokens(name)[:2])
