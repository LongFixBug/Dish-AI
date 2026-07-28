# Sổ tay bug thật của FoodAI — kể chuyện khi phỏng vấn

> Đây là danh sách **bug có thật** đã gặp và sửa trong project (lấy từ lịch sử git và ghi chép các phiên làm việc).
> Khi nhà tuyển dụng hỏi *"Em từng gặp bug gì? Xử lý thế nào?"* — chọn 2–3 bug ở đây kể theo công thức:
> **Triệu chứng → Nguyên nhân gốc → Cách sửa → Bài học**.
> Mỗi bug có sẵn đoạn "🎤 Trả lời 30 giây" để luyện nói.

Cách chọn bug để kể:
- Phỏng vấn **AI Engineer** → kể nhóm B (ML) trước.
- Phỏng vấn **Backend** → kể nhóm A trước.
- Câu "bug nhớ đời nhất" → chọn A1 (None.strip) hoặc B1 (promote sai split) — cả hai đều có bài học sâu.

---

## Nhóm A — Bug backend / logic nghiệp vụ

### A1. LLM trả về `None` làm crash cả endpoint

- **Triệu chứng:** Thi thoảng gọi `/analyze` bị lỗi 500 (mã lỗi máy chủ sập) dù ảnh bình thường.
- **Nguyên nhân gốc:** Vision API (dịch vụ AI nhìn ảnh trên cloud) đôi lúc trả `dish_name: None` thay vì tên món. Code gọi thẳng `name.strip()` (hàm cắt khoảng trắng) trên giá trị `None` → Python nổ lỗi `AttributeError`.
- **Cách sửa:** Thêm guard (chốt chặn kiểm tra đầu vào) `if not name or not name.strip()` trước khi dùng, và trả thông báo rõ ràng cho người dùng thay vì hiện "Món 'None'".
- **Bài học:** **Không bao giờ tin output của LLM** (mô hình ngôn ngữ lớn). Nó là dữ liệu bên ngoài, phải validate (kiểm tra hợp lệ) như validate input của người dùng.
- 🎤 *"Em từng bị crash 500 vì Vision API trả None thay vì tên món. Root cause là em tin tưởng output của LLM như dữ liệu nội bộ. Em sửa bằng guard validate đầu vào và viết test cho case đó. Bài học lớn nhất: output LLM là untrusted data, phải qua cùng một cửa kiểm tra như input người dùng."*

### A2. Mặc định confidence 1.0 và hiển thị món 0 kcal

- **Commit:** `61a936d`
- **Triệu chứng:** Kết quả phân tích hiện món "0 kcal" (vô lý) và độ tự tin luôn 100% kể cả khi hệ thống không chắc.
- **Nguyên nhân gốc:** Khi thiếu dữ liệu, code lấy giá trị mặc định `confidence=1.0` — tức mặc định là "chắc chắn nhất" đúng lúc đang "mù mờ nhất". Món không có dữ liệu dinh dưỡng thì vẫn được render ra 0 kcal.
- **Cách sửa:** Bỏ item 0 kcal khỏi kết quả, không bao giờ mặc định confidence 1.0 — thiếu thì để trống/thấp và nói thật với người dùng.
- **Bài học:** Giá trị mặc định (default) phải là giá trị **an toàn nhất**, không phải giá trị "đẹp nhất". Default sai còn nguy hiểm hơn lỗi hiện rõ, vì nó âm thầm đánh lừa người dùng.

### A3. Recipe rỗng vẫn được lưu; đổi tên trùng gây lỗi 500

- **Triệu chứng:** (1) Người dùng góp công thức món mà toàn bộ nguyên liệu đều không hợp lệ → hệ thống vẫn lưu một món "rỗng ruột". (2) Đổi tên món trùng với món khác → sập 500 thay vì báo lỗi lịch sự.
- **Nguyên nhân gốc:** (1) Thiếu validate trước khi INSERT (lệnh ghi vào database). (2) Ràng buộc UNIQUE (quy tắc "tên món không được trùng") của database nổ ra `IntegrityError` mà code không bắt.
- **Cách sửa:** Validate danh sách nguyên liệu trước khi lưu → trả 400 (lỗi do người dùng); bắt `IntegrityError` → trả 409 (mã "xung đột dữ liệu"), kiểm tra trùng bằng `vn_norm` (tên đã chuẩn hóa bỏ dấu tiếng Việt) và loại trừ chính món đang sửa.
- **Bài học:** Database constraint là **lưới an toàn cuối cùng**, không phải cơ chế báo lỗi cho người dùng. App phải kiểm tra trước và dịch lỗi kỹ thuật thành mã HTTP đúng nghĩa (400/409, không phải 500).

### A4. `LIMIT 1` mà không `ORDER BY` — kết quả "hên xui"

- **Triệu chứng:** Tra cùng một tên món, lúc ra kết quả này lúc ra kết quả khác.
- **Nguyên nhân gốc:** Câu truy vấn lấy 1 dòng (`LIMIT 1`) nhưng không sắp xếp (`ORDER BY`) — database được quyền trả dòng **bất kỳ** trong số các dòng khớp, thứ tự không đảm bảo.
- **Cách sửa:** Thêm `ORDER BY char_length(tên) ASC` — ưu tiên tên khớp ngắn nhất (khớp "sát" nhất).
- **Bài học:** `LIMIT` không có `ORDER BY` là bug tiềm ẩn kinh điển của SQL — kết quả không xác định (non-deterministic) rất khó tái hiện khi debug.

### A5. Rate limit bị vượt mặt (bypass)

- **Commit:** `899cbc6`
- **Triệu chứng:** Rate limit (giới hạn số lần gọi API trong 1 phút, chống spam/lạm dụng) có thể bị lách qua; các endpoint tra cứu công khai bị gọi tự do.
- **Cách sửa:** Chặn đường bypass ở middleware (lớp chặn mọi request trước khi vào xử lý chính), siết lại các endpoint công khai, thêm test cho hành vi giới hạn.
- **Bài học:** Kiểm soát an ninh phải đặt ở **một cửa duy nhất, sớm nhất** (middleware) — rải rác từng endpoint sẽ luôn bỏ sót.

### A6. Healthcheck dùng nhầm `/ready` gây vòng lặp restart

- **Commit:** `5978e2b`
- **Triệu chứng:** Khi database chưa lên kịp, container (hộp Docker chạy app) bị hệ thống giết và khởi động lại liên tục.
- **Nguyên nhân gốc:** Nhầm lẫn 2 khái niệm: `/live` (liveness — "app còn thở không?") và `/ready` (readiness — "app đã sẵn sàng phục vụ chưa, tức đã nối được DB chưa?"). Healthcheck của Docker dùng `/ready` → DB chậm một chút là app bị coi như "chết" và bị giết oan.
- **Cách sửa:** Healthcheck dùng `/live`; `/ready` chỉ để cân bằng tải quyết định có dồn traffic vào không. Đồng thời thêm cache cho readiness (không dồn dập query DB mỗi lần check) và sửa circuit breaker có trạng thái **half-open** (xem A7).
- **Bài học:** "Còn sống" và "sẵn sàng" là hai câu hỏi khác nhau — trộn chung là tự tay gây sự cố dây chuyền.

### A7. Circuit breaker thiếu trạng thái half-open

- **Commit:** `5978e2b`
- **Khái niệm:** Circuit breaker (cầu dao điện phần mềm) — khi một dịch vụ ngoài (vd Vision API) lỗi liên tục, "cầu dao nhảy" và tạm ngừng gọi để không phí thời gian chờ lỗi.
- **Triệu chứng:** Cầu dao đã "nhảy" thì không bao giờ tự đóng lại — dịch vụ ngoài đã hồi phục mà hệ thống vẫn từ chối gọi.
- **Cách sửa:** Thêm trạng thái **half-open** (hé mở): sau một khoảng nghỉ, cho **một** request thử đi qua; thành công thì đóng cầu dao lại bình thường, thất bại thì mở tiếp.
- **Bài học:** Pattern chịu lỗi phải có đường **hồi phục tự động**, không chỉ đường "ngắt".

### A8. Migration thêm CHECK constraint thất bại vì dữ liệu bẩn

- **Commit:** `6b3f854`
- **Triệu chứng:** Chạy migration (script nâng cấp cấu trúc database) thêm CHECK constraint (quy tắc ràng buộc giá trị, vd "calo không được âm") thì thất bại.
- **Nguyên nhân gốc:** Trong bảng đã tồn tại các dòng dữ liệu cũ vi phạm quy tắc mới → database từ chối áp quy tắc.
- **Cách sửa:** Migration phải **dọn dữ liệu vi phạm trước**, rồi mới tạo constraint. Đồng thời đồng bộ index vào file models (để code và database mô tả cùng một sự thật).
- **Bài học:** Thêm ràng buộc mới vào database đang có dữ liệu = 2 bước: làm sạch quá khứ, rồi mới khóa tương lai.

---

## Nhóm B — Bug ML / AI

### B1. Chọn model để "lên sóng" dựa trên validation — sai split

- **Commit:** `2823763`
- **Khái niệm:** Dữ liệu chia 3 phần: train (để học), validation (để chỉnh trong lúc học), test (niêm phong, chỉ mở ra chấm điểm cuối cùng).
- **Triệu chứng:** Model được promote (thăng hạng lên phục vụ thật) dựa trên điểm validation.
- **Nguyên nhân gốc:** Điểm validation bị "lạc quan ảo" — vì chính mình đã dùng nó để chọn hyperparameter (các nút vặn khi train) và chọn checkpoint (bản lưu model), nên model đã "học mẹo" theo validation. Giống ôn đúng bộ đề rồi thi bộ đề đó.
- **Cách sửa:** Quyết định promote dựa trên **test split** chưa từng đụng tới.
- **Bài học:** Đây là dạng **data leakage** (rò rỉ dữ liệu) tinh vi — không lộ dữ liệu vào model mà lộ vào **quy trình ra quyết định**. Câu này kể trong phỏng vấn AI rất ăn điểm.
- 🎤 *"Em từng promote model theo val accuracy — sai, vì val đã bị dùng để chọn checkpoint nên điểm bị lạc quan. Em sửa pipeline để promote chỉ dựa trên test split niêm phong. Đó là bài học về leakage ở tầng quy trình chứ không chỉ tầng dữ liệu."*

### B2. Resize ép ảnh thành hình vuông làm méo món ăn

- **Triệu chứng:** Độ chính xác thấp hơn kỳ vọng dù data sạch.
- **Nguyên nhân gốc:** Bước tiền xử lý dùng `Resize((size, size))` — ép ảnh chữ nhật thành vuông làm **méo hình** (tô phở thành hình elip dẹt). Chuẩn ImageNet là `Resize(size)` (giữ tỉ lệ) + `CenterCrop(size)` (cắt giữa).
- **Cách sửa:** Đổi sang Resize + CenterCrop cho validation/test, và transform lúc inference (dự đoán thật) phải **khớp y hệt** transform lúc validation.
- **Bài học:** Train/serve skew (lệch giữa cách xử lý lúc train và lúc chạy thật) là bug ML thầm lặng phổ biến nhất — model không sai, đầu vào bị "chế biến" khác nhau.

### B3. Một ảnh hỏng làm sập cả buổi train

- **Triệu chứng:** DataLoader (bộ nạp dữ liệu theo lô cho việc train) crash giữa chừng vì một file ảnh lỗi không mở được.
- **Cách sửa:** `try/except` trong hàm đọc ảnh → ghi log và bỏ qua sang ảnh kế; kèm script quét trước bằng PIL verify (thư viện ảnh Python kiểm tra file mở được không).
- **Bài học:** Dữ liệu thật luôn có rác. Pipeline phải **sống sót qua rác** chứ không giả định dữ liệu hoàn hảo.

### B4. Model không có checkpoint vẫn chạy — và dự đoán rác

- **Triệu chứng:** CV model (model thị giác máy tính chạy tại chỗ) vẫn khởi động bình thường nhưng dự đoán chính xác ~7.7% (ngang mức đoán bừa).
- **Nguyên nhân gốc:** File checkpoint (não đã train) không tồn tại → model chạy với **random weights** (trọng số ngẫu nhiên, tức chưa học gì) mà không hề báo lỗi. Nguy hiểm vì hệ thống trông "vẫn chạy tốt".
- **Cách sửa:** Kiểm tra sau khi load: `strict=False` phải kèm hàm báo cáo missing/unexpected keys (các mảnh não bị thiếu/thừa) để biết backbone có load đủ không; hệ thống fallback (dự phòng) sang Vision khi CV không đáng tin.
- **Bài học:** **Fail loudly** (hỏng thì hỏng cho to) — một hệ AI chết lặng lẽ mà vẫn trả kết quả là loại bug tệ nhất.

### B5. Class imbalance — lớp có 1 ảnh

- **Triệu chứng:** Có món chỉ có 1 ảnh train trong khi món khác có 50 → model bỏ bê món hiếm.
- **Cách sửa:** Weighted CrossEntropyLoss (hàm mất mát có trọng số — món hiếm được "nhân điểm" để model chú ý hơn), log độ chính xác từng lớp mỗi epoch (vòng train) và theo dõi `val_worst_class_acc` (điểm của lớp tệ nhất).
- **Bài học:** Accuracy trung bình che giấu lớp yếu — phải nhìn **per-class** (từng lớp một).

### B6. Tiền xử lý chậm hàng trăm ms vì tự viết flood fill

- **Triệu chứng:** Bước tách nền ảnh chậm bất thường.
- **Nguyên nhân gốc:** Tự viết flood fill (thuật toán loang màu tìm vùng liền nhau) bằng Python thuần — chậm hàng trăm ms mỗi ảnh.
- **Cách sửa:** Thay bằng `scipy.ndimage.label` (thư viện tính toán khoa học viết bằng C) → còn ~11ms cho ảnh 1 megapixel.
- **Bài học:** Với xử lý số liệu/ảnh, **đừng tự viết** cái thư viện chuẩn đã tối ưu — chậm gấp chục lần và dễ sai.

---

## Nhóm C — Bug vận hành, cấu hình, giao diện

### C1. Server kẹt vòng restart vô hạn vì một request treo

- **Triệu chứng:** `uvicorn --reload` (chế độ tự khởi động lại khi sửa code) kẹt cứng, không tắt cũng không lên lại được.
- **Nguyên nhân gốc:** Một request đang chờ Vision API (cloud chậm/treo) không chịu kết thúc → graceful shutdown (quy trình "tắt máy lịch sự": chờ mọi request xong rồi mới tắt) chờ vô hạn.
- **Cách sửa:** Thêm `--timeout-graceful-shutdown 5` — chờ lịch sự tối đa 5 giây rồi cưỡng chế tắt. Đã ghi thẳng vào `scripts/dev_up.sh` kèm comment giải thích.
- **Bài học:** Mọi thao tác chờ đợi bên ngoài đều phải có **timeout** (hạn chờ) — kể cả thao tác... tắt máy.

### C2. Biến môi trường trong shell "đè" file `.env`

- **Triệu chứng:** Đã sửa `.env` thành model mới mà hệ thống vẫn gọi model cũ.
- **Nguyên nhân gốc:** Biến `VISION_MODEL` từng được `export` trong shell (phiên dòng lệnh) — biến shell có **độ ưu tiên cao hơn** file `.env`, nên `.env` sửa mấy cũng vô ích.
- **Cách sửa:** `unset VISION_MODEL` trước khi chạy, và gỡ export khỏi file cấu hình shell.
- **Bài học:** Phải thuộc **thứ tự ưu tiên cấu hình** (shell env > `.env` > default trong code). Bug cấu hình khó chịu vì code hoàn toàn đúng.

### C3. Test không "kín" — gọi nhầm service thật đang chạy

- **Triệu chứng:** Bộ test cho kết quả khác nhau tùy... máy có đang bật server embedding ảnh hay không.
- **Nguyên nhân gốc:** Test tưởng là cô lập nhưng thật ra gọi HTTP sang sidecar (dịch vụ phụ chạy cạnh) SigLIP đang chạy thật ở cổng 8082.
- **Cách sửa:** `conftest.py` (file cấu hình chung của pytest) thêm fixture autouse (tự áp cho mọi test) tắt cờ `image_embed_enabled` — test mặc định chạy trong "phòng cách ly".
- **Bài học:** Test phải **hermetic** (kín, không phụ thuộc môi trường ngoài) — "chạy được trên máy em" chưa đủ, phải chạy được trên mọi máy và CI.

### C4. Sửa nguyên liệu về 0 gram thì nguyên liệu... biến mất (mobile)

- **Commit:** `2145a5c`
- **Triệu chứng:** Trên app mobile, người dùng chỉnh khẩu phần một thành phần về 0 g → thành phần bị xóa khỏi danh sách; món thiếu dữ liệu hiện "0 kcal" thay vì "chưa có dữ liệu".
- **Nguyên nhân gốc:** Code coi `0` như "không tồn tại" — nhầm lẫn kinh điển giữa **0 và null** (0 là giá trị hợp lệ người dùng cố tình nhập; null là "không biết").
- **Cách sửa:** Giữ thành phần khi giá trị = 0; phân biệt "0 kcal" với "thiếu dữ liệu" trên UI; thêm widget test (test giao diện tự động của Flutter).
- **Bài học:** `0`, `""` (chuỗi rỗng), `null` là **ba thứ khác nhau** — dùng truthiness (tính "coi như false") để check tồn tại là mầm bug.

### C5. Giao diện hiện nguyên liệu lặp 3 chỗ

- **Triệu chứng:** Tab Analyze của Streamlit (khung dựng giao diện web nhanh bằng Python) render danh sách nguyên liệu ở 3 vị trí → người dùng tưởng dữ liệu bị nhân bản.
- **Nguyên nhân gốc:** Bug UI thật — cùng một dữ liệu được vẽ ở nhiều khối giao diện chồng nhau.
- **Bài học:** Bug hiển thị cũng làm mất lòng tin y như bug dữ liệu — người dùng không phân biệt được "hiện sai" và "tính sai".

### C6. Upload ảnh mới nhưng kết quả cũ vẫn hiện

- **Triệu chứng:** Chọn ảnh khác nhưng màn hình vẫn hiện kết quả phân tích của ảnh trước.
- **Nguyên nhân gốc:** State (trạng thái lưu tạm của giao diện) không được reset khi ảnh đổi.
- **Cách sửa:** So sánh bytes (nội dung nhị phân) ảnh mới với ảnh cũ — khác thì xóa kết quả cũ.
- **Bài học:** Mọi state phải có câu trả lời cho câu hỏi *"khi nào mày hết hạn?"*.

---

## "Bug" hóa ra không phải bug (để không nhận oan khi bị hỏi xoáy)

- **`/analyze` báo nguyên liệu "missing" (thiếu):** thường do database **thật sự chưa có** nguyên liệu tên đó — hành vi đúng thiết kế (by design), đường xử lý là bổ sung catalog qua cơ chế candidate chờ duyệt, không phải sửa thuật toán matching.
- **Gõ "suon" không tìm ra "sườn":** hạn chế đã biết của ILIKE (tìm gần đúng của PostgreSQL, có phân biệt dấu) — đã có 2 lời giải: cột `vn_norm` chuẩn hóa bỏ dấu + tìm kiếm ngữ nghĩa qua Qdrant.
- **"Project dùng ResNet50 đúng không?"** — câu gài: CV model đã **đổi từ ResNet50 sang EfficientNet-B0** (commit `7b2c904`) vì nhẹ và chính xác hơn cho bài toán này.

---

## Công thức kể chuyện bug trong phỏng vấn

1. **Triệu chứng** — 1 câu, nói bằng góc nhìn người dùng ("thi thoảng 500", "kết quả hên xui").
2. **Cách truy vết** — đọc log ở đâu, tái hiện thế nào (điểm cộng lớn: nói được cách *tìm ra* chứ không chỉ cách *sửa*).
3. **Nguyên nhân gốc** — 1–2 câu, gọi đúng tên khái niệm (leakage, train/serve skew, non-deterministic query...).
4. **Cách sửa + test chống tái diễn** — luôn kết bằng "và em viết test cho case đó".
5. **Bài học khái quát** — nâng từ bug cụ thể lên nguyên tắc (đây là câu khiến bạn khác biệt).

> Tài liệu liên quan: [FOODAI_INTERVIEW_QA_VI.md](FOODAI_INTERVIEW_QA_VI.md) (bộ 116 câu hỏi), [FOODAI_CODE_WALKTHROUGH_VI.md](FOODAI_CODE_WALKTHROUGH_VI.md) (giải thích code), [CASCADE_NHAN_DIEN_ANH.md](CASCADE_NHAN_DIEN_ANH.md) (kiến trúc nhận diện mới nhất), [KE_HOACH_ON_PHONG_VAN.md](KE_HOACH_ON_PHONG_VAN.md) (lộ trình ôn).
