# Cascade nhận diện ảnh — kiến trúc mới nhất (26/7) giải thích từ đầu

> Đây là phần **mới nhất và "ăn điểm" nhất** của FoodAI khi phỏng vấn, nhưng chưa có trong
> [FOODAI_CODE_WALKTHROUGH_VI.md](FOODAI_CODE_WALKTHROUGH_VI.md) (tài liệu đó viết trước khi phần này ra đời).
> Đọc xong file này bạn phải tự vẽ lại được sơ đồ và giải thích được từng con số.

---

## 1. Bài toán: nhận diện "mọi món Việt" mà không phá sản

Trước đây hệ thống có 2 con đường nhận diện:

- **CV model cục bộ** (EfficientNet-B0 — mạng nơ-ron thị giác nhỏ chạy ngay trên máy): miễn phí, nhanh, nhưng là **closed-set** (tập đóng — chỉ biết đúng ~12–34 món đã train, gặp món lạ là đoán bừa thành món quen).
- **Vision API** (Qwen — AI "nhìn ảnh" trên cloud): biết gần như mọi món, nhưng **tốn tiền theo lượt gọi** và bị giới hạn 10 request/phút.

Mâu thuẫn: muốn phủ mọi món Việt (open-set — tập mở) thì phải dựa vào Vision, nhưng gọi Vision cho *mọi* ảnh thì vừa chậm vừa tốn. Cần một tầng đứng giữa: **rẻ như CV, mở như Vision**.

## 2. Ý tưởng: "album ảnh mẫu" thay cho train lại model

Thay vì train model phân loại (mỗi lần thêm món mới phải train lại từ đầu), ta xây một **album ảnh tham chiếu đã duyệt tay** và nhận diện bằng cách **so ảnh mới với album**:

1. Mỗi ảnh trong album được biến thành **embedding** (dãy 768 con số tóm tắt "nội dung thị giác" của ảnh) bằng model **SigLIP 2** (model của Google học cách xếp ảnh giống nhau lại gần nhau trong không gian số).
2. Toàn bộ vector nằm trong **Qdrant** (database chuyên tìm vector gần nhau), collection tên `dish_images`.
3. Ảnh người dùng upload → cũng biến thành vector → hỏi Qdrant: *"những ảnh mẫu nào giống ảnh này nhất?"* (kỹ thuật **k-NN** — k-nearest neighbors, tìm k hàng xóm gần nhất).

Ưu điểm chí mạng so với train model: **thêm món mới = thả thêm ảnh vào album + đánh index**, không cần train lại gì cả. Đây là câu trả lời chuẩn cho câu hỏi *"tại sao không train thêm lớp mới vào CV model?"*.

## 3. Luồng chạy đầy đủ (thuộc lòng sơ đồ này)

```
Ảnh upload
   │
   ▼
SigLIP 2 sidecar (:8082) — biến ảnh thành vector 768 chiều
   │  (sidecar = dịch vụ phụ chạy cạnh backend, tách riêng để
   │   backend không phải nạp model nặng vào bộ nhớ của mình)
   ▼
Qdrant `dish_images` — tìm ảnh mẫu giống nhất, gom điểm theo TÊN MÓN
   │
   ▼
decide_cascade(top1, top2):                    ← hàm PURE (thuần — chỉ tính toán,
   │                                             không gọi mạng/DB, nên test cực dễ)
   ├─ top1.score ≥ 0.82  VÀ  (top1 − top2) ≥ 0.02
   │        │
   │        ▼ ĐẠT → chốt luôn tên món, source="image_knn"
   │          → tra dinh dưỡng trong PostgreSQL → trả kết quả
   │          → KHÔNG tốn một xu Vision
   │
   └─ KHÔNG ĐẠT → gọi Vision API, nhưng đính kèm danh sách
              tối đa 8 tên ứng viên từ album vào prompt
              (Vision được "gợi ý đáp án" nên đoán trúng hơn)
```

Hai điều kiện chốt — giải thích được là ghi điểm:

- **threshold 0.82** (ngưỡng điểm giống tối thiểu): "giống đủ nhiều chưa?"
- **margin 0.02** (khoảng cách top-1 trừ top-2): "top-1 có **bỏ xa** top-2 không?" — nếu Phở được 0.85 mà Hủ tiếu cũng 0.84 thì dù điểm cao vẫn KHÔNG chốt, vì hai món đang "so kè" nghĩa là hệ thống đang phân vân.

## 4. Các con số phải nhớ (đo thật, không bịa)

| Con số | Ý nghĩa |
|---|---|
| 768 | Số chiều vector ảnh SigLIP 2 |
| 34 món / 1486 ảnh | Kích thước album tham chiếu trong Qdrant |
| 1160 + 427 | Số ảnh references (album) + golden (bộ chấm điểm), đã dedup bằng phash (mã băm cảm quan — hai ảnh gần giống nhau sẽ có mã gần nhau, dùng để lọc ảnh trùng lọt giữa 2 tập) |
| 0.82 / 0.02 / 8 | threshold / margin / số ứng viên tối đa gửi Vision |
| **53.6% @ 95.2%** | Trên bộ golden: cascade tự chốt được 53.6% số ảnh (coverage), và trong số chốt đó đúng 95.2% (precision) — nghĩa là **hơn nửa số ảnh không tốn tiền Vision**, đổi lấy ~5% rủi ro sai |
| 62.1% | End-to-end top-1 accuracy toàn hệ (29 lớp golden) — con số baseline trung thực, dùng làm mốc cải thiện |
| 10 req/phút | Giới hạn Vision API → eval script phải tự retry khi gặp lỗi 429 (mã "gọi quá nhanh") |

Cặp món hay nhầm nhất (confusable pairs — dùng cho phase cải thiện kế tiếp): Bún bò Huế ↔ Bún riêu, Phở ↔ Hủ tiếu, Bánh căn ↔ Bánh khọt. Kể được cặp nhầm cụ thể chứng minh bạn **thật sự nhìn vào lỗi của model** chứ không chỉ nhìn con số tổng.

## 5. Ngưỡng 0.82/0.02 ở đâu ra? — KHÔNG phải đoán

Đây là điểm phân biệt "làm thật" với "vibe": ngưỡng được **đo bằng máy**, không chọn cảm tính.

- `ml/evaluation/tune_cascade.py` chạy quét (sweep) nhiều cặp threshold/margin trên bộ golden, in ra bảng coverage/precision tương ứng → chọn điểm cân bằng (chốt nhiều nhất mà precision còn ≥ 95%).
- Kết quả được ghi làm **default trong `backend/config.py`** kèm comment ghi rõ ngày đo, kích thước album, số đo — để người sau biết nguồn gốc con số (provenance — xuất xứ dữ liệu).
- **Quy tắc vận hành:** album đổi lớn (thêm nhiều món/ảnh) → **phải tune lại ngưỡng**, vì phân bố điểm giống nhau đã thay đổi.

## 6. Hai lưới an toàn ít ai để ý (kể ra là điểm cộng lớn)

**Lưới 1 — chống "biến dạng tên qua đường vòng ngữ nghĩa":** album chốt "Phở bò", nhưng khi tra catalog bằng tìm kiếm ngữ nghĩa, tên có thể bị "morph" thành món khác hao hao. Hàm `is_name_refinement` kiểm tra tên sau tra cứu có thực sự là **phiên bản chi tiết hơn** của tên album không (so khớp không phân biệt dấu qua `_accent_key`) — nếu tên bị biến dạng thành món khác → bỏ kết quả album, chuyển sang Vision. Nguyên tắc: *thà tốn một lượt Vision còn hơn trả lời sai với vẻ mặt tự tin*.

**Lưới 2 — degrade mềm (xuống cấp êm ái):** sidecar SigLIP chết hoặc `image_embed_enabled=false` → cascade lặng lẽ bỏ qua, mọi ảnh đi thẳng Vision như trước. Hệ thống **mất tối ưu chi phí chứ không mất chức năng**. Client HTTP gọi sidecar dùng chung tầng resilience (retry — thử lại, circuit breaker — cầu dao ngắt khi lỗi liên tục, concurrency cap — trần số request đồng thời) với embedding chữ.

## 7. Vòng lặp dữ liệu tự béo lên

Khi người dùng **sửa lại tên món** qua tính năng feedback → ảnh đó cùng nhãn đúng được **upsert** (thêm-hoặc-cập-nhật) vào album. Nghĩa là: càng nhiều người dùng, album càng dày, cascade chốt được càng nhiều, chi phí Vision càng giảm. Đây là **data flywheel** (bánh đà dữ liệu) — từ khóa đáng nói trong phỏng vấn.

## 8. Bản đồ file của phần này

| File | Vai trò |
|---|---|
| `ml/serving/image_embed_server.py` | Sidecar FastAPI cổng 8082, nạp SigLIP 2, nhận ảnh trả vector. Chạy: `bash scripts/start_image_embed.sh` |
| `backend/services/image_embeddings.py` | Client gọi sidecar (kèm retry/circuit breaker), trả vector đúng thứ tự gửi |
| `backend/services/dish_image_index.py` | Nói chuyện với Qdrant `dish_images`: tìm k-NN, gom điểm theo món (best_score + votes) |
| `backend/services/recognition_cascade.py` | `decide_cascade` (quyết định chốt/không — hàm pure), `is_name_refinement` (lưới an toàn tên) |
| `backend/api/analyze.py` | Nối cascade vào luồng `/analyze`: chốt được → `_image_knn_response`; không → Vision kèm candidates |
| `scripts/index_dish_images.py` | Nạp album `data/images/references/` vào Qdrant |
| `scripts/download_datasets.py` | Tải dataset 30VNFoods stream từ Hugging Face (kho model/dataset cộng đồng) |
| `scripts/build_test_split.py` | Dựng tập test niêm phong cho việc release CV model |
| `ml/evaluation/recognition_eval.py` | Đo end-to-end accuracy trên bộ golden (tự retry khi Vision trả 429) |
| `ml/evaluation/tune_cascade.py` | Quét tìm threshold/margin tối ưu |
| `data/images/references/`, `data/images/golden/` | Album ảnh mẫu & bộ ảnh chấm điểm (đã dedup chéo) |
| `data/eval/class_names.json`, `data/eval/dish_aliases.json` | Map slug→tên có dấu; các tên gọi khác của cùng món |

## 9. Trả lời mẫu khi phỏng vấn

**"Em tối ưu chi phí AI thế nào?"**
> *"Em xây cascade 3 tầng theo nguyên tắc rẻ-trước-đắt-sau. Tầng giữa là image retrieval: ảnh upload được embed bằng SigLIP 2 rồi so k-NN với album 1486 ảnh mẫu đã duyệt trong Qdrant. Nếu top-1 đạt điểm ≥ 0.82 và bỏ xa top-2 ít nhất 0.02 thì chốt luôn không gọi cloud. Ngưỡng này em không đoán mà đo bằng script tune trên bộ golden 427 ảnh: chốt được 53.6% số ảnh với precision 95.2% — tức cắt hơn nửa chi phí Vision, đổi lấy dưới 5% rủi ro, và rủi ro đó còn được chặn thêm bằng một lưới kiểm tra tên món sau tra cứu."*

**"Tại sao không train thêm lớp mới vào model phân loại?"**
> *"Classification là closed-set — thêm món mới phải gom đủ ảnh và train lại, còn gặp món ngoài danh sách thì nó ép về món quen gần nhất mà không hề biết mình sai. Retrieval trên album thì thêm món mới chỉ cần thêm ảnh và đánh index, có cơ chế 'không đủ giống thì thôi' tự nhiên qua threshold, và feedback người dùng làm album tự dày lên — một data flywheel không cần train."*

**"Số 62.1% thấp thế?"**
> *"Đó là end-to-end top-1 trên 29 lớp golden — em cố tình công bố số trung thực làm baseline. Em đã phân tích ma trận nhầm lẫn: lỗi tập trung ở các cặp nhìn giống nhau như Bún bò Huế với Bún riêu. Kế hoạch là xử lý confusable sets có chủ đích thay vì tối ưu mù. Với em, một baseline trung thực kèm phân tích lỗi giá trị hơn một con số đẹp không giải thích được."*

---

> Đọc tiếp: [SO_TAY_BUG_PHONG_VAN.md](SO_TAY_BUG_PHONG_VAN.md) — trong đó có 3 "bẫy" gặp phải khi làm chính phần này (test không kín, uvicorn kẹt shutdown, quên tune lại ngưỡng).
