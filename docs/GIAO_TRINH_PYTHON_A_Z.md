# Giáo trình Python từ A đến Z — kiểu "làm theo từng bước"

> Cách dùng giáo trình này: đọc đến đâu **gõ code đến đó** (gõ tay, KHÔNG copy-paste — tay gõ thì đầu mới nhớ),
> chạy lên xem kết quả, rồi đọc phần giải thích từng dòng. Giống xem video hướng dẫn nhưng bạn chủ động tốc độ.
> Thuật ngữ có giải thích trong ngoặc `( )`. Bài tập chỉ có GỢI Ý, không có lời giải sẵn — bạn phải tự viết
> (kẹt thì hỏi Claude, sẽ được dẫn dắt từng bước).
>
> Giáo trình này dạy Python từ số 0. Học xong hãy chuyển sang [PYTHON_QUA_FOODAI.md](PYTHON_QUA_FOODAI.md)
> để soi các khái niệm này trong code project thật.

---

# PHẦN 0 — SETUP: chuẩn bị "bàn học"

## Bước 1: Tạo thư mục học riêng (đừng học trong repo FoodAI)

Mở Terminal (ứng dụng gõ lệnh trên Mac: bấm `Cmd + Space`, gõ "Terminal", Enter) và gõ:

```bash
mkdir -p ~/hoc-python && cd ~/hoc-python
```

Giải thích: `mkdir -p` tạo thư mục `hoc-python` trong Home (`~` = thư mục nhà của bạn), `&&` nghĩa là "xong thì làm tiếp", `cd` là "đi vào thư mục đó".

## Bước 2: Kiểm tra công cụ

Máy bạn đã có sẵn `uv` (trình quản lý Python hiện đại — tự lo cài Python và thư viện). Kiểm tra:

```bash
uv --version
```

Khởi tạo project học tập (uv tạo sẵn khung):

```bash
uv init && uv run python --version
```

Thấy `Python 3.x.x` hiện ra là xong. Từ giờ, chạy file Python nào cũng bằng `uv run python <tên_file>.py`.

## Bước 3: Editor (trình soạn code)

Dùng VS Code (miễn phí): mở VS Code → `File > Open Folder` → chọn `hoc-python`. Cài extension "Python" của Microsoft (biểu tượng ô vuông bên trái → gõ Python → Install) để có tô màu code + gạch đỏ báo lỗi.

## Bước 4: Hai chế độ chạy code

- **Chế độ file** — viết code vào file `.py`, chạy: `uv run python bai01.py`. Dùng cho bài học.
- **Chế độ REPL** (Read-Eval-Print Loop — "vọc thử": gõ một dòng, Python trả lời ngay):

```bash
uv run python
```

Gõ thử `2 + 3` rồi Enter → thấy `5`. Thoát bằng `exit()`. REPL là "giấy nháp" — cứ nghi ngờ điều gì, mở REPL thử ngay.

---

# PHẦN 1 — NHẬP MÔN

## Bài 1: Chương trình đầu tiên — print và biến

🎯 **Mục tiêu:** chạy được chương trình đầu tiên, hiểu biến là gì.

📝 Tạo file `bai01.py`, gõ:

```python
# Dòng bắt đầu bằng dấu # là comment (ghi chú) — Python bỏ qua, chỉ để người đọc
ten_mon = "Phở bò"        # biến kiểu str (chuỗi ký tự) — luôn có ngoặc kép
so_calo = 450             # biến kiểu int (số nguyên)
gia_tien = 45.5           # biến kiểu float (số thực — có phần thập phân)
con_hang = True           # biến kiểu bool (đúng/sai) — True hoặc False, viết hoa chữ đầu

print("Xin chào, đây là món:", ten_mon)
print(f"{ten_mon} có {so_calo} kcal, giá {gia_tien} nghìn")   # f-string: nhét biến vào chuỗi
print(type(so_calo))      # type() cho biết kiểu của biến
```

▶ Chạy: `uv run python bai01.py`

🔍 **Giải thích:**
- **Biến** = cái hộp có dán nhãn tên, bên trong đựng một giá trị. `ten_mon = "Phở bò"` đọc là *"bỏ chuỗi Phở bò vào hộp tên ten_mon"* (dấu `=` là GÁN, không phải "bằng" như toán).
- **f-string**: chuỗi có chữ `f` đằng trước, trong đó `{ten_bien}` được thay bằng giá trị thật. Đây là cách in đẹp nhất, dùng suốt đời.
- Tên biến: chữ thường, nối bằng `_` (gọi là snake_case — kiểu con rắn). Không dấu, không bắt đầu bằng số.

💪 **Bài tập 1:** Tạo `bt01.py` khai báo 4 biến về BẢN THÂN bạn (tên, tuổi, chiều cao mét, có đang tìm việc không) rồi in ra một đoạn tự giới thiệu 2 dòng bằng f-string. Chạy không lỗi là đạt.

## Bài 2: Nhận input và tính toán

🎯 **Mục tiêu:** chương trình biết "hỏi" người dùng, hiểu ép kiểu.

📝 File `bai02.py`:

```python
ten = input("Bạn ăn món gì? ")                 # input() dừng lại chờ người dùng gõ
gram_text = input("Bao nhiêu gram? ")           # ⚠️ input LUÔN trả về chuỗi, kể cả gõ số
gram = float(gram_text)                         # ép kiểu (convert) chuỗi "300" → số 300.0

calo_moi_gram = 1.5
tong_calo = gram * calo_moi_gram                # toán tử: + - * / , ** (mũ), % (chia dư)

print(f"{ten} {gram:.0f}g ≈ {tong_calo:.1f} kcal")   # :.1f = làm tròn 1 chữ số thập phân
```

🔍 **Điểm chết người của bài này:** `input()` trả về `str`. `"300" * 1.5` sẽ nổ lỗi `TypeError` — chuỗi không nhân được với số thực. Phải `float(...)` hoặc `int(...)` trước. Đây là lỗi số 1 của người mới.

💪 **Bài tập 2:** Viết `bt02.py` — máy tính BMI: hỏi cân nặng (kg) và chiều cao (m), in BMI = cân nặng / (chiều cao bình phương — dùng `**`), làm tròn 1 số lẻ. Thử với 60kg, 1.7m → phải ra ~20.8.

## Bài 3: Rẽ nhánh if / elif / else

🎯 **Mục tiêu:** chương trình biết "quyết định".

📝 File `bai03.py`:

```python
calo = float(input("Bữa này bao nhiêu kcal? "))

if calo > 800:                       # nếu điều kiện đúng → chạy khối thụt vào bên dưới
    print("Ăn hơi nhiều đó nha!")
elif calo >= 400:                    # elif = "còn nếu" — chỉ xét khi if trên sai
    print("Một bữa vừa phải.")
else:                                # else = "còn lại thì"
    print("Bữa nhẹ, nhớ đừng để đói.")

print("Cảm ơn đã dùng app!")         # dòng này KHÔNG thụt → luôn chạy dù rẽ nhánh nào
```

🔍 **Điều quan trọng nhất của cả Python nằm ở đây: THỤT LỀ (indentation).** Python không dùng ngoặc `{}` như ngôn ngữ khác — khối lệnh được xác định bằng thụt lề 4 dấu cách. Thụt sai = chương trình sai hoặc chạy sai nghĩa. Ẩn dụ: thụt lề là "ai thuộc quyền quản lý của ai" trong sơ đồ công ty.
- So sánh: `==` (bằng — chú ý HAI dấu bằng), `!=` (khác), `>=`, `<=`. Ghép điều kiện: `and`, `or`, `not`.

💪 **Bài tập 3:** `bt03.py` — phân loại BMI từ bài 2: dưới 18.5 in "gầy", 18.5–24.9 "bình thường", 25–29.9 "thừa cân", còn lại "béo phì". Thử đủ 4 trường hợp.

## Bài 4: Vòng lặp for / while

🎯 **Mục tiêu:** bắt máy làm việc lặp đi lặp lại.

📝 File `bai04.py`:

```python
mon_an = ["phở", "bún chả", "cơm tấm"]      # list: dãy hộp đánh số từ 0

for mon in mon_an:                           # "với TỪNG mon trong mon_an, làm khối dưới"
    print(f"- {mon}")

for i, mon in enumerate(mon_an):             # enumerate: vừa lấy số thứ tự vừa lấy giá trị
    print(f"{i + 1}. {mon}")                 # i chạy 0,1,2 → cộng 1 cho đẹp

tong = 0
for calo in [450, 550, 620]:
    tong = tong + calo                       # cộng dồn (viết tắt: tong += calo)
print(f"Tổng: {tong} kcal")

dem = 3
while dem > 0:                               # while: lặp CHỪNG NÀO điều kiện còn đúng
    print(f"Đếm ngược: {dem}")
    dem -= 1                                 # quên dòng này → lặp vô hạn (Ctrl+C để thoát!)
```

🔍 `for` dùng khi biết duyệt qua cái gì; `while` dùng khi lặp đến-khi-nào-đó. `range(5)` sinh dãy 0..4: `for i in range(5)`.

💪 **Bài tập 4:** `bt04.py` — in bảng cửu chương 7 (7 × 1 đến 7 × 10) bằng for + f-string, mỗi dòng dạng `7 x 3 = 21`.

---

# PHẦN 2 — CƠ BẢN

## Bài 5: Hàm — đóng gói việc để tái dùng

🎯 **Mục tiêu:** viết hàm có tham số và giá trị trả về.

📝 File `bai05.py`:

```python
def tinh_calo(gram: float, calo_moi_gram: float) -> float:
    """Tính calo của một món theo khối lượng."""    # docstring: mô tả hàm làm gì
    return gram * calo_moi_gram                     # return: TRẢ kết quả về cho người gọi

def phan_loai_bua_an(calo: float) -> str:
    if calo > 800:
        return "nhiều"          # return kết thúc hàm NGAY — kiểu "early return"
    if calo >= 400:
        return "vừa"
    return "nhẹ"

# --- chương trình chính ---
calo_pho = tinh_calo(350, 1.3)                      # gọi hàm, hứng kết quả vào biến
print(f"Phở 350g ≈ {calo_pho:.0f} kcal → bữa {phan_loai_bua_an(calo_pho)}")
```

🔍 **Giải thích:**
- `def` = define (định nghĩa). Hàm là "máy chế biến": bỏ nguyên liệu vào (tham số), nhận thành phẩm ra (`return`). Định nghĩa xong hàm CHƯA chạy — chỉ chạy khi được GỌI `tinh_calo(350, 1.3)`.
- `gram: float` và `-> float` là type hints (chú thích kiểu — không bắt buộc nhưng chuyên nghiệp, project FoodAI dùng 100%).
- `print` khác `return`: print chỉ HIỆN ra màn hình cho người xem; return ĐƯA giá trị cho code dùng tiếp. Người mới nhầm cặp này nhiều nhất.
- Kiểu "early return" (trả sớm — gặp kết luận là return luôn, khỏi else chồng chất) là style chuẩn của FoodAI.

💪 **Bài tập 5:** `bt05.py` — viết hàm `bmi(can_nang, chieu_cao)` trả về số BMI và hàm `phan_loai(bmi_value)` trả về nhãn phân loại (tái dùng logic bài 3 nhưng bằng early return). Chương trình chính gọi cả hai và in kết quả.

## Bài 6: Dict — tra cứu theo nhãn

🎯 **Mục tiêu:** dùng dict (từ điển — tủ hồ sơ tra theo nhãn, không theo số thứ tự).

📝 File `bai06.py`:

```python
bang_calo = {                       # key (khóa): value (giá trị)
    "phở bò": 1.3,                  # "phở bò" là key, 1.3 là value (kcal mỗi gram)
    "cơm tấm": 1.6,
    "gỏi cuốn": 0.9,
}

print(bang_calo["cơm tấm"])          # tra theo key → 1.6
print(bang_calo.get("bún bò"))       # .get: key không có → trả None (không nổ lỗi)
print(bang_calo.get("bún bò", 0))    # .get với giá trị mặc định → 0

bang_calo["bún bò"] = 1.2            # thêm cặp mới
for mon, calo_g in bang_calo.items():          # duyệt cả key lẫn value
    print(f"{mon}: {calo_g} kcal/g")
```

🔍 Khác biệt sống còn: `bang_calo["bún bò"]` khi key chưa tồn tại → nổ lỗi `KeyError`; `.get()` thì trả `None` êm ái. Backend FoodAI dùng `.get()` khắp nơi khi đọc kết quả từ Vision API — vì không tin LLM luôn trả đủ field.

💪 **Bài tập 6:** `bt06.py` — làm "menu tính tiền": dict 5 món với giá tiền; hỏi người dùng gõ tên món (vòng while, gõ "xong" thì dừng); món có trong menu thì cộng tiền, không có thì báo "quán không bán"; cuối cùng in tổng. Đây là bài tổng hợp while + dict + if.

## Bài 7: Đọc/ghi file và exception

🎯 **Mục tiêu:** lưu dữ liệu ra file, xử lý lỗi không cho chương trình sập.

📝 File `bai07.py`:

```python
import json                                   # module có sẵn để đọc/ghi JSON

nhat_ky = [
    {"mon": "phở bò", "calo": 455},
    {"mon": "cà phê sữa", "calo": 120},
]

with open("nhat_ky.json", "w", encoding="utf-8") as f:    # "w" = write (ghi đè)
    json.dump(nhat_ky, f, ensure_ascii=False, indent=2)   # đổ list Python ra file JSON
# hết khối with → file TỰ đóng, kể cả khi lỗi giữa chừng

try:
    with open("nhat_ky.json", encoding="utf-8") as f:     # không ghi "w" = chế độ đọc
        du_lieu = json.load(f)                            # JSON → list/dict Python
    tong = sum(item["calo"] for item in du_lieu)          # sum + generator expression
    print(f"Đã ăn {tong} kcal")
except FileNotFoundError:                                  # nếu file không tồn tại
    print("Chưa có nhật ký nào — hôm nay là ngày đầu tiên!")
```

🔍 **Giải thích:**
- `with open(...) as f` là context manager (trình quản lý ngữ cảnh — "mượn đồ tự động trả"): hết khối là file tự đóng. Không bao giờ mở file mà thiếu `with`.
- JSON (định dạng văn bản để trao đổi dữ liệu — chính là format mà API FoodAI nói chuyện với mobile app): `json.dump` = Python → file, `json.load` = file → Python.
- `try/except`: "thử làm, hỏng thì rẽ nhánh xử lý". Bắt lỗi CỤ THỂ (`FileNotFoundError`) chứ đừng `except Exception` nuốt mọi lỗi — nuốt lỗi là giấu bệnh.

💪 **Bài tập 7:** `bt07.py` — nâng cấp bài 6: sau mỗi lần tính tiền, ghi hóa đơn (list các món + tổng) ra `hoa_don.json`; khi khởi động, nếu file đã tồn tại thì đọc và in "lần trước bạn tiêu X đồng". Chạy 2 lần liên tiếp để thấy tác dụng.

## Bài 8: Class — tự tạo "khuôn" dữ liệu

🎯 **Mục tiêu:** hiểu class (lớp — khuôn đúc) và object (đối tượng — sản phẩm đúc từ khuôn).

📝 File `bai08.py`:

```python
class MonAn:
    """Một món ăn với tên và calo mỗi gram."""

    def __init__(self, ten: str, calo_moi_gram: float):   # hàm khởi tạo — chạy lúc "đúc"
        self.ten = ten                       # self = "chính sản phẩm đang được đúc"
        self.calo_moi_gram = calo_moi_gram   # gắn dữ liệu vào sản phẩm

    def tinh_calo(self, gram: float) -> float:   # method (phương thức — hàm của class)
        return gram * self.calo_moi_gram

    def __repr__(self) -> str:                   # cách object tự giới thiệu khi print
        return f"MonAn({self.ten}, {self.calo_moi_gram} kcal/g)"

pho = MonAn("Phở bò", 1.3)          # đúc một object từ khuôn — KHÔNG cần gọi __init__
com = MonAn("Cơm tấm", 1.6)         # mỗi object có dữ liệu RIÊNG
print(pho.tinh_calo(400))            # 520.0 — gọi method qua dấu chấm
print(com)                           # MonAn(Cơm tấm, 1.6 kcal/g) — nhờ __repr__
```

🔍 Ẩn dụ: class là **khuôn bánh**, object là **cái bánh**. `self` là từ khiến người mới sợ nhất — nó chỉ đơn giản là "cái bánh đang được nói tới": khi gọi `pho.tinh_calo(400)`, Python tự hiểu `self` = `pho`. Các method `__tên__` (hai gạch dưới — gọi là dunder) là "móc treo" để Python gọi ngầm: `__init__` lúc tạo, `__repr__` lúc print.

💪 **Bài tập 8:** `bt08.py` — viết class `BuaAn` có `__init__` nhận tên bữa ("sáng"/"trưa"/"tối"), có method `them_mon(mon: MonAn, gram: float)` lưu vào một list nội bộ, và method `tong_calo()` trả tổng. Tạo một bữa trưa 2 món và in tổng. (Gợi ý: trong `__init__` tạo `self.cac_mon = []`.)

---

# PHẦN 3 — NÂNG CAO

## Bài 9: Comprehension + sort/filter dữ liệu

🎯 **Mục tiêu:** xử lý danh sách kiểu "một dòng ăn ngay" — phong cách code của FoodAI.

📝 File `bai09.py`:

```python
bua_an = [
    {"mon": "phở bò", "calo": 455},
    {"mon": "trà sữa", "calo": 350},
    {"mon": "gỏi cuốn", "calo": 90},
    {"mon": "cơm tấm", "calo": 640},
]

ten_cac_mon = [item["mon"] for item in bua_an]                      # list comprehension
mon_nhieu_calo = [i["mon"] for i in bua_an if i["calo"] > 300]      # kèm điều kiện lọc
tong = sum(item["calo"] for item in bua_an)                          # generator expression

sap_xep = sorted(bua_an, key=lambda item: item["calo"], reverse=True)   # sort theo calo giảm dần
print(ten_cac_mon)
print(mon_nhieu_calo)
print(f"Tổng {tong} kcal, nhiều nhất: {sap_xep[0]['mon']}")
```

🔍 Đọc comprehension từ TRÁI qua như câu văn: *"lấy `item['mon']`... với từng item trong bua_an... nếu calo > 300"*. `lambda item: item["calo"]` là hàm nặc danh một dòng làm "thước đo" cho sorted. Chú ý cả 3 dòng đều **tạo dữ liệu MỚI**, không sửa `bua_an` gốc — nguyên tắc immutable của project.

💪 **Bài tập 9:** từ list `bua_an` trên: (a) tạo list các món dưới 400 kcal, (b) tính calo trung bình, (c) tạo dict `{tên món: calo}` bằng **dict comprehension** — cú pháp `{k: v for ...}` (tự tra thêm), (d) tìm món calo thấp nhất bằng `min(..., key=...)`.

## Bài 10: Generator và yield

🎯 **Mục tiêu:** hiểu hàm "nhả từng viên kẹo" — nền của streaming và tiết kiệm bộ nhớ.

📝 File `bai10.py`:

```python
def doc_theo_dong(duong_dan: str):
    """Generator: nhả từng dòng file, không nuốt cả file vào RAM."""
    with open(duong_dan, encoding="utf-8") as f:
        for dong in f:
            yield dong.strip()        # yield: nhả ra một giá trị rồi ĐỨNG CHỜ tại đây

def dem_nguoc(n: int):
    while n > 0:
        yield n
        n -= 1
    yield "Bắn pháo hoa! 🎆"

for x in dem_nguoc(3):
    print(x)                          # 3, 2, 1, Bắn pháo hoa!
```

🔍 Hàm có `yield` khi gọi KHÔNG chạy ngay — nó trả về một generator (máy bán kẹo); mỗi vòng `for` lấy một viên, hàm chạy tiếp từ chỗ đứng chờ. So với `return` (trả một lần rồi chết), `yield` trả nhiều lần và **nhớ trạng thái giữa các lần**. FoodAI dùng đúng cơ chế này ở 3 chỗ: phát session database (dùng xong tự dọn), vòng đời app, và streaming chat từng chữ (xem mục 8 của [PYTHON_QUA_FOODAI.md](PYTHON_QUA_FOODAI.md)).

💪 **Bài tập 10:** viết generator `fibonacci(n)` nhả n số Fibonacci đầu tiên (dãy 1, 1, 2, 3, 5, 8... — số sau bằng tổng hai số trước), rồi dùng nó in 10 số đầu. Cấm tạo list — phải `yield` từng số.

## Bài 11: Decorator — tự làm cái "mũ" đội cho hàm

🎯 **Mục tiêu:** hiểu decorator bằng cách TỰ VIẾT một cái (hiểu rồi thì nhìn `@router.post` của FastAPI hết thấy ma thuật).

📝 File `bai11.py`:

```python
import time
import functools

def do_thoi_gian(ham_goc):                       # decorator = hàm nhận HÀM, trả HÀM đã độ
    @functools.wraps(ham_goc)                    # giữ lại tên/docstring của hàm gốc
    def ham_da_do(*args, **kwargs):              # *args/**kwargs: hứng mọi tham số bất kỳ
        bat_dau = time.perf_counter()
        ket_qua = ham_goc(*args, **kwargs)       # chạy hàm gốc như bình thường
        het = time.perf_counter() - bat_dau
        print(f"⏱ {ham_goc.__name__} chạy hết {het:.4f}s")
        return ket_qua
    return ham_da_do

@do_thoi_gian                                    # tương đương: tinh_tong = do_thoi_gian(tinh_tong)
def tinh_tong(n: int) -> int:
    return sum(range(n))

print(tinh_tong(10_000_000))                     # in tổng + tự động in thời gian chạy
```

🔍 Đọc từ trong ra: `ham_da_do` bọc quanh `ham_goc` — làm thêm việc trước/sau (đo giờ) nhưng không đụng ruột hàm gốc. Dòng `@do_thoi_gian` chỉ là đường tắt của phép gán bên comment. FastAPI làm y hệt: `@router.post("/analyze")` bọc hàm của bạn thêm lớp "nhận HTTP request, validate, trả JSON".

💪 **Bài tập 11:** viết decorator `@thu_lai(so_lan=3)` — hàm gốc nổ exception thì tự chạy lại tối đa 3 lần, hết lượt thì ném lỗi ra. (Khó — decorator CÓ tham số cần 3 tầng hàm lồng nhau; đây chính là nguyên lý retry mà FoodAI dùng khi gọi Vision API. Kẹt thì hỏi, sẽ được dẫn từng tầng.)

## Bài 12: Async/await — một người phục vụ nhiều bàn

🎯 **Mục tiêu:** thấy TẬN MẮT vì sao async nhanh hơn khi phải chờ đợi.

📝 File `bai12.py`:

```python
import asyncio
import time

async def goi_api_gia(ten: str, giay: float) -> str:    # giả lập gọi API mất thời gian
    await asyncio.sleep(giay)          # await: "tôi chờ ở đây, ai cần cứ chạy trước"
    return f"{ten} xong sau {giay}s"

async def chay_tuan_tu():              # cách 1: chờ từng cái xong mới gọi cái sau
    a = await goi_api_gia("Vision", 1)
    b = await goi_api_gia("Database", 1)
    c = await goi_api_gia("Embedding", 1)
    return [a, b, c]

async def chay_dong_thoi():            # cách 2: phóng cả 3 đi cùng lúc, chờ chung
    return await asyncio.gather(
        goi_api_gia("Vision", 1),
        goi_api_gia("Database", 1),
        goi_api_gia("Embedding", 1),
    )

t = time.perf_counter()
asyncio.run(chay_tuan_tu())            # asyncio.run: mở "quán" (event loop) và chạy
print(f"Tuần tự:    {time.perf_counter() - t:.1f}s")    # ~3.0s

t = time.perf_counter()
asyncio.run(chay_dong_thoi())
print(f"Đồng thời:  {time.perf_counter() - t:.1f}s")    # ~1.0s 🎉
```

🔍 Cùng 3 việc, mỗi việc chờ 1 giây: tuần tự mất 3s, `gather` (gom chạy đồng thời) chỉ mất 1s — vì trong lúc "Vision" đang chờ, người phục vụ (event loop — vòng lặp sự kiện) chạy sang phục vụ "Database" và "Embedding". **Chỉ hiệu quả với việc CHỜ ĐỢI (I/O)** — chờ mạng, chờ database; còn tính toán nặng bằng CPU thì phải `asyncio.to_thread` (đã giải thích ở mục 10 tài liệu kia). Toàn bộ backend FoodAI viết `async def` là vì lý do trong 20 dòng code này.

💪 **Bài tập 12:** sửa `bai12.py`: cho 3 "API" thời gian chờ khác nhau (0.5s, 1s, 2s), dự đoán TRƯỚC tổng thời gian mỗi cách rồi chạy kiểm chứng. (Đáp án đúng nói lên bạn đã hiểu: tuần tự = tổng, đồng thời = cái lâu nhất.)

---

# ĐỒ ÁN TỐT NGHIỆP — "FoodAI mini" chạy trong Terminal

Tổng hợp TẤT CẢ những gì đã học thành một app hoàn chỉnh ~100 dòng. Tự viết theo yêu cầu sau, không nhìn code mẫu:

**Yêu cầu chức năng:**
1. Dữ liệu món ăn để trong dict `{tên món: calo_mỗi_gram}` với ít nhất 8 món Việt (bài 6).
2. Class `NhatKyAnUong` quản lý list các bữa đã ăn, có method `them_bua`, `tong_calo_hom_nay`, `mon_nhieu_calo_nhat` (bài 8, 9).
3. Menu vòng lặp: `1. Ghi bữa ăn  2. Xem thống kê  3. Thoát` — nhập sai thì báo lỗi lịch sự, không sập (bài 3, 4, 7).
4. Ghi bữa ăn: hỏi tên món + gram; tên món tra không phân biệt hoa thường (`.lower()`); món không có trong dict → hỏi người dùng nhập calo/gram thủ công (đúng tinh thần "candidate" của FoodAI thật!).
5. Mỗi lần thêm bữa → lưu toàn bộ nhật ký ra `nhat_ky.json`; mở app lại thì đọc và tiếp tục (bài 7).
6. Thống kê dùng comprehension: tổng kcal, trung bình mỗi bữa, top 3 món (bài 9).
7. Nâng cao tùy chọn: decorator `@do_thoi_gian` đo thời gian hàm thống kê (bài 11).

**Tiêu chí tự chấm:** chạy 3 phiên liên tiếp dữ liệu không mất; gõ bậy không sập; mỗi hàm < 20 dòng; có type hints. Làm xong đồ án này, quay lại đọc `backend/api/dishes.py` của project thật — bạn sẽ nhận ra nó chỉ là phiên bản "người lớn" của đúng bài toán bạn vừa giải.

---

# LỘ TRÌNH GỢI Ý

| Giai đoạn | Nội dung | Thời lượng gợi ý |
|---|---|---|
| Tuần 1 | Phần 0 + Phần 1 (bài 1–4) + bài tập | mỗi ngày 1 bài |
| Tuần 2 | Phần 2 (bài 5–8) + bài tập | mỗi ngày 1 bài |
| Tuần 3 | Phần 3 (bài 9–12) — chậm lại, mỗi bài 1–2 ngày | generator/decorator/async cần ngấm |
| Tuần 4 | Đồ án tốt nghiệp + đọc [PYTHON_QUA_FOODAI.md](PYTHON_QUA_FOODAI.md) đối chiếu vào code thật | 3–4 buổi |

Quy tắc vàng: **mỗi bài tập tự gõ 100%**. Kẹt quá 30 phút → hỏi Claude xin GỢI Ý (không xin đáp án). Sai và tự sửa được một lần đáng giá hơn đọc mười trang lý thuyết.
