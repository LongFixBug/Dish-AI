# FoodAI — Bộ câu hỏi phỏng vấn kỹ thuật và cách trả lời thông minh

> Tài liệu mô phỏng phỏng vấn dựa trên code FoodAI tại ngày 25/07/2026.
> Mục tiêu là giúp bạn **giải thích đúng điều mình đã làm**, không phóng đại những phần
> project chưa có.

Nên đọc song song với
[bản giải thích code và luồng chạy](./FOODAI_CODE_WALKTHROUGH_VI.md). Tài liệu này tập
trung vào cách đối thoại trong phỏng vấn, không lặp lại toàn bộ source walkthrough.

## 1. Cách sử dụng tài liệu này

Đừng học thuộc từng chữ. Với mỗi câu hỏi, hãy nhớ bốn mảnh:

1. **Bài toán:** hệ thống cần giải quyết điều gì?
2. **Quyết định:** bạn chọn thiết kế nào?
3. **Lý do:** trade-off của lựa chọn đó là gì?
4. **Bằng chứng:** code, metric hoặc test nào chứng minh?

Công thức trả lời kỹ thuật ngắn:

```text
Kết luận trước
    -> giải thích cơ chế
    -> nêu trade-off
    -> dẫn chứng từ FoodAI
    -> nói bước cải thiện tiếp theo
```

Ví dụ không tốt:

> Em dùng Qdrant vì nó là vector database mạnh và hiện đại.

Ví dụ tốt:

> Em dùng Qdrant làm semantic index để xử lý tên món không khớp exact. PostgreSQL vẫn
> là source of truth; Qdrant chỉ trả UUID ứng viên rồi backend resolve lại record từ
> PostgreSQL. Thiết kế này giúp index có thể rebuild mà không làm mất dữ liệu chính.
> Hiện threshold là 0,75 và em bổ sung lexical guard để giảm false positive giữa các
> họ món như bún và phở.

Câu thứ hai mạnh hơn vì có cơ chế, invariant, con số và giới hạn.

## 2. Cheat sheet số liệu phải nhớ

| Hạng mục | Giá trị hiện tại |
| --- | --- |
| Backend | FastAPI, Python async |
| Auth | Argon2id, JWT access 15 phút, rotating refresh 30 ngày |
| Database chính | PostgreSQL port 5432 |
| Semantic index | Qdrant port 6333 |
| Production rate limit | Redis; analyze 10/phút, vision-only 3/phút |
| Embedding | Qwen3-Embedding-0.6B qua llama.cpp port 8081 |
| Vector size | 1.024 |
| Similarity | Cosine, threshold 0,75 |
| Local CV | EfficientNet-B0, input 224×224 |
| Local serving threshold | default legacy 0,85; release lấy từ manifest |
| Vision | Qwen Vision cloud, tối đa 3 menu item |
| Vision main/side threshold | 0,55 / 0,80 |
| Local classes | 8 |
| Train/validation images | 366 / 165 |
| Epoch | 18 |
| Learning rate | 5e-5 |
| Batch size | 16 |
| Loss | Weighted Cross Entropy |
| Optimizer | AdamW |
| Scheduler | CosineAnnealingLR |
| Validation accuracy gần nhất | 61,21% |
| Class validation yếu nhất | `ha_cao`, 42,11% |
| Upload limit | 10 MB, JPEG/PNG/WebP |
| Pixel limit | 20 triệu pixel, decode thật và strip EXIF |
| Mobile API timeout | 90 giây |
| `vn_dishes` có weight | 816/816; 652 estimate confidence <0,5 |
| Backend test gần nhất | 170 pass, coverage CI 85,05% |
| Flutter test gần nhất | 41 pass; `flutter analyze` sạch |
| Alembic head | `0012_production_hardening` |
| Model release | Test split độc lập + manifest/checksum; hiện chưa pass |

Không cần đọc hết bảng trong phỏng vấn. Hãy dùng đúng con số khi interviewer hỏi sâu.

## 3. Giới thiệu project

### Câu 1: “Em hãy giới thiệu FoodAI trong 60 giây.”

**Nhà tuyển dụng đang kiểm tra:** khả năng chọn thông tin quan trọng, hiểu end-to-end
và ownership.

**Trả lời mẫu:**

> FoodAI là hệ thống nhận diện món Việt từ ảnh và ước tính dinh dưỡng. Mobile Flutter
> gửi ảnh đến FastAPI. Backend thử EfficientNet-B0 local trước; chỉ khi confidence từ
> serving threshold của checkpoint và catalog có đủ nutrition lẫn serving weight thì dùng
> fast-path. Checkpoint legacy mặc định 0,85. Các trường hợp
> còn lại fallback sang Qwen Vision để nhận diện món ngoài tập class hoặc combo nhiều
> món. Tên món được reconcile với PostgreSQL, có Qdrant semantic fallback, nhưng
> PostgreSQL luôn là source of truth. Cuối cùng calorie và macro được tính bằng Python
> deterministic. Món chưa có trong catalog chỉ được stage vào hàng chờ, cần người duyệt
> trước khi trở thành dữ liệu tin cậy.

**Nếu được hỏi “điểm em tự hào nhất?”:**

> Không phải chỉ là gọi được model, mà là em thiết kế đường biên tin cậy: AI nhận diện,
> database giữ dữ liệu đã duyệt, toán dinh dưỡng không giao cho LLM, và món lạ không tự
> động làm bẩn catalog.

### Câu 2: “Em trực tiếp làm phần nào?”

**Trả lời thông minh:** nêu đúng phần bạn thật sự hiểu và làm, không nhận hết nếu có code
được hỗ trợ.

> Em làm và kiểm chứng luồng phân tích ảnh end-to-end: cấu trúc dataset, fine-tune model
> local, logic CV-first/Vision-fallback, lookup catalog, tính nutrition, candidate review
> và kết nối Flutter multipart API. Em cũng hoàn thiện auth/token rotation, secure upload,
> rate limit, observability, feedback retention, CI/container và model release gate. Với
> những phần em dùng công cụ hỗ trợ để xây nhanh,
> em vẫn đọc lại source, viết test và có thể giải thích các invariant chính. Những phần
> như email verification/password reset, diary cloud sync và recommendation model chưa
> hoàn thiện, nên em không xem chúng là feature đã xong.

Không nói “em làm tất cả” nếu không thể sửa một bug trực tiếp trước mặt interviewer.

### Câu 3: “Project này giải quyết pain point nào?”

> Người dùng khó ước tính calorie món Việt vì món thường là combo và dữ liệu không đồng
> nhất giữa per-100g với một khẩu phần. FoodAI giảm thao tác nhập tay: nhận diện từ ảnh,
> chuẩn hóa về tên menu, đối chiếu catalog Việt Nam rồi tính macro. Em tập trung vào khả
> năng giải thích nguồn dữ liệu và fallback thay vì hứa độ chính xác y tế.

### Câu 4: “Đây là demo AI hay một hệ thống phần mềm?”

> Phần model vẫn ở mức prototype do dataset nhỏ và chưa pass release gate, nhưng phần mềm
> đã có mobile client, auth, secure upload, async database, semantic index, fallback,
> human review, migration, observability, CI security scan và runbook. Em gọi nó là
> production-hardened engineering prototype, chưa phải production deployment hay sản phẩm
> medical-grade.

### Câu 5: “Tại sao chọn món Việt?”

> Vì dữ liệu và cách gọi món Việt có đặc thù: dấu tiếng Việt, nhiều tên gần nghĩa, combo
> cơm–thịt–món phụ, và nguồn `vnmeal` biểu diễn tổng của serving chứ không đồng nhất
> per-100g. Điều đó tạo ra bài toán thú vị cả ở computer vision, retrieval lẫn data
> modeling, không chỉ thay label của một classifier chung.

### Câu 6: “Nếu chỉ có ba phút demo, em sẽ demo gì?”

> Em chọn ba ảnh: một class local confidence cao để chứng minh fast-path; một combo để
> Vision trả main và side; một món lạ để cho thấy estimate vẫn dùng được nhưng record đi
> vào `dish_candidates` thay vì tự động vào catalog. Sau đó em tắt Qdrant hoặc local CV
> để chứng minh exact lookup và Vision fallback vẫn hoạt động.

## 4. Kiến trúc và luồng xử lý

### Câu 7: “Hãy mô tả luồng một request phân tích ảnh.”

> Flutter đọc ảnh thành bytes và gửi multipart field `file` đến
> `/api/v1/analyze` kèm Bearer JWT. Middleware áp rate limit; FastAPI đọc tối đa 10 MB,
> decode JPEG/PNG/WebP thật, giới hạn pixel, strip EXIF rồi ghi ảnh đã sanitize vào file
> tạm. Nếu local model đã load, inference chạy trong worker thread. Kết quả chỉ được dùng
> trực tiếp khi confidence đạt serving threshold và PostgreSQL có record với nutrition cùng
> `typical_grams`. Nếu không, backend gọi Vision. Mỗi menu item Vision được lookup exact,
> semantic khi phù hợp, rồi dùng nutrition DB hoặc estimate Vision nếu chưa có. Python
> cộng totals, API trả Pydantic response, mobile parse thành domain object và chuyển sang
> result screen. File tạm luôn được xóa trong `finally`.

### Câu 8: “Tại sao dùng hybrid local + cloud?”

> Local model có latency và chi phí thấp nhưng chỉ biết tám class; Vision cloud biết
> open-set và combo tốt hơn nhưng chậm, tốn phí và output ít ổn định. Hybrid cho phép
> class quen, rất chắc đi fast-path; phần khó mới trả chi phí cloud. Trade-off là logic
> điều phối phức tạp hơn và phải hiệu chỉnh threshold.

**Follow-up:** “Tại sao không luôn gọi cả hai rồi ensemble?”

> Có thể tăng recall nhưng latency/cost sẽ luôn bằng nhánh cloud và cần cơ chế hợp nhất
> label. Với mục tiêu hiện tại, cascade phù hợp hơn ensemble. Nếu production yêu cầu độ
> chính xác cao hơn chi phí, em sẽ benchmark cascade, parallel ensemble và selective
> routing trên cùng test set trước khi đổi.

### Câu 9: “Invariant quan trọng nhất của kiến trúc là gì?”

> PostgreSQL là source of truth. Qdrant chỉ là derived index; Vision candidate chưa
> duyệt không được xuất hiện như catalog chính thức; và khi DB có nutrition, con số Vision
> không được ghi đè. Các test trong project khóa chính ba invariant này.

### Câu 10: “Tại sao không viết tất cả trong endpoint?”

> Endpoint nên chỉ điều phối HTTP. Lookup nằm ở service để có thể dùng từ endpoint,
> script và test; phép toán nằm trong schema nutrition để không viết lại; inference nằm
> trong `ml/` vì có dependency và lifecycle riêng. Tách như vậy giảm coupling, test từng
> lớp dễ hơn và tránh một file vừa làm network, SQL, AI lẫn toán.

### Câu 11: “Tại sao FastAPI?”

> FastAPI phù hợp Python ML stack, hỗ trợ async I/O, dependency injection cho DB session,
> Pydantic validation và OpenAPI tự sinh. Trade-off là tác vụ PyTorch/Qdrant sync vẫn có
> thể block event loop, nên em phải chủ động đưa chúng sang thread hoặc tách model server
> khi scale.

### Câu 12: “Hệ thống có phải microservices không?”

> Backend nghiệp vụ hiện là modular monolith FastAPI. PostgreSQL, Qdrant, llama.cpp và
> Vision là service phụ trợ độc lập, nhưng em không gọi mỗi module Python là một
> microservice. Với quy mô hiện tại, modular monolith đơn giản để debug và transaction;
> chỉ tách inference service khi tải hoặc deployment lifecycle thật sự khác.

### Câu 13: “Tại sao dùng graceful degradation?”

> Vì local CV và semantic search là tối ưu bổ sung. Checkpoint hỏng không nên làm health
> endpoint chết nếu Vision vẫn dùng được; Qdrant offline không nên phá exact PostgreSQL.
> Startup bắt exception cho từng dependency và giữ đường fallback. Tuy nhiên production
> vẫn cần readiness/observability để không che giấu lỗi kéo dài.

### Câu 14: “Nếu Vision và local model bất đồng thì tin ai?”

> Cascade hiện không gọi Vision khi local đạt điều kiện fast-path, nên không có voting ở
> trường hợp đó. Khi local không đủ điều kiện, Vision chịu trách nhiệm label cuối; nhưng
> nutrition vẫn ưu tiên catalog DB nếu resolve được. Muốn so hai model cần log shadow
> prediction và đánh giá offline, không nên thêm luật cảm tính theo từng món.

### Câu 15: “Tại sao tên bữa ăn ghép bằng dấu cộng?”

> Response có thể chứa main và tối đa hai side. Ghép `Cơm sườn + Trứng ốp la` tạo label
> đọc được cho UI, còn dữ liệu cấu trúc vẫn nằm trong `dishes` và `nutrition.items`.
> Business logic không parse ngược chuỗi ghép; nếu cần lưu diary thì phải lưu từng item,
> không chỉ string hiển thị.

## 5. Backend, async và API

### Câu 16: “Async giúp gì trong project này?”

> Async giúp server chờ PostgreSQL, embedding HTTP và Vision HTTP mà không giữ cứng một
> thread cho từng request. Nó không tự làm PyTorch nhanh hơn. Những hàm đồng bộ nặng như
> model inference, file I/O lớn hoặc Qdrant sync client được bọc `asyncio.to_thread` để
> không chặn event loop.

### Câu 17: “`asyncio.to_thread` có giải quyết được scale inference không?”

> Không hoàn toàn. Nó bảo vệ event loop, nhưng nhiều request vẫn tranh CPU/GPU và memory
> trong cùng process. Khi tải tăng, em sẽ giới hạn concurrency bằng semaphore/queue và
> tách model serving thành process/service riêng, có batching và metric latency.

### Câu 18: “DB session được quản lý thế nào?”

> `get_session()` yield một `AsyncSession` theo request. Engine dùng pool 10 connection
> và overflow 5. Session request-scoped tránh transaction của hai request trộn nhau.
> `expire_on_commit=False` giữ ORM field đọc được sau commit. Các operation thay đổi dữ
> liệu commit rõ ràng; lỗi staging rollback.

### Câu 19: “Tại sao Pydantic schema khác SQLAlchemy model?”

> ORM model là hình dạng dữ liệu lưu trữ. Pydantic schema là hợp đồng API và object tính
> toán. Tách chúng giúp không lộ cột nội bộ, validate range/type ở boundary, và API không
> bị khóa vào database schema. Ví dụ `AnalyzeResponse` chứa source/error/dishes, những
> field đó không phải một table.

### Câu 20: “Tại sao endpoint đôi lúc trả HTTP 200 nhưng có `error`?”

> Code hiện giữ một response shape thống nhất cho lỗi Vision và mobile chủ động biến
> field `error` thành exception. Em hiểu đây không phải lựa chọn REST lý tưởng vì
> monitoring theo status code khó hơn. Nếu nâng production, em sẽ trả 502/503 cho upstream
> Vision, 422 cho input không phân tích được nếu phù hợp, đồng thời giữ error body có
> schema. Mobile hiện đã xử lý cả non-2xx và body error nên migration khả thi.

Đây là kiểu trả lời tốt: giải thích code hiện tại nhưng không cố bảo vệ một điểm yếu.

### Câu 21: “Upload được bảo vệ thế nào?”

> Backend allowlist JPEG/PNG/WebP, đọc chunk 1 MB và dừng khi vượt 10 MB, rồi dùng Pillow
> decode nội dung thật. Code đối chiếu format với MIME, giới hạn 20 triệu pixel, chặn
> decompression bomb, áp EXIF orientation và re-encode để strip metadata. File tạm dùng
> UUID + extension từ decoder và luôn xóa trong `finally`.

### Câu 22: “Có path traversal không?”

> Sau khi decode, code không dùng filename client trong đường dẫn tạm; chỉ dùng UUID và
> extension suy từ format thật. Vì vậy `../../secret` không thể điều khiển path. Feedback
> object key cũng được tạo server-side và filesystem backend từ chối absolute path/`..`.

### Câu 23: “Tại sao timeout mobile là 90 giây, Vision là 30 giây?”

> Timeout mobile bao trùm upload, queue, local inference, Vision, DB và download response;
> Vision client chỉ bao trùm upstream call. Mobile phải dài hơn timeout con để backend có
> thời gian trả lỗi có cấu trúc thay vì client cắt kết nối trước.

### Câu 24: “API có idempotent không?”

> Analyze về mặt response gần giống read operation nhưng có side effect stage candidate
> và tăng `observation_count`. Gửi lại cùng ảnh có thể tăng count, nên không hoàn toàn
> idempotent. Upsert giúp không tạo duplicate row. Nếu retry tự động ở production, em sẽ
> cân nhắc request id/idempotency key để tránh tăng quan sát do network retry.

### Câu 25: “Tại sao file tạm nằm trên local disk?”

> Đơn giản cho prototype và cả local CV lẫn Vision client đều nhận path. Khi chạy nhiều
> replica/container, local disk không phù hợp cho dữ liệu cần giữ; nhưng ảnh analyze chỉ
> sống trong request và được xóa. Feedback cần giữ lâu không dùng temp path: code đã có
> abstraction filesystem local/S3 production, metadata retention trong PostgreSQL và
> delete endpoint theo owner.

## 6. PostgreSQL và mô hình dữ liệu

### Câu 26: “Tại sao PostgreSQL là source of truth?”

> Nutrition cần constraint, transaction, migration, provenance và human review. Qdrant
> tối ưu nearest-neighbor nhưng không thay thế quan hệ/trạng thái duyệt. PostgreSQL giữ
> UUID và record chính; Qdrant có thể rebuild hoàn toàn từ đó.

### Câu 27: “Tại sao tách `vn_ingredients`, `vn_dishes`, `dish_candidates`?”

> Ba loại có semantics khác nhau. Ingredient lưu per-gram; dish lưu tổng của serving cùng
> `typical_grams`; candidate là estimate chưa duyệt, có status và observation count. Gộp
> chung sẽ tạo nhiều cột nullable và dễ vô tình dùng dữ liệu chưa duyệt như dữ liệu thật.

### Câu 28: “Vấn đề khó nhất của nutrition data là gì?”

> Không phải phép nhân mà là **basis** của con số. `vnfood` là per-gram, còn `vnmeal` là
> tổng cho một khẩu phần nguồn. Nếu coi nhầm tổng serving là per-100g, mọi kết quả sai có
> hệ thống. Em giữ serving totals nguyên bản, chỉ đổi sang per-gram khi có
> `typical_grams`, và gắn provenance cho weight ước lượng.

### Câu 29: “`typical_grams` lấy từ đâu?”

> Nhiều record dùng heuristic theo họ món: tô bún/phở lớn hơn snack, cơm phần ở khoảng
> khác. Heuristic còn điều chỉnh theo calorie tham chiếu nhưng clamp scale 0,75–1,25 và
> giới hạn min/max, làm tròn 25 g. Mỗi estimate có source, confidence và rule. Em không
> trình bày nó như số đo chính thức.

### Câu 30: “Tại sao phải có provenance?”

> Hai số cùng là 400 g nhưng một số đo thực tế và một heuristic không có cùng độ tin cậy.
> Provenance cho phép UI, review, audit và lần rebuild sau biết số đến từ đâu. Không có
> provenance thì dữ liệu estimate dần trông giống dữ liệu thật và rất khó sửa.

### Câu 31: “Làm sao tìm tiếng Việt không dấu?”

> Migration tạo SQL function `vn_norm` để lower-case và translate ký tự có dấu, ví dụ
> `Cơm sườn -> com suon`. Exact và ILIKE bọc cả column lẫn query bằng function này. Nó
> xử lý được truy vấn không dấu trước khi phải dùng vector search.

### Câu 32: “Tại sao dish không dùng substring match?”

> `Phở bò` là substring của `Phở bò xào` nhưng hai món khác nhau. Substring tăng recall
> giả nhưng làm nutrition sai. Dish dùng normalized exact rồi semantic có guard;
> ingredient autocomplete mới cho substring vì cách tìm nguyên liệu khác.

### Câu 33: “Unique constraint nào quan trọng?”

> `vn_dishes.dish_name` unique bảo vệ catalog khỏi hai món trùng tên chính thức.
> `dish_candidates.dish_name_key` unique gom các quan sát cùng tên normalized. Status có
> check constraint chỉ cho pending/approved/rejected. Constraint ở DB vẫn cần dù API có
> validation, vì script hoặc request concurrent có thể bỏ qua validation app.

### Câu 34: “Concurrency khi hai request thấy cùng món lạ?”

> Service dùng PostgreSQL `INSERT ... ON CONFLICT` và tăng observation count trong một
> statement atomic. Không làm kiểu `SELECT count -> Python + 1 -> UPDATE`, vì hai request
> có thể cùng đọc một giá trị rồi làm mất một lượt tăng.

### Câu 35: “Approve candidate có transaction thế nào?”

> Candidate được lock `FOR UPDATE`, kiểm tra trạng thái, tạo `VnDish` nếu cần rồi đánh dấu
> approved trong transaction. Sau commit PostgreSQL mới publish Qdrant. Nếu Qdrant lỗi,
> command cảnh báo reindex; source of truth vẫn đúng. Đây là eventual consistency có
> đường repair rõ ràng.

### Câu 36: “Tại sao dùng Alembic thay vì `create_all`?”

> `create_all` chỉ tạo trạng thái hiện tại, không mô tả cách nâng database đang có dữ
> liệu. Alembic lưu lịch sử version, upgrade/downgrade và migration dữ liệu. Nó cho local,
> CI và production tiến qua cùng schema contract.

## 7. Embedding, Qdrant và retrieval

### Câu 37: “Embedding là gì trong project này?”

> Embedding biến tên món/nguyên liệu thành vector 1.024 chiều sao cho text gần nghĩa có
> hướng gần nhau. Query và catalog dùng cùng model Qwen3-Embedding. Qdrant tìm vector có
> cosine similarity cao thay vì so ký tự tuyệt đối.

### Câu 38: “Tại sao dùng cosine similarity?”

> Với text embedding, hướng vector thường biểu diễn semantics tốt hơn độ lớn. Cosine đo
> góc giữa hai vector. Tuy nhiên lựa chọn thực tế phải benchmark trên eval queries; code
> hiện dùng cosine và threshold 0,75, không nên coi 0,75 là hằng số đúng cho mọi model.

### Câu 39: “Qdrant trả đúng tên rồi, sao còn query PostgreSQL?”

> Payload vector có thể stale, thiếu nutrition hoặc bị sửa ngoài luồng. Qdrant chỉ trả
> UUID/name/score để chọn candidate. Backend resolve UUID về PostgreSQL để lấy record
> authoritative và type đúng. Đây cũng ngăn vector index trở thành hai nguồn dữ liệu cạnh
> tranh nhau.

### Câu 40: “Lexical guard dùng để làm gì?”

> Semantic similarity có thể kéo `phở bò` gần `bún bò` vì cùng món nước và thịt bò. Guard
> bỏ dấu, tách token, reject khi family token như `pho` và `bun` khác nhau, đồng thời yêu
> cầu đủ token chung. Nó hy sinh một ít recall để giảm false positive có hậu quả nutrition.

### Câu 41: “Tại sao exact search trước semantic?”

> Exact nhanh, deterministic và độ chính xác cao khi tên đã normalize. Semantic tốn call
> embedding/Qdrant và có false positive. Retrieval cascade exact-first tối ưu latency lẫn
> precision; semantic chỉ xử lý phần exact không giải quyết được.

### Câu 42: “Đây có phải RAG không?”

> Project có retrieval-augmented component: query lấy context catalog qua text/vector.
> Nhưng analyze chính không phải RAG cổ điển nơi LLM sinh câu trả lời từ retrieved
> documents. Retrieval ở đây resolve entity rồi Python tính nutrition. Em sẽ gọi chính
> xác là semantic retrieval/reconciliation; RAGAS chỉ đang được dùng để đánh giá lookup
> ingredient.

### Câu 43: “Reindex Qdrant an toàn thế nào?”

> Script đọc record PostgreSQL, embed batch 50, validate đủ số vector, đúng 1.024 chiều và
> tất cả hữu hạn. Nó tạo xong toàn bộ embedding trước khi thay collection, upsert theo UUID
> rồi audit hai chiều: missing trong Qdrant và orphan trong Qdrant. `--check` chỉ audit,
> không mutate.

### Câu 44: “Nếu đổi embedding model thì sao?”

> Phải coi đó là một index version mới: xác minh vector dimension, rebuild toàn bộ point,
> benchmark threshold và eval query lại. Không trộn vector từ hai model trong cùng
> collection vì không cùng không gian biểu diễn. Production nên build collection mới rồi
> atomically switch alias để tránh downtime.

### Câu 45: “Embedding server chết thì request ra sao?”

> Exact PostgreSQL vẫn chạy. Semantic fallback bắt exception và trả miss an toàn. Điều đó
> giảm recall chứ không làm server crash. Production cần metric để biết semantic miss do
> thật sự không có món hay do dependency offline.

## 8. Vision LLM và prompt engineering

### Câu 46: “Vision output những gì?”

> Tối đa ba menu item. Mỗi item có tên, gram, main/side, confidence và total calories,
> protein, fat, carbs, fiber cho đúng lượng gram. Backend sau đó ưu tiên nutrition DB nếu
> match; estimate Vision chỉ dùng cho món chưa có catalog.

### Câu 47: “Tại sao prompt không yêu cầu tách từng nguyên liệu?”

> Vì catalog và UI làm việc ở dish/menu level. Nếu tách cơm, sườn, dưa leo, nước chấm rồi
> đồng thời match `Cơm sườn`, hệ thống dễ double-count. Prompt định nghĩa một combo chỉ có
> một main và tối đa hai side có tên riêng.

### Câu 48: “Prompt có phải business logic không?”

> Có. Prompt định nghĩa ontology output, threshold và ví dụ combo. Nhưng prompt không đủ
> làm validation. Backend vẫn clamp số, kiểm schema, lọc confidence, loại garnish và giới
> hạn ba item. Em coi model output là untrusted external input.

### Câu 49: “Vì sao temperature 0,1?”

> Đây là extraction theo JSON schema, cần ổn định hơn sáng tạo. Temperature thấp giảm biến
> thiên. Nó không bảo đảm JSON hợp lệ tuyệt đối, nên parser vẫn xử lý code fence/thinking
> tag và lỗi schema.

### Câu 50: “Tại sao main threshold 0,55 nhưng side 0,80?”

> Main là chủ thể ảnh và bắt buộc để response hữu ích. Side thường nhỏ, mờ, dễ suy diễn;
> false positive side cộng thêm calorie sai. Vì vậy hệ thống bảo thủ hơn với side.

### Câu 51: “LLM trả field sai thì sao?”

> Normalizer chấp nhận alias như `grams`, `weight_grams`, clamp số không âm, confidence về
> [0,1], bỏ phần tử không phải object và fallback sum ingredient grams cho response legacy.
> Nếu JSON không parse được thì raise `VisionError`, endpoint trả error có kiểm soát.

### Câu 52: “Có prompt injection từ ảnh không?”

> Ảnh có thể chứa text hướng dẫn model, nên không được tin Vision output. Hiện hệ thống
> giảm hậu quả bằng JSON validation, giới hạn item, không cho model trực tiếp chạy tool/SQL
> và không tự approve catalog. Production nên thêm adversarial image tests, content policy
> và tách system instruction mạnh hơn tùy provider.

### Câu 53: “Vision có được fine-tune trong project không?”

> Không. Qwen Vision là cloud inference; em chỉ thiết kế prompt và validation. Model được
> train trong repo là EfficientNet-B0 local. Em phân biệt rõ prompt engineering với model
> training để không nhận công việc mình chưa làm.

## 9. Thuật toán training local CV

### Câu 54: “Bài toán training là gì?”

> Supervised multi-class image classification: input RGB, output một trong tám class theo
> folder label. Nó không định vị bounding box và không xử lý multi-label combo; combo là
> lý do có Vision fallback.

### Câu 55: “Tại sao chọn EfficientNet-B0?”

> B0 nhỏ, khoảng 5,3 triệu parameter theo cấu hình timm, input 224 và cân bằng tốt giữa
> tốc độ với accuracy cho local prototype. Checkpoint EfficientNet trong project nhỏ hơn
> checkpoint ResNet50 cũ. Trade-off là capacity thấp hơn model lớn; em chọn theo constraint
> serving trước, rồi mới benchmark model khác trên cùng split.

### Câu 56: “Transfer learning giúp gì?”

> Dataset chỉ có 366 ảnh train nên train CNN từ đầu rất dễ overfit. Weights ImageNet đã
> biết edge, texture và shape; em thay classifier thành tám class rồi fine-tune toàn bộ
> backbone với learning rate 5e-5. Full fine-tune cho feature thích nghi texture món ăn,
> nhưng LR nhỏ để không phá nhanh kiến thức pretrained.

### Câu 57: “Tại sao không freeze backbone?”

> Freeze tiết kiệm compute và giảm overfit nhưng giữ feature generic. Food recognition
> phụ thuộc texture/màu khá nhiều, nên code chọn full fine-tune. Với dataset nhỏ, đây là
> trade-off cần thực nghiệm; em sẽ so freeze-head-only, gradual unfreeze và full fine-tune
> trên cùng validation/test set thay vì khẳng định một phương án luôn tốt.

### Câu 58: “Augmentation gồm gì và tại sao?”

> Random resized crop, horizontal/vertical flip, rotation, affine translate/scale, color
> jitter, perspective và random erasing. Mục tiêu là giảm học thuộc nền, góc và ánh sáng.
> Validation chỉ resize giữ tỷ lệ, center crop và normalize để metric ổn định. Em lưu ý
> augmentation quá mạnh có thể tạo ảnh thức ăn phi thực tế.

### Câu 59: “Vì sao normalize theo ImageNet?”

> Backbone pretrained được học với distribution đã chuẩn hóa theo ImageNet mean/std.
> Training và inference phải dùng preprocessing tương thích; nếu scale khác, feature đầu
> vào lệch khỏi điều model đã học.

### Câu 60: “Class imbalance được xử lý thế nào?”

> Weighted Cross Entropy với
> `weight[c] = total/(num_classes × count[c])`. Class ít ảnh bị phạt nặng hơn khi dự đoán
> sai. Nó không tạo thêm thông tin cho class ít ảnh; giải pháp gốc vẫn là thu thập dữ liệu
> tốt và xem per-class metric.

### Câu 61: “Cross Entropy hoạt động thế nào?”

> Model trả logits. Softmax chuyển thành probability; Cross Entropy lấy negative log
> probability của class đúng, có nhân class weight. Nếu model đặt xác suất thấp cho label
> thật, loss lớn. Backprop tính gradient và AdamW cập nhật weights.

### Câu 62: “Một training step có những gì?”

> Chuyển image/label sang device, `zero_grad`, forward lấy logits, tính weighted CE,
> `backward`, `optimizer.step`. Cuối epoch chạy validation trong `model.eval()` và
> `torch.no_grad()`, sau đó scheduler step.

### Câu 63: “Tại sao AdamW?”

> AdamW thích nghi learning rate theo parameter và tách weight decay khỏi gradient update,
> thường ổn cho fine-tuning. Em dùng LR nhỏ 5e-5. Đó là baseline thực dụng, không phải vì
> AdamW luôn thắng; production experiment cần compare SGD/momentum hoặc optimizer khác.

### Câu 64: “Cosine Annealing có tác dụng gì?”

> Learning rate giảm theo cosine trong 18 epoch: đầu học nhanh hơn, cuối update nhỏ để hội
> tụ quanh vùng tốt. Resume phải khôi phục scheduler state, nếu không learning-rate phase
> bị reset.

### Câu 65: “Checkpoint lưu những gì?”

> Epoch, architecture, model state, optimizer state, scheduler state, validation accuracy,
> class list, history, model version, recommended threshold và quality metrics. File epoch
> giữ để debug. Serving cần thêm manifest chứa checksum SHA-256, dataset fingerprint,
> evaluation split và kết quả gate; class mapping ngoài chỉ là fallback legacy.

### Câu 66: “Tại sao lưu best theo validation accuracy, không lấy epoch cuối?”

> Epoch cuối có thể overfit, nên validation vẫn cần để chọn experiment. Nhưng validation
> đã tham gia quyết định model nên không được dùng làm bằng chứng phát hành. Code hiện chỉ
> promote sau evaluation trên test split độc lập và gate gồm accuracy, macro-F1,
> worst-class, ECE, selective accuracy và coverage.

### Câu 67: “Kết quả model hiện tại thế nào?”

> Run gần nhất có validation accuracy 61,21% trên 165 ảnh; train accuracy 63,11%.
> `ha_cao` thấp nhất 42,11%, trong khi `com_tam` 80%. Em không xem 61% là production-ready;
> thư mục test hiện có 0 ảnh và chưa có approved manifest. Vì vậy API image production
> mặc định tắt CV; muốn bật phải có checkpoint test-gated trong image `Dockerfile.cv`.

### Câu 68: “Train và val gần nhau có nghĩa model tốt không?”

> Chỉ cho thấy chưa có khoảng generalization gap lớn trên split hiện tại. Nó không chứng
> minh data đại diện hay không leakage. Dataset nhỏ và test split chưa có ảnh; hai metric
> gần nhau vẫn có thể cùng thấp hoặc cùng biased.

### Câu 69: “Accuracy có đủ không?”

> Không. Dataset lệch class nên cần macro precision/recall/F1, per-class recall, confusion
> matrix, top-k và calibration. Với routing threshold còn cần selective accuracy: trong
> nhóm prediction đạt serving threshold, tỷ lệ đúng là bao nhiêu và coverage bao nhiêu.

### Câu 70: “Em chọn threshold 0,85 như thế nào?”

> 0,85 là fallback cho checkpoint legacy. Training đã tính ECE, risk–coverage và
> recommended threshold, nhưng threshold chỉ đáng tin để serving sau khi lặp lại trên test
> độc lập và manifest pass. Mỗi threshold phải cân selective accuracy, coverage, latency
> và cloud cost thay vì chọn theo cảm tính.

### Câu 71: “Overfitting được giảm bằng gì?”

> Transfer learning, augmentation, dropout 0,3, AdamW/weight decay và chọn best validation.
> Nhưng biện pháp mạnh nhất vẫn là dữ liệu đa dạng và test độc lập. Code chưa có early
> stopping; 18 epoch cố định và checkpoint theo epoch giúp chọn lại experiment, nhưng chỉ
> test gate mới quyết định serving.

### Câu 72: “Data leakage có thể xảy ra ở đâu?”

> Ảnh trùng/near-duplicate giữa train và val, ảnh cùng video burst chia sang hai bên, hoặc
> background đặc trưng cho class. Script feedback local legacy sort file rồi chia 80/20,
> chưa hash perceptual/group split và chưa nối storage mới. Importer production phải chỉ
> lấy approved feedback, deduplicate, group theo nguồn/user/session và giữ test set bất biến.

### Câu 73: “Nếu thêm class mới thì sao?”

> Tạo folder train/val, đảm bảo đủ dữ liệu, train lại classifier. Code resume có thể reset
> classifier khi class count thay đổi; em phải kiểm tra optimizer state tương thích, class
> mapping và regression các class cũ. Không chỉ thêm một folder rồi tin accuracy tổng.

### Câu 74: “Feedback có train online không?”

> Không. Endpoint yêu cầu user đăng nhập và consent, sanitize ảnh, lưu object S3/filesystem
> cùng metadata `pending`, owner và retention. Feedback không tự đi vào dataset; schema có
> trạng thái review nhưng admin review/import flow hiện chưa hoàn chỉnh. Sau khi bổ sung
> bước đó, batch training vẫn phải qua independent-test gate; user có thể xóa submission
> của chính mình.

## 10. Inference local

### Câu 75: “Preprocessing inference có giống training không?”

> Inference giống validation: resize cạnh ngắn, center crop 224, RGB, tensor và ImageNet
> normalization. Không dùng random augmentation khi serving. Nếu preprocessing lệch,
> accuracy có thể giảm dù weights không đổi.

### Câu 76: “`model.eval()` và `no_grad()` khác gì?”

> `eval()` đổi hành vi layer như dropout/batch norm. `no_grad()` tắt xây graph gradient để
> giảm memory và tăng tốc. Cần cả hai; một cái không thay thế cái kia.

### Câu 77: “Device được chọn thế nào?”

> Ưu tiên MPS trên Apple Silicon, rồi CUDA, cuối cùng CPU. Checkpoint load với
> `map_location=device`. Đây là portability local; production cần benchmark và pin rõ
> resource, không auto chọn ngẫu nhiên giữa replica.

### Câu 78: “Nếu thiếu PyTorch hoặc checkpoint?”

> `load()` giữ `_loaded=False`, predict trả `fallback_required`; startup không làm app sập.
> Vision xử lý request. Backend log lỗi để vận hành biết local optimization đang mất.

### Câu 79: “Top-5 dùng để làm gì?”

> Wrapper trả top-5 probability phục vụ debug, phân tích confusion hoặc UI tương lai. Luồng
> production hiện dùng top-1 và threshold. Top-5 không nên hiển thị như năm đáp án đúng;
> nó là ranking hypothesis.

## 11. Toán dinh dưỡng và độ tin cậy

### Câu 80: “Nutrition được tính như thế nào?”

> Với dish có serving total và weight, backend chia từng nutrient cho `typical_grams` để
> có per-gram, rồi nhân gram Vision ước lượng. Ingredient đã lưu per-gram sẵn. Từng item
> được cộng thành total. Chỉ khi mọi item có nutrition và gram cùng basis, code mới scale
> về per-100g bằng `100/total_grams`; nếu có source serving thiếu weight thì đánh dấu
> `per_100g_available=false`. Tất cả là Python deterministic và clamp giá trị âm.

### Câu 81: “Cho ví dụ số.”

> Record 400 g có 640 kcal thì mật độ là 1,6 kcal/g. Nếu phần ảnh 300 g, kết quả là
> 480 kcal. Nếu thêm trứng 80 kcal thì bữa ăn 560 kcal. Em giữ phép tính trong hàm dùng
> chung để endpoint và UI adjustment không viết lại công thức.

### Câu 82: “Nếu dish có nutrition nhưng thiếu weight?”

> Không thể suy per-gram. Code dùng serving total hiện có thay vì bịa mẫu số. Kết quả gram
> có thể vẫn đến từ Vision nhưng nutrition basis không scale. Đây là hạn chế cần hiển thị
> provenance; dài hạn nên bổ sung weight được review.

### Câu 83: “Các confidence hiện có nghĩa là gì?”

> `recognition_confidence` là confidence của nhánh nhận diện; `catalog_coverage_score` là
> số item `found_in_db=True` chia tổng item cộng missing. Field legacy `confidence_score`
> vẫn bằng catalog coverage để tương thích. Chúng không phải portion confidence và model
> confidence vẫn cần calibration. Mobile hiển thị recognition và catalog coverage riêng.

### Câu 84: “Tại sao DB nutrition thắng Vision?”

> Catalog đã duyệt có provenance và ổn định; Vision estimate có variance giữa request.
> Nếu model vừa nhận diện vừa tự ghi đè con số chuẩn, kết quả khó reproduce. Vision chỉ
> lấp khoảng trống để UX dùng tạm, đồng thời item được đánh dấu không có trong DB.

### Câu 85: “Có thể dùng kết quả này như tư vấn y tế không?”

> Không. Nhận diện, gram và typical serving đều có sai số. Đây là estimate hỗ trợ tracking,
> không phải thiết bị đo hay tư vấn y tế. Production cần disclaimer, validation chuyên gia,
> range uncertainty và có thể yêu cầu user xác nhận portion.

## 12. Flutter và kết nối mobile

### Câu 86: “Mobile được tổ chức thế nào?”

> Theo feature: auth, onboarding, dashboard, analyze, suggestions; core chứa theme/config/
> widget dùng chung. `AppState` + `AppScope` giữ session/profile/diary/preferences tập
> trung; auth và analyze tách API gateway khỏi presentation/domain. `MaterialPageRoute`
> vẫn đủ đơn giản ở quy mô hiện tại, chưa cần router framework lớn.

### Câu 87: “Tại sao inject `pickImage` và `analyzeImage`?”

> Để widget test không mở camera thật hay network thật. Test truyền fake function,
> điều khiển loading/success/error deterministic. Đây là dependency injection nhẹ, giảm
> coupling mà chưa cần framework DI.

### Câu 88: “Tại sao kiểm tra `mounted` sau `await`?”

> User có thể thoát screen khi image picker hoặc network đang chờ. Khi future hoàn tất,
> widget đã dispose; gọi `setState`/Navigator sẽ lỗi. `mounted` xác nhận State còn trong
> tree.

### Câu 89: “iOS simulator, Android emulator và máy thật gọi backend khác nhau thế nào?”

> iOS simulator dùng `127.0.0.1`; Android emulator dùng `10.0.2.2`; máy thật dùng IP LAN
> của Mac và FastAPI listen `0.0.0.0`. `API_BASE_URL` được truyền qua `--dart-define` để
> không hard-code môi trường.

### Câu 90: “Có integration bug nào em đã nhận ra?”

> Em từng thấy hai lỗi biên đáng chú ý: HEIC từ iPhone không nằm trong contract backend và
> nhiều request đồng thời có thể cùng refresh một token xoay vòng. Mobile hiện chặn HEIC
> sớm với thông báo rõ, còn `AppState` dùng một `_refreshInFlight` chung. Release build cũng
> fail nếu `API_BASE_URL` không phải HTTPS.

### Câu 91: “Các screen đều đã nối backend chưa?”

> Auth và Analyze đã nối backend thật. Register/login nhận JWT access + refresh token;
> refresh xoay vòng và logout revoke token. Hồ sơ, nhật ký, dashboard và preferences vẫn
> persist trong secure storage trên thiết bị, chưa cloud sync. Suggestions vẫn là rule
> local, không phải recommendation model đã được train/evaluate.

### Câu 91A: “Auth được thiết kế thế nào?”

> Password được hash Argon2id; login dùng dummy hash khi email không tồn tại để giảm timing
> leak. Access JWT HS256 sống 15 phút, kiểm issuer/audience/expiry/role. Refresh token là
> chuỗi opaque 30 ngày, database chỉ giữ SHA-256; mỗi refresh lock row, revoke token cũ và
> phát cặp mới. Analyze và feedback dùng `require_user`; dependency `require_admin` đã có
> nhưng hiện chưa được gắn vào một admin HTTP workflow hoàn chỉnh.

### Câu 91B: “Tại sao mobile phải single-flight refresh?”

> Refresh token xoay vòng chỉ dùng hợp lệ một lần. Nếu hai request cùng thấy access token
> sắp hết hạn và cùng refresh, request sau có thể dùng token đã bị revoke. `_refreshInFlight`
> cho mọi caller chờ cùng một Future, giống nhiều người dùng chung một lượt đổi vé thay vì
> mỗi người tự mang cùng vé cũ ra quầy.

## 13. Testing và evaluation

### Câu 92: “Em test những gì?”

> Backend test các nhánh CV/DB/Vision, candidate lifecycle, nutrition basis, serving
> adjustment, Qdrant UUID resolution, upload decode, auth security, token rotation, rate
> limit, readiness, observability, object storage, resilience, Alembic và model registry.
> Mobile test auth API/validation, refresh race, sign-out isolation, multipart, parser,
> widget và golden screen. Lần gần nhất backend 170 pass/85,05% coverage; Flutter 41 pass.

### Câu 93: “Mock quá nhiều có làm test vô nghĩa không?”

> Mock giúp kiểm branch và invariant nhanh nhưng không chứng minh service thật tương thích.
> Vì vậy cần cả unit test, integration test với PostgreSQL/Qdrant/embedding test container,
> contract test Vision response và end-to-end mobile–API. CI hiện đã chạy PostgreSQL,
> Qdrant, Alembic/seed/audit, backend/mobile tests, Docker smoke test, pip-audit và Trivy;
> khoảng trống còn lại là live provider E2E và staging deployment test.

### Câu 94: “Test quan trọng nhất là test nào?”

> `CV confidence cao + DB hit phải skip Vision` khóa cost/latency fast-path;
> `DB match phải bỏ nutrition Vision` khóa data trust; và `món lạ chỉ pending` khóa chống
> data poisoning. Đây là test của quyết định kiến trúc, không chỉ test getter/setter.

### Câu 95: “RAGAS đánh giá gì?”

> Query ingredient có ground truth hand-curated, lookup exact/vector trả retrieved context,
> RAGAS LLM judge chấm context recall và precision. Nó đánh giá retrieval, không đánh giá
> image classifier hay calorie accuracy. LLM judge có variance nên project còn có catalog
> eval deterministic cho các case cố định.

### Câu 96: “Ground truth có bị circular không?”

> Dataset eval hand-curated, không tự lấy search result làm ground truth; nếu làm vậy eval
> sẽ tự chấm mình đúng. Code verify ground-truth name có tồn tại DB nhưng expected semantic
> vẫn do người định nghĩa.

### Câu 97: “Golden test có tác dụng gì?”

> So ảnh render với baseline để phát hiện UI lệch ngoài ý muốn. Nó nhạy với font/platform,
> nên cần môi trường ổn định và review diff, không tự động coi mọi thay đổi pixel là bug.

## 14. Bảo mật và độ tin cậy

### Câu 98: “Rủi ro bảo mật lớn nhất hiện tại?”

> Auth/rate limit/secure decode đã có. Rủi ro còn lại lớn nhất là vận hành: secret thật và
> hạ tầng private chưa được cấu hình trong repo, chưa có email verification/password reset,
> feedback sẽ có nguy cơ poisoning nếu approval flow review yếu, và model chưa pass release
> gate. Production config fail fast với secret placeholder, memory limiter, local DB hoặc
> filesystem object storage.

### Câu 99: “Có lộ Vision API key cho mobile không?”

> Không. Mobile chỉ gọi FastAPI; key ở backend settings/secret manager. Nếu nhúng key cloud
> vào app, người dùng có thể extract và dùng quota. Backend áp auth, rate limit và không
> đưa provider error body thẳng về client.

### Câu 100: “Log có được ghi ảnh hoặc secret không?”

> JSON formatter gắn request ID, redact Bearer token/API-key pattern và không log base64
> ảnh. Ảnh analyze là file tạm đã strip EXIF; feedback có object key, consent và retention.
> Vẫn cần cấu hình log retention/access control ở nền tảng deploy vì application code không
> tự thay thế chính sách vận hành.

### Câu 101: “Data poisoning xảy ra thế nào?”

> User có thể gửi ảnh phở nhưng label bánh xèo. Submission hiện gắn owner, consent và trạng
> thái `pending`; không được tự vào training. Admin review/import hiện là khoảng trống cần
> bổ sung cùng anomaly/duplicate checks, dataset version/fingerprint và independent-test
> gate trước promotion.

### Câu 102: “Nếu cùng lúc nhiều request upload?”

> UUID tránh ghi đè file; per-user/IP rate limit chặn burst. Vision và embedding có
> semaphore bulkhead, pooled HTTP client, retry/backoff và circuit breaker. Local PyTorch
> vẫn chạy qua thread nên khi scale lớn cần tách bounded model workers/queue; candidate
> upsert đã atomic ở DB.

### Câu 103: “Làm sao quan sát hệ thống?”

> Code có JSON log + request ID, `/live`, dependency-aware `/ready` và Prometheus `/metrics`
> có token. Metrics hiện đo HTTP count/latency/in-progress, external call count/latency và
> analyze outcome theo source. Hạ tầng deploy vẫn cần scrape, dashboard và alert cho p95,
> error rate, readiness, Vision cost, DB pool và model-quality drift.

## 15. Scale và production

### Câu 104: “Nếu traffic tăng 100 lần, bottleneck ở đâu?”

> Vision latency/quota, local model inference, embedding call và DB/Qdrant connection là
> ứng viên chính. Vision/embedding đã có concurrency cap, retry và circuit breaker; rate
> limit dùng Redis giữa replica. Bước tiếp theo là trace p50/p95 từng stage, cache exact/
> embedding, tách bounded model worker, batch inference và autoscale theo queue/GPU.

### Câu 105: “Có cache được không?”

> Catalog lookup và embedding của tên text có thể cache vì thay đổi ít. Không nên cache
> toàn kết quả chỉ theo filename; có thể hash bytes nhưng ảnh gần giống vẫn khác và dữ liệu
> catalog có version. Cache key nên chứa model version, prompt version và catalog/index
> version để tránh trả kết quả stale không giải thích được.

### Câu 106: “Scale PostgreSQL và Qdrant thế nào?”

> Exact lookup cần index phù hợp, connection pool và query profiling. Qdrant scale theo
> số vector/QPS; catalog hiện nhỏ nên chưa cần sharding. Quan trọng là đo trước. Reindex
> production nên blue-green collection/alias, không force recreate collection đang phục vụ.

### Câu 107: “Deploy model version mới an toàn ra sao?”

> `cv_release.py` đánh giá test split độc lập rồi tạo checkpoint + manifest gồm version,
> classes, threshold, metrics, dataset fingerprint và SHA-256. `promote_model.py` chỉ nhận
> manifest pass và thay serving files atomically. `Dockerfile.cv` kiểm contract này khi
> build; deploy nên canary, theo dõi quality/latency và rollback về release đã duyệt trước.
> Validation metric một mình không bao giờ được promote.

### Câu 108: “Làm sao giảm chi phí Vision?”

> Tăng local coverage nhưng giữ precision: thêm dữ liệu class phổ biến, calibrate threshold,
> cache theo content hash nếu privacy cho phép, resize ảnh hợp lý, và chỉ gửi cloud khi
> router không chắc. Không nên hạ threshold local chỉ để giảm cost nếu làm tăng lỗi.

### Câu 109: “Làm sao đo end-to-end accuracy?”

> Cần dataset ảnh có label món, portion ground truth và nutrition reference. Đo riêng
> recognition accuracy, portion MAE/MAPE, nutrient MAE, catalog resolution rate, rồi metric
> end-to-end. Nếu chỉ đo tên món đúng thì chưa biết calorie sai do gram; nếu chỉ đo calorie
> tổng có thể hai lỗi tình cờ triệt tiêu.

### Câu 110: “Nếu bỏ Vision cloud thì sao?”

> Phải tăng phạm vi local/open-set: classifier nhiều class, embedding image-text hoặc VLM
> self-hosted, detection/segmentation cho combo và model portion. Đây là dự án dữ liệu và
> serving lớn hơn, không chỉ đổi một API call. Em sẽ benchmark chất lượng, GPU cost và
> latency trước.

## 16. Khó khăn, trade-off và cách nói có chiều sâu

### Câu 111: “Khó khăn kỹ thuật lớn nhất là gì?”

**Trả lời mẫu tốt:**

> Khó nhất là nối ba loại uncertainty: model không chắc tên, catalog có thể không có món,
> và serving weight có thể chỉ là heuristic. Nếu gộp chúng thành một confidence thì rất
> dễ đánh lừa UI. Em giải bằng cascade: local threshold, Vision item confidence, catalog
> found flag, candidate review và provenance của grams. Hệ thống chưa mô hình hóa uncertainty
> hoàn chỉnh, nhưng ít nhất không trộn estimate với dữ liệu đã duyệt.

### Câu 112: “Bug hoặc quyết định sai nào em từng gặp?”

> Một vấn đề quan trọng là dễ hiểu nhầm dữ liệu `vnmeal` thành per-100g, trong khi nó là
> serving total. Nếu normalize sai ở bước seed, toàn bộ calorie sẽ sai có hệ thống. Em giữ
> totals nguồn, thêm `typical_grams` có provenance, migration/test nutrition basis và chỉ
> chia khi có weight. Bài học là trước khi tối ưu model, phải xác định semantics dữ liệu.

Bạn có thể thay bằng bug thật mình từng trực tiếp sửa. Cần nói: triệu chứng → root cause
→ fix → prevention, không kể chung chung “em gặp nhiều khó khăn về data”.

### Câu 113: “Trade-off nào em chấp nhận?”

> Em chấp nhận recall thấp hơn ở semantic dish lookup để có precision cao hơn, bằng exact
> first và lexical guard. Trong nutrition, false positive có thể trả một con số rất tự tin
> nhưng sai, nên safe miss tốt hơn match bừa. Với search gợi ý thuần túy, trade-off có thể
> ngược lại.

### Câu 114: “Nếu làm lại từ đầu, em đổi gì?”

> Em sẽ định nghĩa evaluation set và data contract trước; version model/prompt/catalog từ
> đầu; tách các loại confidence rõ tên; thêm integration test bằng service thật; và thiết
> kế feedback review UI trước khi thu dữ liệu. Em vẫn giữ nguyên nguyên tắc PostgreSQL
> source of truth và deterministic nutrition.

### Câu 115: “Feature tiếp theo ưu tiên gì?”

> Không ưu tiên thêm screen. Em ưu tiên đóng vòng chất lượng: test set độc lập, confusion
> matrix/calibration, thêm dữ liệu class yếu, review candidate/feedback và portion
> confirmation UI. Sau đó mới làm email recovery và diary cloud sync. Những phần này biến
> prototype thành sản phẩm đo được hơn là chỉ tăng bề rộng giao diện.

### Câu 116: “Em học được gì?”

> Model chỉ là một component. Chất lượng end-to-end phụ thuộc data semantics, threshold,
> schema, fallback, concurrency, test và cách hiển thị uncertainty. Em cũng học rằng nói
> rõ một feature chưa làm đáng tin hơn việc gắn nhãn AI cho mọi màn hình.

## 17. Câu hỏi gài và cách không bị mất điểm

### “Project dùng ResNet50 đúng không?”

> Project có checkpoint ResNet50 lịch sử, nhưng serving/training hiện tại dùng
> EfficientNet-B0. Em lấy source `ARCH="efficientnet_b0"` làm chuẩn; production còn yêu
> cầu checkpoint đó có approved manifest, không suy từ tên file lịch sử.

### “Validation 61% mà em gọi model tốt?”

> Em không gọi nó production-ready. Nó là baseline có hoạt động và có per-class metric.
> Kiến trúc có selective routing và Vision fallback, nhưng test split hiện trống nên local
> CV production mặc định tắt. Chỉ model có independent-test manifest pass mới được đóng
> gói vào CV image.

### “Qdrant là source of truth phải không?”

> Không. PostgreSQL là source of truth; Qdrant là index có thể rebuild.

### “LLM tính calorie đúng không?”

> Khi catalog match, Python tính từ serving/per-gram. Vision estimate chỉ lấp khoảng trống
> cho món chưa duyệt và được đánh dấu rõ.

### “Có auth và recommendation rồi chứ?”

> Auth đã end-to-end với Argon2id, JWT và rotating refresh token. Recommendation chưa có
> model; suggestion hiện là rule local. Profile/diary cũng chưa cloud sync.

### “Đây là object detection à?”

> Local model là classification. Vision cloud trả menu item có cấu trúc, nhưng project
> không train bounding-box detector.

### “Confidence 1,0 nghĩa là chắc chắn đúng 100%?”

> Không. `catalog_coverage_score=1,0` chỉ nói mọi item đã resolve được catalog;
> `recognition_confidence` cũng cần calibration. Không có score nào mặc định là xác suất
> đúng thực tế.

### “Async nghĩa là inference chạy song song vô hạn?”

> Không. Async tối ưu thời gian chờ I/O. PyTorch sync được offload thread nhưng vẫn cần
> resource/concurrency control.

## 18. Những câu không nên nói

| Không nên nói | Nên nói |
| --- | --- |
| “Model chính xác 95%” khi không có report | “Val 61,21%; fast-path cần calibration riêng” |
| “Qdrant đảm bảo kết quả đúng” | “Qdrant đề xuất candidate, PostgreSQL xác nhận record” |
| “AI tự học từ user” | “Feedback pending có consent; phải review/import rồi retrain có version” |
| “App hoàn thiện production” | “Auth/analyze đã end-to-end; model gate, hạ tầng deploy, diary sync và recommendation còn thiếu” |
| “Em chọn vì công nghệ này hot” | Nêu constraint, trade-off và benchmark cần làm |
| “LLM hiểu nutrition” | Nêu rõ DB basis và phép toán deterministic |
| “Không có lỗi vì đã test” | Nêu phạm vi test và khoảng trống integration/production |
| “Em không biết” rồi dừng | “Em chưa triển khai; cách em kiểm chứng sẽ là…” |

Mẫu trả lời khi chưa biết:

> Phần đó em chưa triển khai nên em không muốn đoán như thể đã có số liệu. Giả thuyết của
> em là ..., em sẽ kiểm chứng bằng metric/test ..., và quyết định dựa trên ...

Đây không phải né câu hỏi; nó cho thấy phương pháp kỹ thuật.

## 19. Mock interview rút gọn

### Vòng 1 — HR/Hiring Manager, 10 phút

**Interviewer:** FoodAI có gì khác việc gọi thẳng Vision API?

**Bạn:**

> Vision chỉ là nhận diện fallback. FoodAI có local fast-path, catalog nutrition có
> provenance, semantic entity resolution, deterministic calculation và human review. Nếu
> gọi thẳng Vision, cùng một món có thể trả nutrition khác nhau và món hallucinated dễ đi
> thẳng đến user mà không có hàng rào dữ liệu.

**Interviewer:** Project đã có user thật chưa?

**Bạn:**

> Chưa có production users. Em đánh giá bằng dataset/test hiện có và không lấy UI prototype
> làm bằng chứng adoption. Mục tiêu hiện tại là chứng minh pipeline kỹ thuật và xây vòng
> thu thập feedback an toàn.

### Vòng 2 — AI Engineer, 20 phút

**Interviewer:** Vì sao model val chỉ 61% nhưng threshold 85%?

**Bạn:**

> Accuracy toàn bộ và confidence threshold là hai khái niệm khác. Router chỉ nhận subset
> confidence cao, kỳ vọng selective accuracy cao hơn nhưng coverage thấp hơn. Training đã
> tính risk–coverage trên validation, nhưng chưa có test split để xác nhận; 0,85 chỉ là
> fallback legacy. Model vì vậy chưa được promote. Bước đúng là đo lại subset accuracy trên
> test độc lập, đồng thời tính cloud cost.

**Interviewer:** Weighted loss có thể làm accuracy tổng giảm không?

**Bạn:**

> Có. Nó đánh đổi ưu tiên majority class để cải thiện minority recall. Vì vậy không chọn
> chỉ theo total accuracy; cần macro-F1, worst-class accuracy và yêu cầu sản phẩm. Em có
> flag baseline không class weight để so thực nghiệm. CLI truyền lựa chọn này thành tham số
> `use_class_weight` rõ ràng cho `main`, và có unit test khóa lại để tránh lỗi module
> `__main__` thay nhầm global.

**Interviewer:** Nếu embedding match sai `bún bò` thành `phở bò`?

**Bạn:**

> Qdrant không được quyết định một mình. Lexical guard phát hiện family token khác, reject
> candidate và có thể trả safe miss. Em muốn false negative có thể fallback/review hơn là
> false positive âm thầm tạo nutrition sai.

### Vòng 3 — Backend/System Design, 20 phút

**Interviewer:** Hai request cùng stage một món thì sao?

**Bạn:**

> Unique normalized key và PostgreSQL upsert atomic. Conflict không tạo row mới mà tăng
> `observation_count`. Khi approve, row lock bảo vệ state transition. Qdrant sync sau commit
> và có reindex repair nếu thất bại.

**Interviewer:** Scale lên 1.000 request/phút?

**Bạn:**

> Em đo p95 từng stage trước. Khả năng cao Vision quota và inference là bottleneck. Em sẽ
> đưa request qua bounded queue, tách model workers, limit concurrency, cache text embedding,
> autoscale theo queue, và giữ FastAPI stateless. Với Qdrant/Postgres em profile QPS/index/
>pool thay vì sharding sớm. Đồng thời rate-limit theo user vì Vision có chi phí.

**Interviewer:** Làm sao deploy không downtime khi đổi embedding?

**Bạn:**

> Build collection version mới từ PostgreSQL, validate dimension/parity/eval, sau đó đổi
> alias atomically. Không xóa collection đang phục vụ trước khi vector mới sẵn sàng.

## 20. Bài luyện tập tự trả lời

Tự ghi âm, mỗi câu tối đa 90 giây:

1. Vẽ pipeline lên giấy mà không nhìn tài liệu.
2. Giải thích khác nhau giữa model confidence và catalog coverage.
3. Chứng minh tại sao Qdrant không phải source of truth.
4. Tính calorie cho serving bằng một ví dụ số.
5. Giải thích một training step mà không dùng từ “AI tự học”.
6. Nêu ba giới hạn hiện tại mà không tự hạ thấp project.
7. Nêu một bug, root cause và test phòng tái diễn.
8. Thiết kế calibration cho threshold 0,85.
9. Thiết kế test set chống data leakage.
10. Nói feature nào là prototype và feature nào thật sự end-to-end.

Tiêu chí tự chấm:

- Có kết luận trong 15 giây đầu không?
- Có nhắc đúng file/metric/invariant không?
- Có nói trade-off hay chỉ kể công nghệ?
- Có phân biệt “đã làm” và “sẽ làm” không?
- Có trả lời đúng câu hỏi trước khi mở rộng không?

## 21. Câu hỏi nên hỏi ngược nhà tuyển dụng

Cuối buổi, bạn có thể hỏi:

1. Team đánh giá model theo offline metric hay business metric nào?
2. Quy trình từ experiment đến production/model rollback hiện ra sao?
3. Ai chịu trách nhiệm data quality và labeling guideline?
4. Team xử lý model monitoring, drift và human review như thế nào?
5. Với vị trí fresher, ba năng lực kỹ thuật quan trọng nhất trong ba tháng đầu là gì?
6. Một task gần đây mà AI Engineer phải phối hợp chặt với backend/product là gì?

Những câu này cho thấy bạn hiểu AI Engineer không chỉ train model trong notebook.

## 22. Câu kết thúc mạnh

Nếu interviewer hỏi “Em muốn chúng tôi nhớ điều gì về project này?”, có thể trả lời:

> FoodAI giúp em học cách xây hàng rào quanh model. Em không chỉ quan tâm model đoán tên
> gì, mà còn dữ liệu nào được tin, khi nào phải fallback, phép tính nào phải deterministic,
> feedback nào cần người duyệt và metric nào còn thiếu. Model hiện chưa production-ready,
> nhưng em có thể chỉ ra chính xác hệ thống đang đúng ở đâu, yếu ở đâu và cách kiểm chứng
> bước tiếp theo.

Đó là câu trả lời thông minh vì nó cụ thể, trung thực và thể hiện tư duy engineering.
