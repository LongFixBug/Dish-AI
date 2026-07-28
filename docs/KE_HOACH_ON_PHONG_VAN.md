# Kế hoạch 7 ngày: hiểu hết FoodAI và trình bày tự tin khi phỏng vấn

> Bạn đã có đủ tài liệu. Vấn đề không phải thiếu kiến thức để đọc, mà là **đọc theo thứ tự nào
> và luyện thế nào để nói ra được**. File này là bản đồ + lịch ôn + phương pháp luyện nói.

---

## 1. Bản đồ tài liệu — cái nào dùng làm gì

| Tài liệu | Dùng khi nào |
|---|---|
| [VAN_HANH_DU_AN.md](VAN_HANH_DU_AN.md) | Ngày 1 — hiểu các bộ phận và cách chạy, thuật ngữ giải thích trong ngoặc |
| [FOODAI_CODE_WALKTHROUGH_VI.md](FOODAI_CODE_WALKTHROUGH_VI.md) | Ngày 2–4 — "giáo trình" chính: giải thích code, luồng chạy, thuật toán training |
| [CASCADE_NHAN_DIEN_ANH.md](CASCADE_NHAN_DIEN_ANH.md) | Ngày 4 — phần MỚI NHẤT (chưa có trong walkthrough): cascade ảnh SigLIP 2 |
| [SO_TAY_BUG_PHONG_VAN.md](SO_TAY_BUG_PHONG_VAN.md) | Ngày 5 — kho chuyện bug thật để kể, kèm câu trả lời 30 giây |
| [FOODAI_INTERVIEW_QA_VI.md](FOODAI_INTERVIEW_QA_VI.md) | Ngày 6–7 — 116 câu hỏi + mock interview (phỏng vấn thử) + câu gài |
| [GIAO_TRINH_PYTHON_A_Z.md](GIAO_TRINH_PYTHON_A_Z.md) | Nếu Python còn yếu, học file này TRƯỚC — dạy từ số 0 kiểu làm-theo-từng-bước, 12 bài + đồ án |
| [PYTHON_QUA_FOODAI.md](PYTHON_QUA_FOODAI.md) | Sau giáo trình A–Z — soi lại các khái niệm Python trong chính code repo, kèm bài tập tự viết |
| `GLOSSARY.md` (gốc repo) | Tra thuật ngữ bất cứ lúc nào |
| `plan.md` (gốc repo) | Nhật ký quyết định theo ngày — đọc lướt để nhớ "vì sao hồi đó mình đổi hướng" |

## 2. Nguyên tắc học (quan trọng hơn lịch)

1. **Học chủ động, không đọc trôi:** đọc xong mỗi mục → **gấp tài liệu lại → tự giảng to thành tiếng** như đang giảng cho bạn cùng phòng (kỹ thuật Feynman — nếu không giảng lại được bằng lời đơn giản nghĩa là chưa hiểu). Chỗ nào ấp úng, mở lại đọc đúng chỗ đó.
2. **Tay phải bẩn:** mỗi khái niệm phải đi kèm một hành động thật trên máy (chạy lệnh, đọc file code, cố tình làm hỏng rồi xem lỗi). Kiến thức chỉ-đọc sẽ bay hơi trước cửa phòng phỏng vấn.
3. **Vẽ tay 3 sơ đồ, mỗi ngày vẽ lại 1 lần không nhìn tài liệu:** (a) sơ đồ các service + port, (b) luồng `/analyze` từ ảnh đến kcal, (c) cascade 3 tầng. Vẽ được từ trí nhớ = nói được trên bảng trắng.
4. **Mỗi câu trả lời kết bằng con số hoặc trade-off** (sự đánh đổi): "53.6% @ 95.2%", "thà tốn 1 lượt Vision còn hơn trả lời sai" — đây là thứ khiến người nghe tin bạn làm thật.

## 3. Lịch 7 ngày (mỗi ngày ~2–3 giờ)

### Ngày 1 — Chạy được và trỏ tay gọi tên từng bộ phận
- Đọc [VAN_HANH_DU_AN.md](VAN_HANH_DU_AN.md), rồi tự chạy: `bash scripts/dev_up.sh` → mở `http://127.0.0.1:8000/docs` → `bash scripts/smoke_test.sh`.
- Bài tập: tắt Docker rồi gọi `/ready` xem lỗi gì; bật lại. Đọc `logs/api.log` tìm dòng startup.
- ✅ Đạt khi: giảng lại được bảng service/port không nhìn tài liệu, và giải thích được `/live` khác `/ready` chỗ nào.

### Ngày 2 — Luồng vàng: từ ảnh đến kcal
- Đọc walkthrough mục 5, 7, 8 (luồng đầy đủ + upload + `backend/api/analyze.py`).
- Bài tập: mở [analyze.py](../backend/api/analyze.py) và **đọc đối chiếu từng bước** với tài liệu; lấy 1 ảnh món ăn gọi thử `/analyze` qua trang `/docs` (1 lượt thôi — tốn tiền Vision), đọc response từng field.
- ✅ Đạt khi: vẽ tay được sơ đồ luồng `/analyze` và trả lời được "request đi qua những file nào theo thứ tự nào".

### Ngày 3 — Dữ liệu: PostgreSQL, Qdrant, toán dinh dưỡng
- Đọc walkthrough mục 10, 11 (lookup hai lớp, `vn_norm`, toán per-gram) + mục 16 (Alembic, seed).
- Bài tập: gọi `GET /dishes/lookup` với "pho bo" (không dấu) và "Phở bò" — giải thích vì sao cả hai đều ra; gọi `/ingredients/search` với từ cố tình sai chính tả xem tầng semantic cứu thế nào.
- ✅ Đạt khi: trả lời trôi "tại sao PostgreSQL là source of truth còn Qdrant chỉ là index dựng lại được" + "vnfood khác vnmeal chỗ nào".

### Ngày 4 — AI: training + cascade mới nhất
- Đọc walkthrough mục 13–15 (training EfficientNet-B0, evaluation) rồi **toàn bộ** [CASCADE_NHAN_DIEN_ANH.md](CASCADE_NHAN_DIEN_ANH.md).
- Bài tập: mở [recognition_cascade.py](../backend/services/recognition_cascade.py) đọc hàm `decide_cascade` (ngắn, thuần logic); tự giải thích threshold vs margin bằng ví dụ Phở 0.85 / Hủ tiếu 0.84.
- ✅ Đạt khi: thuộc bảng con số (0.82 / 0.02 / 53.6% @ 95.2% / 62.1%) và trả lời được "tại sao không train thêm lớp mới".

### Ngày 5 — Chuyện bug: nguyên liệu kể chuyện
- Đọc [SO_TAY_BUG_PHONG_VAN.md](SO_TAY_BUG_PHONG_VAN.md). Chọn **3 bug tủ** (gợi ý: A1 None.strip, B1 promote sai split, C1 uvicorn kẹt shutdown — phủ đủ 3 mảng backend/ML/vận hành).
- Bài tập: với mỗi bug tủ, mở commit thật xem diff: `git show 61a936d`, `git show 2823763`... Kể to từng bug theo công thức 5 bước, bấm giờ ≤ 60 giây.
- ✅ Đạt khi: kể 3 bug không vấp, mỗi bug kết được bằng một bài học khái quát.

### Ngày 6 — Ôn theo bộ câu hỏi + tự phản biện
- Đọc [FOODAI_INTERVIEW_QA_VI.md](FOODAI_INTERVIEW_QA_VI.md): mục 2 (cheat sheet số liệu), mục 3–8 đọc dạng "che đáp án — tự trả lời — mở ra so".
- Đặc biệt luyện mục 17 (câu gài) và 18 (những câu không nên nói).
- ✅ Đạt khi: trả lời 20 câu ngẫu nhiên, tự chấm ≥ 15 câu trôi chảy.

### Ngày 7 — Mock interview (phỏng vấn thử) tổng duyệt
- Chạy 3 vòng mock ở mục 19 của bộ Q&A: tự bấm giờ, **ghi âm lại và nghe lại** (nghe lại là bước ai cũng bỏ qua nhưng hiệu quả nhất — bạn sẽ tự thấy chỗ nói vòng vo).
- Luyện bài "giới thiệu project 60 giây" cho đến khi nói 3 lần giống nhau cả 3.
- Tổng duyệt: vẽ lại 3 sơ đồ từ trí nhớ lần cuối.

## 4. Bài giới thiệu 60 giây (học thuộc dàn ý, không thuộc lòng từng chữ)

1. **Bài toán:** app chụp ảnh món Việt → nhận diện món → tính dinh dưỡng từ database chuẩn (USDA + bảng thành phần VN), không để LLM "bịa" số calo.
2. **Kiến trúc:** FastAPI + PostgreSQL (nguồn sự thật) + Qdrant (tìm ngữ nghĩa) + cascade nhận diện 3 tầng rẻ-trước-đắt-sau: album ảnh SigLIP 2 → CV cục bộ → Vision cloud.
3. **Con số:** cascade tự chốt 53.6% ảnh với precision 95.2% → cắt hơn nửa chi phí cloud; end-to-end baseline 62.1% top-1, 342 test pass.
4. **Điểm tự hào:** ngưỡng đo bằng script tune chứ không đoán; feedback người dùng tự làm dày album (data flywheel); mọi con số dinh dưỡng đều truy được nguồn gốc.
5. **Thành thật:** nêu 1 hạn chế đang có kế hoạch xử lý (các cặp món dễ nhầm như Bún bò Huế ↔ Bún riêu).

## 5. Sau 7 ngày — duy trì

- Mỗi tuần 1 lần: chạy lại `dev_up.sh` + smoke test + kể lại 1 bug bất kỳ (chống quên).
- Trước mỗi buổi phỏng vấn 1 ngày: đọc lại cheat sheet số liệu (QA mục 2) + bảng con số cascade + lướt mục "câu gài".
- Khi thêm tính năng mới vào project: **ghi ngay bug gặp phải vào [SO_TAY_BUG_PHONG_VAN.md](SO_TAY_BUG_PHONG_VAN.md)** — kho chuyện của bạn phải sống cùng project.
