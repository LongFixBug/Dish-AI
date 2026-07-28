# Học Python qua chính code FoodAI

> Nguyên tắc của tài liệu này: **không học Python "chay"** — mọi khái niệm đều được minh họa bằng
> code thật đang chạy trong project của bạn (có đường dẫn file kèm theo để mở ra đối chiếu).
> Học xong mỗi mục, mở đúng file đó ra và tự giải thích lại từng dòng.
> Thuật ngữ đều có giải thích trong ngoặc `( )`.

Cách dùng: học lần lượt 12 mục, mỗi ngày 1–2 mục. Cuối tài liệu có bộ câu hỏi phỏng vấn Python kinh điển và bài tập tự viết.

---

## Mục 1 — Biến, kiểu dữ liệu, và bài học "0 khác None"

Python có các kiểu cơ bản: `int` (số nguyên), `float` (số thực), `str` (chuỗi ký tự), `bool` (đúng/sai), `None` (không-có-gì).

```python
grams = 150.0        # float
name = "Phở bò"      # str
found_in_db = True   # bool
confidence = None    # None = "chưa biết" — KHÁC VỚI 0 = "biết, và nó bằng không"
```

**Truthiness** (tính "coi-như-đúng/sai"): trong câu `if x:`, Python coi `0`, `""` (chuỗi rỗng), `[]` (danh sách rỗng), `None` đều là "sai". Tiện, nhưng là mầm bug: project từng dính bug mobile *"sửa nguyên liệu về 0 g thì nguyên liệu biến mất"* vì code coi `0` như "không tồn tại" (xem bug C4 trong [SO_TAY_BUG_PHONG_VAN.md](SO_TAY_BUG_PHONG_VAN.md)). Muốn kiểm tra "có phải None không" thì viết tường minh `if x is None:` chứ đừng `if not x:`.

Ví dụ thật — guard chống LLM trả None trong luồng analyze:

```python
if not name or not name.strip():   # chặn cả None lẫn chuỗi toàn khoảng trắng
    ...
```

Ở đây `if not name` cố ý dùng truthiness để chặn **cả** `None` **và** `""` — dùng đúng chỗ thì truthiness là bạn, dùng sai chỗ (như bug 0 gram) là thù.

## Mục 2 — List, dict, tuple, set: bốn "hộp đựng"

| Kiểu | Ẩn dụ | Đặc điểm | Trong FoodAI |
|---|---|---|---|
| `list` | dãy ngăn kéo có đánh số | có thứ tự, thay đổi được | `candidate_names: list[str]` — danh sách tên món ứng viên |
| `dict` | tủ hồ sơ tra theo nhãn | tra theo key (khóa) cực nhanh | `vision["dish_name"]` — kết quả Vision trả về dạng dict |
| `tuple` | hộp niêm phong | có thứ tự, **không** thay đổi được | tọa độ, cặp giá trị trả về nhiều thứ cùng lúc |
| `set` | túi đựng không trùng | tự loại phần tử trùng, kiểm tra "có trong" nhanh | lọc tên ảnh trùng khi dedup album |

**Comprehension** (cú pháp "một dòng tạo hộp mới") — code thật trong [recognition_cascade.py](../backend/services/recognition_cascade.py):

```python
candidate_names=[
    candidate.dish_name for candidate in candidates[:candidates_limit]
]
```

Dịch: *"lấy `dish_name` của từng `candidate` trong `candidates` (chỉ lấy `candidates_limit` phần tử đầu — cú pháp `[:n]` gọi là slicing, cắt lát), gom thành list mới"*. Tương đương vòng `for` 4 dòng nhưng gọn 1 dòng. Chú ý: nó **tạo list mới** chứ không sửa list cũ — đúng tinh thần immutable (bất biến) của project.

Cũng file đó có **generator expression** (giống comprehension nhưng dùng ngoặc tròn — không tạo cả list trong bộ nhớ mà "nhả" từng phần tử):

```python
stripped = "".join(
    char for char in decomposed if not unicodedata.combining(char)
)
```

Dịch: *"duyệt từng ký tự của chuỗi đã tách dấu, bỏ ký tự nào là dấu thanh, nối phần còn lại thành chuỗi"* — đây chính là cách "Phở bò" biến thành "pho bo" để tìm kiếm không phân biệt dấu.

## Mục 3 — Mutable vs immutable: quy tắc quan trọng nhất của project

- **Immutable** (bất biến — tạo ra rồi không sửa được): `str`, `tuple`, `int`, `float`, frozen dataclass.
- **Mutable** (khả biến — sửa tại chỗ được): `list`, `dict`, `set`.

Vì sao project quy định "luôn tạo object mới, không sửa object cũ"? Vì object mutable được **truyền theo tham chiếu** (nhiều biến cùng trỏ vào một hộp): hàm A âm thầm sửa cái list mà hàm B cũng đang cầm → bug "ma" cực khó truy. Ẩn dụ: hồ sơ gốc chỉ có một bản mà ai mượn cũng gạch xóa thẳng vào đó — thay vào đó hãy photo ra bản mới rồi sửa trên bản photo.

**Bẫy phỏng vấn kinh điển — mutable default argument** (tham số mặc định khả biến):

```python
def add_item(item, bucket=[]):   # SAI! cái list [] này được tạo MỘT LẦN duy nhất
    bucket.append(item)          # mọi lần gọi hàm đều dồn chung vào một list
    return bucket

def add_item(item, bucket=None):  # ĐÚNG
    if bucket is None:
        bucket = []
    ...
```

Lý do: default được tạo **lúc định nghĩa hàm** (chạy 1 lần), không phải mỗi lần gọi. Câu này hỏi fresher Python gần như 100%.

## Mục 4 — Hàm: type hints, tham số, lambda

**Type hints** (chú thích kiểu — Python không bắt buộc nhưng project dùng triệt để): nhìn chữ ký thật của `decide_cascade`:

```python
def decide_cascade(
    candidates: list[DishCandidateScore],   # nhận list các DishCandidateScore
    threshold: float,
    margin: float,
    candidates_limit: int,
) -> CascadeDecision:                       # -> nghĩa là "trả về" CascadeDecision
```

Cú pháp đáng nhớ: `str | None` nghĩa là "hoặc chuỗi, hoặc None" (dấu `|` đọc là "hoặc" — cú pháp Python 3.10+). Trong `CascadeDecision` có `dish_name: str | None` — vì khi không có ứng viên nào thì không có tên món.

Type hints không làm code chạy khác đi, nhưng là **tài liệu sống** + để công cụ bắt lỗi trước khi chạy. Khi phỏng vấn hỏi "Python là ngôn ngữ kiểu gì?" → trả lời: **dynamic typing** (kiểu động — biến không cần khai báo kiểu) nhưng **strong typing** (kiểu chặt — không tự cộng chuỗi với số như JavaScript), và type hints là lớp kiểm tra tĩnh tự nguyện đắp thêm.

`lambda` (hàm nặc danh một dòng): `sorted(dishes, key=lambda d: d.score)` — "sắp xếp theo score". Dùng cho hàm bé xíu truyền vào hàm khác; logic dài hơn một biểu thức thì viết `def` tử tế.

## Mục 5 — Ba loại "class" trong project: phải phân biệt được

Đây là câu hỏi phỏng vấn "đo độ hiểu project" cực tốt: FoodAI có **3 họ class khác nhau cho 3 việc khác nhau**.

**(a) Pydantic BaseModel** — [schemas/nutrition.py](../schemas/nutrition.py) — "hải quan cửa khẩu":

```python
class NutritionPerGram(BaseModel):
    name: str = Field(description="Tên món/nguyên liệu")
    calories_per_g: float = Field(ge=0, description="Calo trên 1 gram (kcal/g)")
```

Pydantic (thư viện validate dữ liệu) tự kiểm tra: `calories_per_g` phải là số và `ge=0` (greater-or-equal — không âm). Dữ liệu từ ngoài vào (request, output LLM) đi qua đây bị "khám" — sai kiểu là chặn ngay tại biên với thông báo rõ ràng. Còn dùng `Literal["per_gram_scaled", "source_serving", "vision_estimate"]` — nghĩa là field chỉ được nhận đúng 1 trong 3 giá trị liệt kê.

**(b) Dataclass** — [recognition_cascade.py](../backend/services/recognition_cascade.py) — "hộp đựng dữ liệu nội bộ":

```python
@dataclass(frozen=True)
class CascadeDecision:
    resolved: bool
    dish_name: str | None
    score: float
```

`@dataclass` tự sinh `__init__` (hàm khởi tạo) khỏi viết tay; `frozen=True` làm object **bất biến** — tạo xong ai cố sửa là nổ lỗi ngay. Nhẹ hơn Pydantic (không validate) — đủ dùng cho dữ liệu nội bộ đã tin cậy.

**(c) SQLAlchemy model** — `backend/db/models.py` — "bản vẽ bảng database": mỗi class ánh xạ một bảng PostgreSQL (ORM — Object-Relational Mapping, kỹ thuật thao tác database bằng object thay vì viết SQL tay).

Vì sao không dùng chung một class? Vì **hình dạng dữ liệu ở biên API khác hình dạng lưu trữ** — schema API đổi theo nhu cầu client, bảng DB đổi theo migration; dính chùm là sửa một đầu gãy đầu kia (đây là đáp án câu 19 trong bộ Q&A).

## Mục 6 — `@decorator`: hàm "đội mũ"

Decorator (trang trí hàm) = hàm nhận một hàm và trả về hàm đã được "độ" thêm khả năng. Cú pháp `@ten_decorator` đặt ngay trên `def`. Ẩn dụ: bọc thêm lớp vỏ cho món quà — món quà bên trong y nguyên, nhưng giờ có thêm giấy gói + nơ.

Code thật — [analyze.py](../backend/api/analyze.py):

```python
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_image(
    session: AsyncSession = Depends(get_session),
    ...
)
```

- `@router.post("/analyze", ...)`: FastAPI "độ" hàm này thành endpoint HTTP — ai gọi `POST /analyze` thì hàm chạy, kết quả được ép khuôn `AnalyzeResponse`.
- `@property` ([config.py](../backend/config.py) — `is_production`): biến method thành thuộc-tính-đọc — gọi `settings.is_production` không cần ngoặc `()`, phía sau vẫn là logic tính toán.
- `@dataclass(frozen=True)`: như mục 5.

Bạn không cần tự viết decorator ở trình fresher — nhưng phải **giải thích được decorator làm gì** khi chỉ vào `@router.post`.

## Mục 7 — Exception: lỗi là dữ liệu, không phải tận thế

```python
try:
    dish = await contribute_dish(session, payload)   # thử làm
except IntegrityError:                               # nếu DB báo trùng tên
    raise HTTPException(status_code=409, detail="Tên món đã tồn tại")
```

- `try/except`: "thử làm, hỏng thì rẽ sang nhánh xử lý" — không để sập cả chương trình.
- `raise`: chủ động ném lỗi lên cho tầng trên xử lý.
- Nguyên tắc project (rút từ bug A3): **bắt lỗi cụ thể** (`except IntegrityError`) chứ không `except Exception` nuốt chửng mọi thứ (nuốt lỗi = giấu bệnh); và **dịch lỗi kỹ thuật thành mã HTTP đúng nghĩa** (trùng tên → 409, đầu vào sai → 400, còn 500 nghĩa là "lỗi của bọn em, xin lỗi").
- Bug B3 (ảnh hỏng sập buổi train) cũng là bài exception: `try/except` quanh chỗ đọc ảnh, log rồi bỏ qua — pipeline phải sống sót qua dữ liệu rác.

## Mục 8 — `yield` và generator: hàm "nhả từng viên kẹo"

Hàm thường `return` một lần rồi chết. Hàm chứa `yield` thành **generator** — nhả một giá trị, **đứng chờ tại chỗ**, ai cần tiếp thì nhả tiếp. Ẩn dụ: máy bán kẹo — bỏ xu ra một viên, máy vẫn đứng đó nhớ mình đang bán dở.

Ba chỗ dùng thật trong project, ba mục đích khác nhau:

**(a) Cấp phát tài nguyên** — [postgres.py](../backend/db/postgres.py):

```python
async def get_session():
    async with async_session() as session:
        yield session          # đưa session cho endpoint dùng
    # endpoint xong việc → chạy tiếp qua đây → with tự đóng session
```

Dòng code **sau** `yield` chỉ chạy khi người dùng generator xong việc → thành cơ chế "phát ra, dùng xong tự dọn".

**(b) Vòng đời app** — `backend/main.py` (hàm lifespan): trước `yield` là việc lúc **khởi động** (nạp CV model, tạo Qdrant collection), sau `yield` là việc lúc **tắt máy**. Cả app "sống" trong khoảng giữa.

**(c) Streaming** — `backend/api/chat.py`:

```python
yield f"data: {word}\n\n"     # đẩy từng chữ về client ngay khi có
```

Trả lời chat kiểu "chữ hiện dần" (SSE — Server-Sent Events, server đẩy dữ liệu nhỏ giọt về trình duyệt) — không đợi cả câu xong mới gửi.

## Mục 9 — `with` / context manager: "mượn đồ tự động trả"

```python
async with async_session() as session:
    ...  # dùng session ở đây
# hết block → session TỰ đóng, kể cả khi trong block nổ lỗi
```

Context manager (trình quản lý ngữ cảnh) đảm bảo "mở thì phải đóng": file, kết nối database, lock... Ẩn dụ: thư viện tự động thu hồi sách khi bạn bước ra cửa — kể cả khi bạn... ngất giữa phòng đọc (exception). Không dùng `with` mà quên `close()` → rò rỉ kết nối, app chạy lâu tự chết — lỗi production kinh điển.

## Mục 10 — async/await: một người phục vụ chạy nhiều bàn

Khái niệm quan trọng nhất của backend này. Ẩn dụ chuẩn để kể khi phỏng vấn:

> Quán ăn có MỘT người phục vụ (event loop — vòng lặp sự kiện). Bàn A gọi món xong phải **chờ bếp nấu** (chờ database/API trả lời — I/O wait). Người phục vụ **không đứng ôm bàn A chờ** mà chạy sang nhận order bàn B, C. Bếp reo chuông (I/O xong) thì quay lại bàn A bưng món.

- `async def` — khai báo hàm "biết nhường chỗ".
- `await` — điểm "tôi phải chờ ở đây, ai cần thì cứ chạy trước" (chờ database, chờ Vision API, chờ embedding server).
- Nhờ vậy **một** process Python phục vụ được hàng trăm request đồng thời — miễn là phần lớn thời gian của request là **chờ I/O** (đúng bài toán của FoodAI: chờ DB, chờ cloud).

**`asyncio.to_thread` — bê việc nặng ra bàn phụ.** Code thật, `backend/api/analyze.py`:

```python
cv_result = await asyncio.to_thread(cv_model.predict, temp_path)
```

`cv_model.predict` là tính toán thuần CPU (chạy mạng nơ-ron) — nó **không chờ ai cả nên không biết nhường**; để nó chạy thẳng trong event loop là người phục vụ bị "trói" đứng im, cả quán tê liệt. `to_thread` đẩy nó sang thread (luồng) riêng, event loop tiếp tục phục vụ bàn khác, xong thì `await` nhận kết quả. Quy tắc rút gọn: **chờ I/O → await trực tiếp; tính toán nặng → to_thread**. (Đây là đáp án câu 17 bộ Q&A: to_thread giải quyết "đừng chặn event loop", KHÔNG giải quyết scale inference — muốn scale thật phải tách service inference riêng.)

**GIL** (Global Interpreter Lock — khóa toàn cục của Python: mỗi thời điểm chỉ MỘT thread chạy bytecode Python): hay bị hỏi kèm. Trả lời gọn: *"GIL làm multi-thread Python không tăng tốc code thuần Python, nhưng không sao với FoodAI vì (1) I/O bound dùng async, (2) PyTorch/NumPy nhả GIL khi tính toán trong C, nên to_thread vẫn hiệu quả."*

## Mục 11 — Import, module, và mấy cú pháp hiện đại hay gặp trong repo

- **Module** = một file `.py`; **package** = thư mục có `__init__.py`. `from backend.services.dishes import lookup_dish` = "vào thư mục backend/services, mở file dishes.py, lấy hàm lookup_dish".
- **Walrus operator `:=`** (toán tử "con hải mã" — gán và dùng luôn trong một biểu thức) — code thật `backend/api/upload_utils.py`:

```python
while chunk := await file.read(UPLOAD_CHUNK_BYTES):
```

Dịch: *"đọc một khúc file, gán vào `chunk`, còn dữ liệu thì lặp tiếp; hết (chuỗi rỗng = falsy) thì dừng"* — đọc file to theo từng khúc để không nuốt cả file ảnh vào RAM một lúc.

- **f-string** (chuỗi định dạng): `f"data: {word}\n\n"` — nhét biến thẳng vào chuỗi. Format số: `f"{score:.4f}"` = lấy 4 chữ số thập phân.
- **`pathlib.Path`**: thao tác đường dẫn kiểu object — `temp_path.write_bytes(...)` thay cho open/write/close thủ công.
- **Chuẩn hóa Unicode** — `unicodedata.normalize("NFKD", ...)` trong `_accent_key`: tách "ở" thành "o" + dấu, rồi lọc bỏ dấu — trái tim của tìm kiếm tiếng Việt không dấu. Kể được ví dụ này là ghi điểm "hiểu bài toán bản địa".

## Mục 12 — Bộ câu hỏi Python phỏng vấn kinh điển (tự trả lời trước khi xem gợi ý)

1. **`==` khác `is`?** — `==` so **giá trị**, `is` so **danh tính** (có phải cùng một object trong bộ nhớ không). Chỉ dùng `is` với `None` (`if x is None`).
2. **list khác tuple?** — list mutable, tuple immutable; tuple làm được key của dict, list thì không (vì mutable không băm được).
3. **Bẫy mutable default argument?** — mục 3. Kể luôn cách sửa `=None`.
4. **Shallow copy khác deep copy?** — copy nông chỉ photo cái hộp ngoài, các hộp con bên trong vẫn dùng chung; `copy.deepcopy` photo toàn bộ đến tận đáy.
5. **GIL là gì, sao FoodAI vẫn nhanh?** — mục 10.
6. **`yield` khác `return`?** — mục 8, kể luôn 3 chỗ dùng thật trong project (điểm cộng lớn).
7. **Decorator là gì?** — mục 6, chỉ vào `@router.post`.
8. **Duck typing?** — "đi như vịt, kêu như vịt thì đối xử như vịt": Python không hỏi object thuộc class gì, chỉ hỏi nó **làm được gì** (có method đó không).
9. **`*args` / `**kwargs`?** — gom tham số thừa: `*args` gom thành tuple theo vị trí, `**kwargs` gom thành dict theo tên.
10. **Vì sao cần virtual environment / uv?** — mỗi project một "phòng riêng" chứa thư viện đúng phiên bản, không giẫm chân nhau; `uv` là công cụ quản lý nhanh, khóa phiên bản trong `uv.lock` để máy nào cài cũng ra y hệt (reproducible — tái lập được).

## Lộ trình 12 ngày (mỗi ngày ~1 giờ, tách riêng với lịch ôn phỏng vấn)

| Ngày | Học | Thực hành trên chính repo |
|---|---|---|
| 1 | Mục 1–2 | Mở Python REPL (`uv run python`), tự tạo list/dict/set, thử truthiness của `0`, `""`, `None` |
| 2 | Mục 3 | Tự tái hiện bug mutable default trong REPL rồi sửa nó |
| 3 | Mục 4 | Đọc chữ ký mọi hàm trong `recognition_cascade.py`, dịch từng type hint thành tiếng Việt |
| 4–5 | Mục 5 | Mở `schemas/nutrition.py` + `backend/db/models.py`, tự trả lời "class này thuộc họ nào, vì sao" |
| 6 | Mục 6 | Đếm mọi decorator trong `backend/api/analyze.py`, giải thích từng cái |
| 7 | Mục 7 | Đọc các `try/except` trong `backend/api/dishes.py`, xem mỗi except dịch ra mã HTTP nào |
| 8 | Mục 8–9 | Đọc `postgres.py` + `main.py` lifespan, kể lại "đời một session" từ mở đến đóng |
| 9–10 | Mục 10 | Tìm mọi `asyncio.to_thread` trong repo (`grep -rn "to_thread" backend/`), giải thích vì sao từng chỗ cần nó |
| 11 | Mục 11 | Đọc `upload_utils.py`, giải thích walrus + vì sao đọc file theo khúc |
| 12 | Mục 12 | Tự trả lời 10 câu không nhìn gợi ý, ghi âm nghe lại |

**Bài tập viết code (tự viết, không nhờ AI — đây là phần bạn PHẢI tự tay làm):**

1. Viết hàm `strip_accents(text: str) -> str` bỏ dấu tiếng Việt bằng `unicodedata` (không nhìn `_accent_key`), rồi so với bản trong repo.
2. Viết generator `read_chunks(path, size)` nhả từng khúc bytes của file (mô phỏng upload_utils).
3. Viết `@dataclass(frozen=True)` tên `MealItem` (name, grams, calories) + hàm `total_calories(items: list[MealItem]) -> float` dùng comprehension.
4. Viết decorator `@timed` in thời gian chạy của hàm bất kỳ (dùng `time.perf_counter`) — hiểu decorator bằng cách tự làm một cái.
5. Viết lại `decide_cascade` từ trí nhớ (chỉ nhìn mô tả ở [CASCADE_NHAN_DIEN_ANH.md](CASCADE_NHAN_DIEN_ANH.md)), rồi diff với bản thật.

> Khi kẹt ở bài nào, quay lại hỏi — tôi sẽ gợi ý theo kiểu dẫn dắt từng bước chứ không đưa đáp án ngay, để bạn tự vỡ ra (đúng cách bạn đang học project này).
