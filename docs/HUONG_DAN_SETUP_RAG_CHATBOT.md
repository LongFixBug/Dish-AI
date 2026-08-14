# RAG chatbot V0 trong FoodAI

Tài liệu này mô tả **đúng code đang chạy**. Đây là RAG đơn giản nhất: chưa có
planner, agent, tool calling, SSE hay RAGAS trong request người dùng.

## RAG là gì?

RAG là "mở đúng trang tài liệu trước khi trả lời":

```text
câu hỏi
-> embedding câu hỏi
-> Qdrant tìm đoạn gần nghĩa
-> đưa đoạn đó vào CONTEXT
-> local LLM trả lời
-> answer + nguồn
```

Ví dụ hỏi "Một tô phở bò thường gồm những gì?": Qdrant tìm `pho-bo.txt`, LLM
chỉ nhận nội dung đó trong `CONTEXT`, rồi trả lời. Nếu không có đoạn nào đủ
liên quan, LLM không được gọi và hệ thống trả câu cố định:

```text
Mình chưa tìm thấy tài liệu phù hợp để trả lời câu này.
```

## Thư viện

| Thư viện | Vai trò |
|---|---|
| `langchain-community` | `DirectoryLoader` đọc file `.txt` |
| `langchain-text-splitters` | `RecursiveCharacterTextSplitter` chia chunk |
| `langchain-core` | kiểu `Document`: text + metadata |
| `qdrant-client` | lưu vector, semantic search |
| `httpx` | gọi llama.cpp embedding và LLM |
| `FastAPI` + `Pydantic` | validate HTTP request/response |

LangChain V0 chỉ dùng để load và chunk. Qdrant, prompt và gọi LLM là code Python
đọc được trong `backend/services/rag.py`.

## File quan trọng

| File | Việc nó làm |
|---|---|
| `data/rag/documents.json` | manifest tài liệu được phép nạp |
| `data/rag/pho-bo.txt` | kiến thức demo |
| `schemas/rag.py` | schema manifest và API |
| `backend/services/rag.py` | toàn bộ flow RAG V0 |
| `scripts/ingest_rag.py` | document -> chunk -> vector -> Qdrant |
| `scripts/search_rag.py` | thử riêng retrieval |
| `scripts/ask_rag.py` | thử đủ retrieval + LLM |
| `backend/api/rag.py` | `POST /api/v1/rag/chat` |
| `mobile/lib/features/rag/` | Flutter API client và màn hỏi đáp |

## Chuẩn bị tài liệu

Mỗi `.txt` trong `data/rag/` phải có một entry trong `documents.json`:

```json
{
  "documents": [
    {
      "document_id": "pho-bo",
      "title": "Phở bò",
      "source": "foodai_demo",
      "file": "pho-bo.txt"
    }
  ]
}
```

- `document_id`: mã ổn định, không trùng; dùng tạo ID chunk.
- `title`: tên hiển thị trong citation.
- `source`: nhãn nguồn, ví dụ `foodai_demo`.
- `file`: đường dẫn tương đối tới file `.txt`.

`load_documents()` chặn ingestion nếu thiếu manifest, file manifest không tồn tại,
có file `.txt` không khai báo, hoặc nội dung file rỗng.

## Chunking

`split_documents()` dùng:

```python
RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    add_start_index=True,
)
```

- `chunk_size=500`: chunk tối đa khoảng 500 ký tự.
- `chunk_overlap=50`: lặp 50 ký tự giữa hai chunk để không cắt mất ý.
- `add_start_index=True`: lưu vị trí chunk trong text gốc.
- `chunk_index`: FoodAI thêm số thứ tự `0`, `1`, `2` cho chunk cùng document.

Chunk giữ `document_id`, `title`, `source`, `file_path` và `chunk_index`.

## Ingest và Qdrant

Chạy:

```bash
DEBUG=false uv run python -m scripts.ingest_rag
```

Luồng:

```text
documents.json + .txt
-> load_documents()
-> split_documents()
-> embed_text() từng chunk
-> kiểm tra vector đủ 1024 chiều
-> rebuild_rag_collection()
-> Qdrant rag_documents_v0
```

`embed_text()` dừng nếu vector không đủ 1024 chiều, thường là do chạy nhầm model.
`rebuild_rag_collection()` chỉ thay collection `rag_documents_v0` **sau khi** tất
cả chunk/vector hợp lệ; nó không đụng `food_catalog` hay `dish_images`.

## Retrieval, prompt và LLM

`search_chunks(question, limit=3)` embed câu hỏi, tìm nhiều nhất 3 point trong
Qdrant và yêu cầu `score_threshold=0.60`. `score` là cosine similarity, không
phải phần trăm chính xác.

Nếu có context, `build_prompt()` tạo prompt ngắn:

```text
Bạn là trợ lý FoodAI.
Chỉ trả lời dựa trên CONTEXT.
Nếu CONTEXT không đủ thông tin, hãy nói rõ là chưa đủ dữ liệu.

CONTEXT:
[1] ...

QUESTION:
...
```

`answer_question()` gọi local LLM `/v1/chat/completions` với `stream: false` và
`temperature: 0.2`. Không có context thì return ngay, không gọi LLM.

Thử riêng retrieval:

```bash
DEBUG=false uv run python -m scripts.search_rag
```

Thử toàn bộ RAG:

```bash
DEBUG=false uv run python -m scripts.ask_rag
```

## API và Flutter

```text
POST /api/v1/rag/chat
Authorization: Bearer <access token>
```

Request:

```json
{"question": "Một tô phở bò thường gồm những gì?"}
```

Response:

```json
{
  "answer": "Một tô phở bò thường gồm bánh phở...",
  "sources": [
    {
      "document_id": "pho-bo",
      "title": "Phở bò",
      "source": "foodai_demo",
      "score": 0.7323
    }
  ]
}
```

API cần đăng nhập, giới hạn câu hỏi 1--1.000 ký tự và rate limit 10 request/phút.
Lỗi Qdrant, embedding hoặc LLM trả `503` thân thiện, không lộ stack trace.

Flutter gọi endpoint trong `RagApi`; `RagChatScreen` hiển thị answer và citation.

## Chạy local từ đầu

Terminal 1:

```bash
docker compose up -d postgres qdrant
```

Terminal 2:

```bash
llama-server \
  --model models/Qwen3-Embedding-0.6B-Q8_0.gguf \
  --embedding --port 8081 --host 0.0.0.0
```

Terminal 3:

```bash
bash scripts/start_llama.sh
```

Terminal 4:

```bash
DEBUG=false uv run python -m scripts.ingest_rag
DEBUG=false uv run uvicorn backend.main:app --reload
```

Terminal 5:

```bash
cd mobile
flutter run
```

## V0 chưa làm

- chat nhiều lượt/lịch sử;
- streaming SSE;
- tool PostgreSQL catalog hay nhật ký cá nhân;
- planner, LangGraph, agentic RAG;
- RAGAS/LLM-as-judge.

Chỉ thêm các phần đó sau khi corpus lớn hơn và retrieval V0 có golden evaluation.

## Nâng cấp Agentic chat: `POST /api/v1/chat/stream`

RAG V0 vẫn giữ nguyên ở `/api/v1/rag/chat`. Chat nâng cao chạy **song song**
ở `/api/v1/chat/stream`, vì vậy nếu có sự cố vẫn có thể quay về V0 ngay.

Luồng của endpoint mới:

```text
message + tối đa 12 history messages
-> planner LLM tạo plan JSON hợp lệ
-> server kiểm tra route và tool allowlist
-> tool lấy dữ liệu PostgreSQL / Qdrant
-> LLM tạo câu trả lời theo từng token
-> SSE: meta -> delta... -> sources -> done
```

- `backend/api/chat.py`: mở endpoint SSE đã yêu cầu đăng nhập.
- `schemas/chat.py`: giới hạn kích thước message/history và chỉ chấp nhận các
  route/tool đã định nghĩa trước.
- `backend/services/chat_service.py`: điều phối planner, tool và câu trả lời.
- `backend/services/chat_tools.py`: kiểm tra arguments của tool; LLM không thể
  truyền `user_id` hay SQL.
- `backend/services/chat_llm.py`: gọi llama.cpp theo hai cách: JSON cho planner,
  stream cho câu trả lời.
- `mobile/lib/features/chat/`: giữ history trong bộ nhớ của màn chat và hiển thị
  token ngay khi SSE trả về.

Tool `search_knowledge_base(query)` nối hai phần trước đây đang tách riêng:
planner gọi tool này khi câu hỏi là FAQ/chính sách/kiến thức từ tài liệu, còn
tool gọi lại `search_chunks()` của RAG V0. Nó trả nhiều nhất 3 chunk đã vượt
`score_threshold`, gồm nội dung, `document_id`, title và source. Không có chunk
thì server trả câu cố định, không gọi LLM để đoán.

`search_catalog` có thể dùng Qdrant để tìm mờ, nhưng luôn đọc record và dinh
dưỡng cuối từ PostgreSQL. Tool cá nhân cũng nhận `user_id` từ access token,
không nhận từ planner. Vì vậy model chỉ *đề xuất việc cần tra*, còn server vẫn
quyết định quyền và dữ liệu nào được trả về.

Quy tắc chọn tool quan trọng:

- calo/dinh dưỡng của món → `search_catalog`;
- FAQ, policy, kiến thức có trong `.txt` → `search_knowledge_base`;
- “tôi đã ăn gì”, mục tiêu, gợi ý cá nhân → tool PostgreSQL theo token;
- bệnh lý/thuốc → `out_of_scope`.

Ví dụ request:

```json
{
  "message": "Phở bò bao nhiêu calo?",
  "history": [],
  "timezone": "Asia/Ho_Chi_Minh"
}
```

Client phải đọc các event SSE theo thứ tự:

- `meta`: route planner chọn và nguồn ban đầu;
- `delta`: nối `text` vào câu trả lời đang hiển thị;
- `sources`: thay danh sách citation khi stream kết thúc;
- `done`: đóng trạng thái đang trả lời;
- `error`: hiển thị lỗi thân thiện, không lộ lỗi server.

Đây là "agentic" ở mức có kiểm soát: planner được chọn tối đa 3 tool trong
allowlist. Chưa dùng LangGraph vì workflow hiện tại chỉ là một plan tuyến tính,
đọc và kiểm tra được bằng Python thường.
