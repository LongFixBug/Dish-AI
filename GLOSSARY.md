# Từ điển thuật ngữ FoodAI

> File này giải thích mọi thuật ngữ kỹ thuật trong dự án bằng ngôn ngữ đơn giản nhất.
> Mục tiêu: đọc tới đâu hiểu tới đó, không cần tra Google.

---

## 1. Machine Learning / AI cơ bản

### Model (mô hình)
Một chương trình máy tính được "học" từ dữ liệu thay vì được lập trình thủ công.

**Ví dụ đời thường**: Dạy em bé phân biệt chó với mèo. Bạn chỉ 100 tấm ảnh "đây là chó", "đây là mèo". Sau đó em bé tự nhìn ảnh mới và nói "chó" hay "mèo". Em bé = model. 100 tấm ảnh = dữ liệu huấn luyện.

### Training / Huấn luyện
Quá trình cho model xem dữ liệu có đáp án để nó tự điều chỉnh và giỏi lên.

### Inference / Dự đoán
Dùng model đã huấn luyện xong để dự đoán trên dữ liệu mới (dữ liệu nó chưa từng thấy).

### Epoch
Một lượt model xem TOÀN BỘ dữ liệu huấn luyện đúng 1 lần.

**Ví dụ**: Bạn có 75 tấm ảnh. 1 epoch = model xem hết 75 tấm ảnh. 15 epoch = model xem đi xem lại 75 tấm ảnh đó 15 lần. Càng nhiều epoch càng học kỹ, nhưng quá nhiều thì "học thuộc lòng" (overfitting).

### Loss / Hàm mất mát
Con số đo độ SAI của model. Loss cao = model đang đoán sai nhiều. Loss thấp = model đang đoán đúng. Mục tiêu huấn luyện: làm loss càng thấp càng tốt.

### Accuracy / Độ chính xác
Tỉ lệ % model đoán đúng. 85% accuracy = 100 ảnh đoán đúng 85 ảnh.

### Overfitting / Học thuộc lòng
Model nhớ chính xác từng ảnh trong tập huấn luyện, nhưng gặp ảnh mới thì đoán sai. Giống như học sinh học thuộc lòng đáp án mà không hiểu bài.

### Weights / Trọng số
Các con số bên trong model, được điều chỉnh dần trong quá trình huấn luyện. Đây là "kiến thức" của model. File `.pth` chính là file lưu các con số này.

---

## 2. Computer Vision (Thị giác máy tính)

### ResNet50
Một model nhận diện ảnh rất nổi tiếng, do Microsoft nghiên cứu năm 2015. **ResNet** = Residual Network (mạng dư). **50** = 50 tầng (layer).

**Tại sao dùng ResNet50?**
- Đã được huấn luyện sẵn trên ImageNet (1.2 triệu ảnh, 1000 loại đối tượng: chó, mèo, xe hơi, cây cối...)
- Nó đã biết cách "nhìn" ảnh: nhận diện cạnh, màu sắc, hình dạng, texture
- Mình chỉ cần dạy thêm phần cuối: "đây là phở, đây là bún chả, đây là cơm tấm"
- Khỏi cần huấn luyện từ đầu (tốn hàng triệu ảnh + hàng tuần)

### Pretrained model / Mô hình huấn luyện sẵn
Model đã được người khác huấn luyện trên dữ liệu khổng lồ. Mình tải về dùng luôn, khỏi train từ số 0.

**Tại sao dùng?** Tự train từ đầu cần GPU xịn + vài tuần + vài triệu ảnh. Không thực tế. Dùng hàng có sẵn rồi "điều chỉnh" (fine-tune) nhanh hơn gấp 100 lần.

### Fine-tuning / Tinh chỉnh
Lấy model pretrained, giữ nguyên phần "mắt" (backbone), chỉ dạy lại phần "não" (head) cho bài toán của mình.

```
ResNet50 gốc:  Nhìn ảnh → Nhận diện 1000 loại (chó, mèo, xe...)
ResNet50 mình: Nhìn ảnh → Nhận diện 3 món (phở, bún chả, cơm tấm)

Phần "mắt" (backbone)    → Giữ nguyên, freeze lại
Phần "não" (head, fc)    → Thay mới, train lại
```

### Backbone / Xương sống
Phần đầu của model, làm nhiệm vụ "nhìn" và trích xuất đặc trưng từ ảnh (cạnh, màu, texture). Phần này dùng chung cho mọi bài toán.

### Head / Classification head / Đầu phân loại
Phần cuối của model, nhận đặc trưng từ backbone và quyết định "đây là món gì". Phần này được thay mới và train lại.

### Freeze / Đóng băng
Khi freeze một layer, weights của nó KHÔNG được cập nhật trong quá trình train. Mình freeze backbone (giữ nguyên kiến thức cũ), chỉ train head (dạy kiến thức mới).

**Tại sao freeze?**
- Backbone đã giỏi nhìn rồi, không cần dạy lại
- Chỉ train head → nhanh hơn, cần ít dữ liệu hơn
- Tránh phá hỏng kiến thức đã có

### Transfer Learning / Học chuyển giao
Kỹ thuật dùng kiến thức từ bài toán A để giải bài toán B. Ở đây: dùng model dạy nhận diện 1000 vật thể → dạy nhận diện 3 món Việt.

### Augmentation / Tăng cường dữ liệu
Từ 1 ảnh gốc, tạo ra nhiều phiên bản biến thể: lật ngang, xoay, phóng to, đổi màu. Mục đích: model thấy cùng 1 tô phở ở nhiều góc, ánh sáng khác nhau → học tổng quát hơn.

### Tensor
Mảng nhiều chiều. Ảnh sau khi xử lý trở thành tensor [3, 224, 224]:
- 3: số kênh màu (Red, Green, Blue)
- 224: chiều cao (pixel)
- 224: chiều rộng (pixel)

Model chỉ hiểu số, không hiểu ảnh JPEG. Biến ảnh thành tensor là cách "dịch" ảnh sang ngôn ngữ của model.

### Normalize / Chuẩn hóa
Đưa giá trị pixel về cùng 1 thang đo. Ảnh gốc pixel từ 0-255. Sau normalize: giá trị quanh khoảng -2 đến +2. Model hoạt động tốt nhất với dữ liệu đã normalize.

### Softmax
Hàm biến output của model thành xác suất (tổng = 100%).

```
Output thô (logits): [2.1, 0.5, -1.3]
Sau Softmax:         [0.80, 0.15, 0.05]  ← xác suất cho 3 class
```

---

## 3. LLM & Embedding

### LLM (Large Language Model) / Mô hình ngôn ngữ lớn
Model hiểu và sinh ra văn bản. Ví dụ: ChatGPT, Gemini, Claude.

### llama.cpp
Phần mềm chạy LLM trên máy cá nhân (không cần cloud). Dùng định dạng GGUF.

**Tại sao dùng?**
- Chạy local, không tốn tiền API
- Tận dụng GPU Mac (Metal)
- Hỗ trợ cả LLM (chat) + Embedding (vector)

### GGUF
Định dạng file model đã nén, tối ưu để chạy trên máy cá nhân. `.gguf` = model đã được "đóng gói" sẵn, chỉ cần tải về chạy.

### Qwen2.5 7B
Một LLM mã nguồn mở của Alibaba. 7B = 7 tỉ tham số (weights). Hỗ trợ tiếng Việt tốt. Đây là "bộ não" chatbot.

### Embedding / Vector hóa
Biến 1 đoạn văn bản thành 1 dãy số (vector) biểu diễn Ý NGHĨA của nó.

**Ví dụ**:
- "phở bò" → [0.23, -0.45, 0.78, ...] (1024 con số)
- "phở bò tái" → [0.25, -0.42, 0.75, ...] (gần giống vector trên)
- "xe máy" → [0.89, 0.12, -0.34, ...] (khác xa)

2 vector gần nhau = 2 văn bản có nghĩa tương tự. Đây là nền tảng của RAG.

### Qwen3-Embedding 0.6B
Model chuyên làm embedding (0.6 tỉ tham số). Đầu vào: văn bản. Đầu ra: vector 1024 chiều.

---

## 4. Database & Vector Search

### Qdrant
Vector database chuyên dụng để lưu, lập chỉ mục và tìm kiếm embedding. Trong
FoodAI, Qdrant là chỉ mục dẫn về UUID; dữ liệu dinh dưỡng chuẩn vẫn nằm trong
PostgreSQL.

### HNSW (Hierarchical Navigable Small World)
Thuật toán tìm kiếm vector nhanh. Thay vì so sánh vector cần tìm với TẤT CẢ vector trong database (chậm), HNSW tạo chỉ mục thông minh → tìm gần đúng trong mili giây.

### RAG (Retrieval-Augmented Generation)
Kỹ thuật: trước khi hỏi LLM, mình TÌM thông tin liên quan từ database → nhét vào câu hỏi → LLM trả lời dựa trên thông tin đó (thay vì bịa).

**Ví dụ**: User hỏi "100g thịt bò bao nhiêu calo?"
1. Embed "thịt bò" → vector
2. Tìm trong Qdrant 5 ingredients gần nhất
3. Lấy thông tin dinh dưỡng của 5 ingredients đó
4. Gửi cho LLM: "Dựa vào dữ liệu sau: [thịt bò: 250 calo...], trả lời câu hỏi"
5. LLM trả lời có căn cứ, không hallucinate (bịa)

### Pipeline / Đường ống xử lý
Một chuỗi các bước nối tiếp nhau, đầu ra bước trước là đầu vào bước sau.

**Ví dụ đời thường**: Dây chuyền làm cơm — Vo gạo → Nấu → Xới ra bát. Mỗi công đoạn nhận đầu vào từ công đoạn trước, làm 1 việc, rồi chuyển tiếp.

**Trong FoodAI**: Upload ảnh → Nhận diện món → Tra dinh dưỡng → Tính tổng → Kết quả.

### Hallucinate / Ảo giác
LLM tự bịa ra thông tin nghe có vẻ đúng nhưng thực ra sai. RAG giúp giảm hallucinate bằng cách ép LLM dùng dữ liệu có thật.

---

## 5. Web & API

### FastAPI
Framework Python để xây dựng API. Tương đương Flask nhưng nhanh hơn, tự động tạo docs, hỗ trợ async.

### Async / Bất đồng bộ
Kỹ thuật xử lý nhiều việc cùng lúc không cần chờ. Khi gọi API (ví dụ: Qwen3.7 Plus), thay vì ngồi chờ 2 giây, server làm việc khác trong lúc chờ phản hồi.

### httpx
Thư viện Python để gọi HTTP request, hỗ trợ async. Thay thế hiện đại cho `requests`.

### SQLAlchemy
Thư viện Python để làm việc với database. Thay vì viết SQL thủ công (`SELECT * FROM ...`), mình viết code Python.

### Docker Compose
Công cụ khởi động nhiều service cùng lúc từ 1 file cấu hình. `docker compose up` = khởi động PostgreSQL + Qdrant cùng 1 lệnh.

---

## 6. Khái niệm khác

### Schema / Lược đồ dữ liệu
Bản thiết kế quy định dữ liệu phải có hình dạng như thế nào. Giống như form đăng ký: Họ tên (chữ), SĐT (số). Ai điền sai kiểu → báo lỗi.

### Pydantic
Thư viện Python để định nghĩa schema và validate dữ liệu. "Cái này phải là số, không được âm" → nếu dữ liệu sai, Pydantic báo lỗi ngay.

### Singleton
Pattern đảm bảo chỉ có DUY NHẤT 1 instance của 1 class trong cả chương trình. Dùng cho model (chỉ load 1 lần, xài chung).

### Checkpoint
File lưu trạng thái model tại 1 thời điểm. Chứa: weights, optimizer state, accuracy hiện tại. Có thể load lại để dùng hoặc train tiếp.

### CUDA / MPS
Công nghệ chạy tính toán trên GPU:
- CUDA: GPU NVIDIA
- MPS (Metal Performance Shaders): GPU Apple Silicon (Mac M1/M2/M3)

Model chạy trên GPU nhanh gấp 10-50 lần CPU.
