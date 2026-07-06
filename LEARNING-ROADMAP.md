# Lộ Trình Học + Build RAG Chat Bot Tra Cứu Văn Bản Pháp Luật (4 Tuần)

> **Trình độ hiện tại**: Mới bắt đầu Python  
> **Mục tiêu**: Hiểu sâu RAG + có project chất lượng để show portfolio xin việc công ty AI (luật + y tế)  
> **Chủ đề**: Tra cứu văn bản pháp luật Việt Nam — chatbot trả lời câu hỏi pháp lý kèm trích dẫn điều khoản chính xác  
> **Thời gian**: 4 tuần full-time  
> **UI**: Streamlit (Python-native, không cần JavaScript/React)

---

## Tại sao chọn chủ đề "Tra cứu văn bản pháp luật"?

| Yếu tố | Lý do |
|--------|-------|
| **Đúng domain công ty** | Công ty AI làm về luật + y tế → thể hiện hiểu đặc thù dữ liệu ngành |
| **Dữ liệu thật, công khai** | Văn bản pháp luật VN có sẵn, miễn phí (thuvienphapluat.vn, vbpl.vn, CSDL quốc gia) |
| **Bài toán thực tế** | Luật sư, doanh nghiệp mất hàng giờ tra cứu — một hệ thống RAG chính xác giải quyết đúng vấn đề này |
| **Đặc thù kỹ thuật thú vị** | Versioning (luật hết hiệu lực), cross-reference (văn bản dẫn chiếu lẫn nhau), citation chính xác đến điều/khoản/điểm |
| **Dễ demo** | Hỏi về luật doanh nghiệp, đầu tư, lao động → câu hỏi cụ thể, câu trả lời kiểm chứng được |

---

## Triết lý học

- **Build để học, không học để build** — mỗi ngày code ra thứ chạy được
- **Sâu > Rộng** — 1 RAG pipeline đúng + có test + đo lường được > 10 tính năng nửa vời
- **Code trước, đọc sau** — xem ý tưởng → code → gặp lỗi → đọc doc sửa
- **Testing không phải việc cuối cùng** — viết test mỗi ngày, không dồn vào ngày chót
- **Commit mỗi ngày** — message tiếng Việt rõ ràng
- **Chất lượng dữ liệu > Mô hình xịn** — document processing đúng quyết định 80% chất lượng RAG

---

## Tech Stack Cuối Cùng

| Layer | Chọn gì | Tại sao |
|-------|---------|---------|
| Backend API | FastAPI | Async, auto-docs, type-safe, industry standard |
| RAG framework | **Không dùng LangChain** | Tự code để hiểu sâu từng bước |
| LLM Server | **llama.cpp** | OpenAI-compatible API, tận dụng tối đa GPU Mac Metal, không bóp hiệu năng như Ollama |
| LLM Model | **Qwen2.5 7B** (GGUF) | Hỗ trợ tiếng Việt vượt trội, Apache 2.0 |
| Embedding Server | **llama.cpp** (server mode, `/v1/embeddings`) | Cùng 1 server cho cả LLM + Embedding, chuẩn OpenAI API |
| Embedding Model | **Qwen3-Embedding 0.6B** (GGUF) | Multilingual, hỗ trợ tiếng Việt tốt, 1024d, Apache 2.0 |
| Vector DB | Qdrant (Docker) | Self-hosted, production-grade |
| Database | PostgreSQL (có thể dùng pgvector nếu muốn gộp) | Chat history, document metadata, version tracking |
| Package Manager | **uv** (thay pip) | Tốc độ gấp 10-100x, quản lý Python version, lock file chuẩn |
| UI | **Streamlit** | Python-native, 30 dòng là có chat UI |
| Deployment | Docker Compose | 1 lệnh `docker compose up` |
| Evaluation | RAGAS | Đo lường chất lượng retrieval |

> **Khác với roadmap cũ**: Chuyển từ Ollama → llama.cpp (hiệu năng cao hơn, chuẩn OpenAI API), từ Llama 3.1 → Qwen2.5 (tiếng Việt tốt hơn), từ sentence-transformers → llama.cpp serve embedding Qwen3-Embedding, từ pip → uv (nhanh hơn).

---

## Project Structure

```
Chat-bot-RAG/
├── models/                          # GGUF model files (gitignored)
│   ├── qwen2.5-7b-instruct-q4_k_m.gguf
│   └── qwen3-embedding-0.6b-q4_k_m.gguf
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app
│   ├── config.py                   # Settings từ biến môi trường
│   ├── api/
│   │   ├── __init__.py
│   │   ├── chat.py                 # Chat endpoints (SSE streaming)
│   │   ├── documents.py            # Upload, list, delete legal documents
│   │   └── legal.py                # Legal-specific search + analysis endpoints
│   ├── services/
│   │   ├── embedding.py            # Gọi llama.cpp /v1/embeddings
│   │   ├── llm.py                  # Gọi llama.cpp /v1/chat/completions (OpenAI-compatible)
│   │   ├── rag.py                  # Core RAG pipeline (citation-aware)
│   │   ├── document.py             # Parse, chunk, index legal docs
│   │   ├── legal.py                # Legal NLP: article extraction, cross-ref, version check
│   │   └── citation.py             # Citation parsing & validation
│   ├── db/
│   │   ├── postgres.py             # SQLAlchemy async session
│   │   ├── qdrant.py               # Qdrant client
│   │   └── models.py               # SQLAlchemy ORM models
│   ├── prompts/                    # Prompt templates (version controlled)
│   │   ├── legal_assistant.py      # Prompt chính: trợ lý pháp lý
│   │   ├── article_extraction.py   # Prompt trích xuất điều khoản
│   │   └── cross_reference.py      # Prompt phát hiện dẫn chiếu
│   ├── evaluation/
│   │   └── ragas_eval.py           # RAGAS evaluation
│   └── schemas/
│       ├── chat.py                 # Pydantic request/response
│       ├── document.py
│       └── legal.py                # Legal-specific schemas
├── streamlit_app/                  # Streamlit UI (Python)
│   ├── Home.py                     # Trang chính
│   ├── pages/
│   │   ├── 1_Chat.py               # RAG Chat — hỏi đáp pháp luật
│   │   ├── 2_Documents.py          # Quản lý văn bản luật
│   │   └── 3_Legal_Search.py       # Tra cứu nâng cao (theo điều, theo luật, cross-ref)
│   └── utils.py                    # API client helpers
├── data/                           # Dữ liệu mẫu (văn bản luật VN)
│   ├── luat-doanh-nghiep-2020.txt
│   ├── luat-dau-tu-2020.txt
│   └── README.md                   # Nguồn dữ liệu, cách crawl thêm
├── tests/
│   ├── conftest.py                 # Fixtures (TestClient, mock services)
│   ├── test_embedding.py
│   ├── test_rag.py
│   ├── test_api_chat.py
│   ├── test_api_documents.py
│   ├── test_legal.py
│   ├── test_citation.py
│   ├── test_edge_cases.py
│   └── test_auth.py
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── evaluation/                     # Kết quả đánh giá
    └── ragas_results.json
```

---

## Tuần 1: Python + Nền Tảng Web + Dữ Liệu

### Ngày 1: Python + uv + Môi Trường Cơ Bản

**Học:**
- Python virtual environment: `venv` là gì, tại sao cần?
- `uv` là gì? Tại sao nhanh hơn pip?
  - `uv` = package manager viết bằng Rust, thay thế pip + venv + pyenv
  - Tốc độ resolve dependency nhanh gấp 10-100x
  - Tự động tạo lock file `uv.lock` (như npm/pnpm)
  - Quản lý được cả phiên bản Python (như pyenv)
- Git: `init`, `add`, `commit`, `.gitignore`
- Câu lệnh terminal cơ bản: `cd`, `ls`, `mkdir`, `rm`, `cat`

**Làm:**
- [ ] Cài Python 3.12 (từ python.org hoặc `brew install python@3.12`)
- [ ] Cài `uv`: 
  - Mac: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Hoặc: `brew install uv`
- [ ] Tạo thư mục dự án `Chat-bot-RAG/`
- [ ] `uv venv --python 3.12` → tạo virtual environment
- [ ] `source venv/bin/activate` → kích hoạt (giống pip)
- [ ] Viết script Python đầu tiên: `hello.py` in ra "Hello RAG!"
- [ ] `git init`, tạo `.gitignore`:
  ```
  venv/
  __pycache__/
  .env
  .DS_Store
  *.pyc
  ```
- [ ] Commit đầu tiên: "khởi tạo dự án RAG tra cứu văn bản pháp luật"

**Check hiểu:**
- Tại sao không cài package global mà phải dùng venv?
- Tại sao chọn `uv` thay vì `pip`?
- `.gitignore` để làm gì?

**File tạo:**
```
.gitignore
requirements.txt  (chỉ có fastapi và uvicorn)
```

---

### Ngày 2: Docker Cơ Bản

**Học:**
- Docker là gì? Container khác gì máy ảo?
- Image vs Container
- Docker Hub là gì?
- `docker run`, `docker ps`, `docker stop`
- Docker Compose: `docker compose up`, `docker compose down`
- Volume (lưu dữ liệu), port mapping

**Làm:**
- [ ] Cài Docker Desktop (từ docker.com)
  - Mac Apple Silicon: chọn chip Apple
  - Xác nhận chạy được: `docker run hello-world`
- [ ] Kéo image PostgreSQL: `docker run --name test-postgres -e POSTGRES_PASSWORD=test -p 5432:5432 -d postgres:16`
- [ ] Kiểm tra: `docker ps` → thấy container đang chạy
- [ ] Dừng & xóa: `docker stop test-postgres && docker rm test-postgres`
- [ ] Tạo `docker-compose.yml` đầu tiên chỉ với PostgreSQL:
  ```yaml
  services:
    postgres:
      image: postgres:16
      environment:
        POSTGRES_USER: raguser
        POSTGRES_PASSWORD: ragpass
        POSTGRES_DB: ragdb
      ports:
        - "5432:5432"
      volumes:
        - postgres_data:/var/lib/postgresql/data
  volumes:
    postgres_data:
  ```
- [ ] `docker compose up -d` → kiểm tra
- [ ] `docker compose down` → dọn dẹp

**Check hiểu:**
- Docker Compose khác gì `docker run` thủ công?
- Volume để làm gì? Nếu không có volume thì sao?
- Port mapping `5432:5432` nghĩa là gì?

**File tạo:**
```
docker-compose.yml  (chỉ có postgres)
```

---

### Ngày 3: FastAPI Cơ Bản

**Học:**
- FastAPI là gì? Tại sao async? Khác Flask/Django ở đâu?
- HTTP: GET, POST, PUT, DELETE
- Request: path parameter (`/users/{id}`), query parameter (`?q=...`), request body (JSON)
- Pydantic: `BaseModel` để validate request/response
- Swagger UI: auto-generated API docs
- Test API với `httpx` hoặc `TestClient`

**Làm:**
- [ ] Cài FastAPI: `pip install fastapi uvicorn[standard]`
- [ ] `app/__init__.py`
- [ ] `app/config.py` — dùng Pydantic `BaseSettings`:
  ```python
  from pydantic_settings import BaseSettings

  class Settings(BaseSettings):
      app_name: str = "RAG Legal Assistant"
      app_version: str = "0.1.0"
      llama_cpp_llm_url: str = "http://localhost:8080"      # llama.cpp LLM server
      llama_cpp_embed_url: str = "http://localhost:8081"    # llama.cpp Embedding server
      qdrant_url: str = "http://localhost:6333"
      database_url: str = "postgresql+asyncpg://raguser:ragpass@localhost:5432/ragdb"

      class Config:
          env_file = ".env"

  settings = Settings()
  ```
- [ ] `app/main.py`:
  ```python
  from fastapi import FastAPI
  from app.config import settings

  app = FastAPI(title=settings.app_name, version=settings.app_version)

  @app.get("/health")
  async def health():
      return {"status": "ok", "version": settings.app_version}
  ```
- [ ] `app/schemas/chat.py` — Pydantic models:
  ```python
  from pydantic import BaseModel

  class MessageRequest(BaseModel):
      content: str

  class MessageResponse(BaseModel):
      content: str
      role: str = "assistant"
      citations: list[dict] = []  # [{law_name, article, content_snippet}]
  ```
- [ ] Chạy server: `uvicorn app.main:app --reload`
- [ ] Vào `http://localhost:8000/docs` → xem Swagger UI
- [ ] Viết test đầu tiên: `tests/test_api_health.py`
  ```python
  from fastapi.testclient import TestClient
  from app.main import app

  client = TestClient(app)

  def test_health():
      response = client.get("/health")
      assert response.status_code == 200
      assert response.json()["status"] == "ok"
  ```
- [ ] Chạy test: `pytest tests/test_api_health.py -v`

**Check hiểu:**
- `uvicorn` làm gì?
- `--reload` để làm gì?
- Swagger UI từ đâu ra mà không cần viết?

**File tạo:**
```
app/__init__.py
app/main.py
app/config.py
app/schemas/__init__.py
app/schemas/chat.py
tests/conftest.py
tests/test_api_health.py
```

---

### Ngày 4: Async/Await + SSE Cơ Bản

**Học:**
- Synchronous vs Asynchronous: khác nhau ở đâu?
- Event loop là gì? (high level)
- `async def`, `await`, `async for`, `AsyncGenerator`
- Tại sao FastAPI dùng async?
- SSE (Server-Sent Events) là gì? Khác WebSocket ở đâu?
- Streaming response trong FastAPI: `StreamingResponse`

**Làm:**
- [ ] Viết script async cơ bản để hiểu:
  ```python
  import asyncio

  async def nấu_cơm():
      print("Bắt đầu nấu cơm...")
      await asyncio.sleep(2)  # giả lập I/O
      print("Cơm chín!")
      return "cơm"

  async def kho_thịt():
      print("Bắt đầu kho thịt...")
      await asyncio.sleep(3)
      print("Thịt kho xong!")
      return "thịt"

  async def main():
      # Chạy đồng thời
      results = await asyncio.gather(nấu_cơm(), kho_thịt())
      print(f"Bữa ăn có: {results}")

  asyncio.run(main())
  ```
- [ ] Thêm endpoint SSE demo vào `app/main.py`:
  ```python
  import asyncio
  from fastapi.responses import StreamingResponse

  @app.get("/api/v1/stream-demo")
  async def stream_demo():
      async def generate():
          for i in range(10):
              yield f"data: Token {i}\n\n"
              await asyncio.sleep(0.5)
      return StreamingResponse(generate(), media_type="text/event-stream")
  ```
- [ ] `app/api/__init__.py`
- [ ] Tạo `app/api/chat.py` với endpoint echo streaming:
  ```python
  import asyncio
  from fastapi import APIRouter
  from fastapi.responses import StreamingResponse
  from app.schemas.chat import MessageRequest

  router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

  @router.post("/echo-stream")
  async def echo_stream(request: MessageRequest):
      async def generate():
          for word in request.content.split():
              yield f"data: {word}\n\n"
              await asyncio.sleep(0.3)
          yield "data: [DONE]\n\n"
      return StreamingResponse(generate(), media_type="text/event-stream")
  ```
- [ ] Đăng ký router trong `main.py`
- [ ] Test bằng curl: `curl -X POST http://localhost:8000/api/v1/chat/echo-stream -H "Content-Type: application/json" -d '{"content": "Xin chào bạn nhé"}'`

**Check hiểu:**
- `await asyncio.sleep(2)` khác gì `time.sleep(2)`?
- Tại sao phải dùng async cho LLM streaming?
- SSE dùng cho use case gì? Khi nào nên dùng WebSocket thay SSE?

**File tạo:**
```
app/api/__init__.py
app/api/chat.py  (echo streaming)
```

---

### Ngày 5: llama.cpp Server + Embedding — Trái Tim Của RAG

**Học:**
- Embedding là gì? (text → vector số)
- Tại sao embedding tốt hơn keyword search?
- Semantic similarity vs Lexical similarity
- **llama.cpp server mode**: serve model qua HTTP, chuẩn OpenAI-compatible API
  - Endpoint `/v1/embeddings` — chuẩn OpenAI
  - Dùng GPU Mac Metal (không bị Docker chặn GPU như Ollama)

> **QUAN TRỌNG**: Tiếng Việt trong văn bản luật có từ Hán-Việt, câu phức, thuật ngữ đặc thù. Chọn **Qwen3-Embedding 0.6B** vì hỗ trợ multilingual vượt trội (gồm tiếng Việt), 1024 chiều, Apache 2.0 license.

- Qwen3-Embedding 0.6B GGUF → 1024 chiều, đa ngôn ngữ
- Cosine similarity: công thức, ý nghĩa (góc giữa 2 vector)

**Làm:**
- [ ] Cài llama.cpp (macOS):
  ```bash
  brew install llama.cpp
  ```
- [ ] Tải model GGUF:
  ```bash
  # Tạo thư mục models
  mkdir -p models
  # Tải embedding model (file GGUF ~0.6GB)
  # Link tham khảo: huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF
  ```
- [ ] Khởi động llama.cpp server cho embedding:
  ```bash
  llama-server \
    -m models/qwen3-embedding-0.6b.Q4_K_M.gguf \
    --embeddings \
    --port 8080 \
    -ngl 99
  ```
  - `--embeddings`: bật chế độ embedding
  - `-ngl 99`: offload 99 layer lên GPU Metal
- [ ] Test embedding API:
  ```bash
  curl http://localhost:8080/v1/embeddings \
    -H "Content-Type: application/json" \
    -d '{"input": "Công ty TNHH hai thành viên", "model": "qwen3-embedding"}'
  ```
- [ ] `app/services/__init__.py`
- [ ] `app/services/embedding.py` (gọi llama.cpp API, chuẩn OpenAI):
  ```python
  import httpx
  import numpy as np
  from app.config import settings

  class EmbeddingService:
      def __init__(self, base_url: str = None):
          self.base_url = base_url or settings.llama_cpp_url  # "http://localhost:8080"
          self.model = "qwen3-embedding"

      async def embed(self, text: str) -> list[float]:
          """Gọi llama.cpp /v1/embeddings"""
          async with httpx.AsyncClient(timeout=30) as client:
              resp = await client.post(
                  f"{self.base_url}/v1/embeddings",
                  json={"input": text, "model": self.model},
              )
              return resp.json()["data"][0]["embedding"]  # 1024 chiều

      async def embed_batch(self, texts: list[str]) -> list[list[float]]:
          async with httpx.AsyncClient(timeout=60) as client:
              resp = await client.post(
                  f"{self.base_url}/v1/embeddings",
                  json={"input": texts, "model": self.model},
              )
              return [item["embedding"] for item in resp.json()["data"]]

      @staticmethod
      def similarity(vec1: list[float], vec2: list[float]) -> float:
          v1, v2 = np.array(vec1), np.array(vec2)
          return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
  ```
- [ ] Script test thủ công với tiếng Việt:
  ```python
  import asyncio
  svc = EmbeddingService()
  v1 = asyncio.run(svc.embed("Công ty TNHH hai thành viên phải có Hội đồng thành viên"))
  v2 = asyncio.run(svc.embed("Hội đồng thành viên là cơ quan quyết định cao nhất"))
  v3 = asyncio.run(svc.embed("Hôm nay trời đẹp quá"))
  print(f"v1 vs v2: {EmbeddingService.similarity(v1, v2):.3f}")  # ~0.8
  print(f"v1 vs v3: {EmbeddingService.similarity(v1, v3):.3f}")  # ~0.2
  ```
- [ ] `tests/test_embedding.py`:
  - Test `embed()` trả về 1024 chiều
  - Test `similarity()` trong khoảng [0, 1]
  - Test: 2 điều luật cùng chủ đề có similarity > 0.7

**Check hiểu:**
- Tại sao serve embedding qua llama.cpp thay vì load trong Python?
- 1024 chiều khác gì 384 chiều?Đánh đổi là gì?
- `/v1/embeddings` theo chuẩn nào? Tại sao cần chuẩn đó?
- Embedding có hiểu được thuật ngữ pháp lý tiếng Việt không? (có, nhưng cần test)

**File tạo:**
```
app/services/__init__.py
app/services/embedding.py
tests/test_embedding.py
```

---

### Ngày 6: Vector Database Qdrant

**Học:**
- Vector database là gì? Khác PostgreSQL ở chỗ nào?
- Qdrant: collection, point, vector, payload
- HNSW index (high level): đồ thị phân lớp để tìm gần đúng
- ANN (Approximate Nearest Neighbor) vs exact search
- Distance metrics: cosine, euclidean, dot
- **Payload strategy cho luật**: lưu `law_name`, `article_number`, `chapter`, `effective_date`, `expiry_date` trong payload để lọc theo metadata

**Làm:**
- [ ] Thêm Qdrant vào `docker-compose.yml`:
  ```yaml
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
  ```
- [ ] Cài `qdrant-client`
- [ ] `app/db/__init__.py`
- [ ] `app/db/qdrant.py`:
  ```python
  from qdrant_client import QdrantClient
  from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
  from app.config import settings

  def get_qdrant_client() -> QdrantClient:
      return QdrantClient(url=settings.qdrant_url)

  def create_collection(client: QdrantClient, name: str, vector_size: int = 384):
      client.create_collection(
          collection_name=name,
          vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
      )

  def upsert_points(client, collection: str, ids: list, vectors: list, payloads: list):
      points = [
          PointStruct(id=id_, vector=vec, payload=pl)
          for id_, vec, pl in zip(ids, vectors, payloads)
      ]
      client.upsert(collection_name=collection, points=points)

  def search(
      client, collection: str, query_vector: list,
      top_k: int = 5, law_name: str = None
  ):
      """Search với optional filter theo tên luật"""
      query_filter = None
      if law_name:
          query_filter = Filter(
              must=[FieldCondition(key="law_name", match=MatchValue(value=law_name))]
          )
      results = client.search(
          collection_name=collection,
          query_vector=query_vector,
          limit=top_k,
          query_filter=query_filter,
      )
      return [{"id": r.id, "score": r.score, "payload": r.payload} for r in results]

  def delete_by_law(client, collection: str, law_name: str):
      """Xóa tất cả chunk của 1 bộ luật (để re-index khi luật cập nhật)"""
      client.delete(
          collection_name=collection,
          points_selector=Filter(
              must=[FieldCondition(key="law_name", match=MatchValue(value=law_name))]
          ),
      )
  ```
- [ ] Script seed: embed 10 điều luật mẫu, insert vào Qdrant, search thử
- [ ] `tests/test_qdrant.py` — test CRUD collection + search + filter by law_name

**Check hiểu:**
- Payload để làm gì? Tại sao cần lưu `article_number` và `effective_date`?
- Tại sao cần hàm `delete_by_law`? Liên quan gì đến versioning?
- Distance COSINE vs EUCLID khác nhau thế nào?

**File tạo:**
```
app/db/__init__.py
app/db/qdrant.py
tests/test_qdrant.py
```

---

### Ngày 7: Document Processing Cho Văn Bản Luật

**Học:**
- Chunking là gì? Tại sao không embed cả bộ luật 300 điều?
- **Chiến lược chunk cho văn bản luật**:
  - Semantic chunking: tách theo Điều (article-boundary) — **ưu tiên**
  - Fixed-size fallback: 500 chars với overlap 100
  - KHÔNG cắt ngang giữa 1 điều luật
- Parse PDF (`pypdf`), DOCX (`python-docx`), TXT file
- **Metadata strategy cho luật**:
  - `law_name` (tên luật: "Luật Doanh Nghiệp 2020")
  - `article_number` (số điều)
  - `chapter` (chương)
  - `effective_date` (ngày hiệu lực)
  - `document_type` (luật / nghị định / thông tư)

**Làm:**
- [ ] Tạo `data/` folder, tải 2-3 văn bản luật mẫu:
  - Luật Doanh Nghiệp 2020 (file .txt từ thuvienphapluat.vn)
  - Luật Đầu Tư 2020
  - Luật Lao Động 2019 (1 phần)
- [ ] Cài `pypdf`, `python-docx`
- [ ] `app/services/document.py`:
  ```python
  import re
  from pypdf import PdfReader
  from docx import Document as DocxDocument

  def parse_pdf(file_path: str) -> str:
      reader = PdfReader(file_path)
      return "\n".join(page.extract_text() for page in reader.pages if page.extract_text())

  def parse_docx(file_path: str) -> str:
      doc = DocxDocument(file_path)
      return "\n".join(p.text for p in doc.paragraphs if p.text)

  def parse_txt(file_path: str) -> str:
      with open(file_path, "r", encoding="utf-8") as f:
          return f.read()

  def chunk_by_article(text: str, law_name: str) -> list[dict]:
      """Tách văn bản luật theo từng Điều. Fallback: fixed-size nếu không parse được."""
      # Pattern: "Điều X." hoặc "Điều X:" — format chuẩn văn bản luật VN
      articles = re.split(r'\n(?=Điều\s+\d+\.)', text)
      chunks = []
      for idx, article_text in enumerate(articles):
          article_text = article_text.strip()
          if not article_text:
              continue
          # Trích số điều
          article_match = re.match(r'Điều\s+(\d+)', article_text)
          article_num = article_match.group(1) if article_match else None

          # Nếu 1 điều quá dài (>1000 chars), cắt thêm sub-chunks
          if len(article_text) > 1000:
              sub_chunks = chunk_text(article_text, chunk_size=800, overlap=100)
              for sub in sub_chunks:
                  sub["article_number"] = article_num
                  sub["law_name"] = law_name
                  chunks.append(sub)
          else:
              chunks.append({
                  "text": article_text,
                  "article_number": article_num,
                  "law_name": law_name,
                  "chunk_index": idx,
              })
      return chunks

  def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
      """Fallback chunker cho văn bản không theo format Điều"""
      chunks = []
      start = 0
      idx = 0
      while start < len(text):
          end = min(start + chunk_size, len(text))
          chunk = text[start:end]
          chunks.append({
              "text": chunk,
              "chunk_index": idx,
              "start_char": start,
              "end_char": end,
          })
          start = end - overlap
          idx += 1
      return chunks
  ```
- [ ] `app/schemas/document.py`:
  ```python
  from pydantic import BaseModel

  class DocumentResponse(BaseModel):
      id: str
      filename: str
      law_name: str
      article_count: int
      chunk_count: int
      status: str  # "indexing", "done", "error"

  class DocumentListResponse(BaseModel):
      documents: list[DocumentResponse]
  ```
- [ ] `app/api/documents.py`:
  - `POST /api/v1/documents/upload` (multipart upload, tự detect law_name)
  - `GET /api/v1/documents` (list, filter theo law_name)
  - `DELETE /api/v1/documents/{law_name}` (xóa toàn bộ 1 bộ luật)
- [ ] `tests/test_document_service.py` — test chunk_by_article với văn bản luật thật

**Check hiểu:**
- Tại sao chunk theo điều luật tốt hơn fixed-size cho văn bản luật?
- Nếu 1 điều có 5 khoản dài, chunk strategy nên thế nào?
- Metadata nào là quan trọng nhất để citation? (law_name + article_number + text)

**File tạo:**
```
data/luat-doanh-nghiep-2020.txt
data/luat-dau-tu-2020.txt
data/README.md
app/services/document.py
app/schemas/document.py
app/api/documents.py
tests/test_document_service.py
```

---

## Tuần 2: LLM + RAG Pipeline + Database

### Ngày 8: LLM với llama.cpp + Qwen2.5

**Học:**
- LLM là gì? Token → next token prediction (high level)
- llama.cpp: engine inference C++ tối ưu cho Mac Metal, hỗ trợ OpenAI-compatible API
- GGUF format: định dạng model đã quantize (nén) để chạy trên consumer hardware
- Prompt structure: system + context + user
- Temperature, top_p, max_tokens
- Tại sao LLM hallucinate? Đặc biệt nguy hiểm với văn bản luật

> **Tại sao llama.cpp thay vì Ollama?**
> - llama.cpp server có `/v1/chat/completions` chuẩn OpenAI API
> - Tận dụng tối đa GPU Metal, không bị overhead như Ollama
> - Dùng chung 1 server cho cả LLM + Embedding (Ngày 5)
> - Cấu hình chi tiết hơn: context size, GPU layers, batch size

**Làm:**
- [ ] Đã cài llama.cpp từ Ngày 5
- [ ] Tải model Qwen2.5 7B GGUF:
  ```bash
  # Từ HuggingFace, chọn bản Q4_K_M (~4.7GB) — cân bằng tốc độ/chất lượng
  # Link: huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF
  ```
- [ ] Khởi động llama.cpp server cho LLM:
  ```bash
  llama-server \
    -m models/qwen2.5-7b-instruct-q4_k_m.gguf \
    --port 8080 \
    -ngl 99 \
    -c 8192
  ```
  - `-ngl 99`: offload lên GPU Metal
  - `-c 8192`: context window 8K tokens
  - **Lưu ý**: Server này chạy trên port 8080, embedding server (Ngày 5) phải chạy port khác (ví dụ 8081). Hoặc chạy 1 server hỗ trợ cả 2 (với `--embeddings` flag nếu model hỗ trợ).
  - **Phương án khác**: 1 script launch 2 llama-server instance: 1 cho LLM (:8080), 1 cho Embedding (:8081)
- [ ] Test tiếng Việt:
  ```bash
  curl http://localhost:8080/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{
      "model": "qwen2.5-7b",
      "messages": [
        {"role": "system", "content": "Bạn là trợ lý pháp lý Việt Nam."},
        {"role": "user", "content": "Công ty TNHH có mấy loại?"}
      ],
      "temperature": 0.3
    }'
  ```
- [ ] `app/services/llm.py` (OpenAI-compatible API):
  ```python
  import httpx
  import json
  from app.config import settings

  class LLMService:
      def __init__(self, model: str = "qwen2.5-7b"):
          self.model = model
          self.base_url = settings.llama_cpp_url  # "http://localhost:8080"

      async def generate(self, prompt: str, system: str = "", temperature: float = 0.3) -> str:
          messages = []
          if system:
              messages.append({"role": "system", "content": system})
          messages.append({"role": "user", "content": prompt})
          async with httpx.AsyncClient(timeout=120) as client:
              resp = await client.post(
                  f"{self.base_url}/v1/chat/completions",
                  json={
                      "model": self.model,
                      "messages": messages,
                      "temperature": temperature,
                      "stream": False,
                  },
              )
              return resp.json()["choices"][0]["message"]["content"]

      async def generate_stream(self, prompt: str, system: str = "", temperature: float = 0.3):
          messages = []
          if system:
              messages.append({"role": "system", "content": system})
          messages.append({"role": "user", "content": prompt})
          async with httpx.AsyncClient(timeout=120) as client:
              async with client.stream(
                  "POST", f"{self.base_url}/v1/chat/completions",
                  json={
                      "model": self.model,
                      "messages": messages,
                      "temperature": temperature,
                      "stream": True,
                  },
              ) as resp:
                  async for line in resp.aiter_lines():
                      if line.startswith("data: "):
                          chunk = json.loads(line[6:])
                          delta = chunk.get("choices", [{}])[0].get("delta", {})
                          if "content" in delta:
                              yield delta["content"]
  ```
- [ ] `tests/test_llm.py` — mock llama.cpp API, test generate + stream

**Check hiểu:**
- Temperature = 0.0 khác gì temperature = 1.0? Với luật nên dùng temperature thấp hay cao?
- Tại sao LLM hallucinate? Với văn bản luật, hậu quả là gì?
- Streaming vs non-streaming: người dùng thấy gì khác?
- `/v1/chat/completions` là chuẩn của ai? Tại sao nên theo chuẩn này?

**File tạo:**
```
app/services/llm.py
tests/test_llm.py
```

---

### Ngày 9: RAG Pipeline — Mọi Thứ Kết Hợp

**Học:**
- Full RAG flow: Query → Embed → Retrieve → Augment → Generate → Cite
- Prompt template cho trợ lý pháp lý: system role + context + question + yêu cầu citation
- **Citation là bắt buộc**: không được phép trả lời mà không trích dẫn điều luật
- Prompt buộc LLM từ chối: "Nếu ngữ cảnh không đủ, phải nói 'Tôi không tìm thấy điều luật nào quy định về vấn đề này'"
- Top-K retrieval: K = ?

**Làm:**
- [ ] `app/prompts/__init__.py`
- [ ] `app/prompts/legal_assistant.py`:
  ```python
  SYSTEM_PROMPT = """Bạn là trợ lý pháp lý chuyên tra cứu văn bản pháp luật Việt Nam. Nhiệm vụ của bạn:

  1. CHỈ trả lời DỰA TRÊN ngữ cảnh văn bản luật được cung cấp bên dưới.
  2. Nếu ngữ cảnh không đủ để trả lời chính xác, phải nói rõ:
     "Tôi không tìm thấy điều luật nào quy định cụ thể về vấn đề này trong các văn bản hiện có."
  3. MỖI câu trả lời PHẢI kèm trích dẫn: tên luật, số điều, khoản (nếu có).
  4. Trích dẫn format: [Luật Doanh Nghiệp 2020, Điều X, Khoản Y]
  5. Trả lời bằng tiếng Việt, ngắn gọn, chính xác, dễ hiểu cho người không chuyên luật.
  6. TUYỆT ĐỐI không tự bịa ra điều luật không có trong ngữ cảnh."""

  def build_prompt(context: str, question: str) -> str:
      return f"""{SYSTEM_PROMPT}

  ## Văn bản pháp luật liên quan:
  {context}

  ## Câu hỏi:
  {question}

  ## Trả lời (kèm trích dẫn điều luật):"""
  ```
- [ ] `app/services/rag.py`:
  ```python
  from app.services.embedding import EmbeddingService
  from app.services.llm import LLMService
  from app.db.qdrant import get_qdrant_client, search
  from app.prompts.legal_assistant import build_prompt

  class RAGService:
      def __init__(self):
          self.embedding = EmbeddingService()
          self.llm = LLMService()
          self.qdrant = get_qdrant_client()

      async def query(
          self, question: str, collection: str = "legal_docs",
          top_k: int = 5, law_name: str = None
      ) -> dict:
          # 1. Embed câu hỏi
          query_vec = self.embedding.embed(question)
          # 2. Retrieve (có filter theo luật nếu người dùng chọn)
          results = search(self.qdrant, collection, query_vec, top_k=top_k, law_name=law_name)
          # 3. Build context với metadata đầy đủ
          context_parts = []
          for r in results:
              p = r["payload"]
              article = f"Điều {p.get('article_number')}" if p.get("article_number") else ""
              context_parts.append(
                  f"[{p.get('law_name', 'Không rõ')}, {article}]\n{p['text']}"
              )
          context = "\n\n---\n\n".join(context_parts)
          # 4. Generate
          prompt = build_prompt(context, question)
          answer = await self.llm.generate(prompt)
          # 5. Return with sources
          return {
              "answer": answer,
              "sources": [
                  {
                      "law_name": r["payload"].get("law_name"),
                      "article_number": r["payload"].get("article_number"),
                      "text_preview": r["payload"]["text"][:300],
                      "score": round(r["score"], 3),
                  }
                  for r in results
              ],
          }

      async def query_stream(
          self, question: str, collection: str = "legal_docs",
          top_k: int = 5, law_name: str = None
      ):
          query_vec = self.embedding.embed(question)
          results = search(self.qdrant, collection, query_vec, top_k=top_k, law_name=law_name)
          context_parts = []
          for r in results:
              p = r["payload"]
              article = f"Điều {p.get('article_number')}" if p.get("article_number") else ""
              context_parts.append(f"[{p.get('law_name', 'Không rõ')}, {article}]\n{p['text']}")
          context = "\n\n---\n\n".join(context_parts)
          prompt = build_prompt(context, question)
          async for token in self.llm.generate_stream(prompt):
              yield token
  ```
- [ ] Cập nhật `app/api/chat.py`: thay echo bằng RAG query thật
- [ ] Test end-to-end: upload Luật Doanh Nghiệp → hỏi "Công ty TNHH 1 thành viên là gì?"

**Check hiểu:**
- Tại sao prompt bắt LLM nói "tôi không biết" nếu thiếu context? Điều này quan trọng thế nào với luật?
- Tại sao phải kèm citation? Người dùng luật cần gì ở citation?
- Top-k=5: điều gì xảy ra nếu chọn k=1? k=20?

**File tạo:**
```
app/prompts/__init__.py
app/prompts/legal_assistant.py
app/services/rag.py
```

---

### Ngày 10: PostgreSQL + Chat History + Document Metadata

**Học:**
- SQLAlchemy async (2.0 style)
- ORM models vs raw SQL
- Alembic: migration là gì, tại sao cần?
- JSONB trong PostgreSQL
- FastAPI dependency injection cho database session

**Làm:**
- [ ] Cài `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
- [ ] `app/db/postgres.py`:
  ```python
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
  from app.config import settings

  engine = create_async_engine(settings.database_url, echo=False)
  async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

  async def get_db() -> AsyncSession:
      async with async_session() as session:
          try:
              yield session
              await session.commit()
          except Exception:
              await session.rollback()
              raise
  ```
- [ ] `app/db/models.py` — ORM models:
  - `ChatSession(id, title, created_at, updated_at)`
  - `ChatMessage(id, session_id FK, role, content, citations JSONB, created_at)`
  - `LegalDocument(id, law_name, file_name, article_count, chunk_count, version_date, effective_date, status, created_at)`
  - `ArticleReference(id, source_law, source_article, target_law, target_article, reference_type)` (cho cross-reference)
- [ ] `alembic init alembic`
- [ ] Sửa `alembic.ini` → trỏ đến database_url
- [ ] Sửa `alembic/env.py` → dùng async engine
- [ ] `alembic revision --autogenerate -m "init"` → tạo migration đầu tiên
- [ ] `alembic upgrade head` → chạy migration
- [ ] Cập nhật Chat API: lưu message vào DB, load history

**Check hiểu:**
- Tại sao cần migration thay vì CREATE TABLE trực tiếp?
- JSONB vs TEXT: khi nào dùng cái nào? (citations nên để JSONB)
- Bảng `ArticleReference` để làm gì?

**File tạo:**
```
app/db/postgres.py
app/db/models.py
alembic/ + alembic.ini
```

---

### Ngày 11: Đánh Giá Chất Lượng RAG với RAGAS

**Học:**
- Không evaluate = không biết mình đang build thứ gì. **Với luật, đánh giá còn quan trọng hơn vì sai 1 điều = hậu quả pháp lý.**
- 4 metric quan trọng:
  - **Context Precision**: chunks lấy về có liên quan đến câu hỏi pháp lý không?
  - **Context Recall**: có bỏ sót điều luật quan trọng không?
  - **Faithfulness**: câu trả lời có đúng với điều luật được cung cấp không? (quan trọng nhất với luật)
  - **Answer Relevancy**: câu trả lời có trả lời đúng câu hỏi pháp lý không?
- **Legal-specific metric**: Citation Accuracy (% câu trả lời trích dẫn đúng điều luật)

**Làm:**
- [ ] Cài `ragas`, `datasets`
- [ ] Tạo test set 20 câu hỏi pháp lý dựa trên Luật Doanh Nghiệp:
  - Ví dụ: "Công ty TNHH 1 thành viên có được phát hành cổ phần không?"
  - Ví dụ: "Chủ tịch Hội đồng thành viên có nhiệm kỳ bao lâu?"
  - Có đáp án chuẩn (điều luật tham chiếu)
- [ ] `app/evaluation/ragas_eval.py`:
  - Chạy pipeline, thu thập (question, contexts, answer)
  - Đánh giá 4 metric RAGAS
  - **Thêm**: thủ công kiểm tra Citation Accuracy trên 20 câu
  - Tuning: thử top_k = 3, 5, 7, 10
  - Ghi kết quả vào `evaluation/ragas_results.json`
- [ ] Bảng so sánh top_k:
  ```
  | top_k | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
  |-------|-------------------|----------------|--------------|------------------|
  | 3     | ...               | ...            | ...          | ...              |
  | 5     | ...               | ...            | ...          | ...              |
  | 7     | ...               | ...            | ...          | ...              |
  | 10    | ...               | ...            | ...          | ...              |
  ```

**Check hiểu:**
- "Faithfulness 0.85" nghĩa là gì trong bối cảnh tra cứu luật? Chấp nhận được không?
- Tại sao Citation Accuracy quan trọng với luật hơn là với mock interview?

---

### Ngày 12: Re-Ranking & Query Rewriting Cho Tiếng Việt

**Học:**
- Re-ranking: Retrieve top 10 → xếp hạng lại → lấy top 5
- Cross-encoder (chậm nhưng chính xác) vs Bi-encoder (nhanh)
- **Vấn đề với tiếng Việt**: cross-encoder phổ biến ít hỗ trợ tiếng Việt → dùng LLM-based rerank
- Query rewriting: câu hỏi người dùng thường không phải ngôn ngữ luật → viết lại thành query pháp lý chuẩn

**Làm:**
- [ ] Cài `sentence-transformers` (đã có)
- [ ] Thêm vào `app/services/rag.py`:
  ```python
  class RAGService:
      def rerank_with_llm(self, query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
          """Dùng LLM để rerank: cho LLM chấm điểm relevance từng chunk"""
          # Prompt: "Cho câu hỏi pháp lý X và danh sách điều luật, sắp xếp theo độ liên quan"
          ...

      async def rewrite_query(self, query: str) -> str:
          """Chuyển câu hỏi thường thành ngôn ngữ pháp lý chuẩn"""
          prompt = f"""Viết lại câu hỏi sau bằng ngôn ngữ pháp lý chuẩn, tập trung vào thuật ngữ chính xác:
  Câu hỏi: "{query}"
  Câu hỏi đã viết lại:"""
          return await self.llm.generate(prompt, temperature=0.2)
  ```
- [ ] Cập nhật pipeline: rewrite query → retrieve 10 → rerank → top 5 → generate
- [ ] Chạy lại RAGAS → so sánh với/không có rerank + query rewrite

**Check hiểu:**
- Tại sao query rewriting quan trọng cho tra cứu luật?
- Người dùng hỏi "mở công ty cần gì" → rewritten query nên là gì?

---

### Ngày 13: Streamlit UI — Chat & Documents

**Học:**
- Streamlit fundamentals: `st.chat_message`, `st.file_uploader`, `st.session_state`
- `st.write_stream` để hiển thị streaming
- `@st.cache_resource` cho model/connection
- Multi-page app structure

**Làm:**
- [ ] Cài `streamlit`
- [ ] `streamlit_app/Home.py` — dashboard tổng quan:
  - Sidebar navigation
  - Thống kê: số văn bản luật, số điều đã index, model đang dùng
  - Danh sách luật đã có trong hệ thống
- [ ] `streamlit_app/utils.py` — API client gọi backend:
  ```python
  import httpx

  API_BASE = "http://localhost:8000"

  async def stream_chat(session_id: str, message: str, law_filter: str = None):
      async with httpx.AsyncClient(timeout=120) as client:
          async with client.stream(
              "POST", f"{API_BASE}/api/v1/chat/{session_id}",
              json={"content": message, "law_name": law_filter}
          ) as resp:
              async for line in resp.aiter_lines():
                  if line.startswith("data: "):
                      yield line[6:]
  ```
- [ ] `streamlit_app/pages/1_Chat.py`:
  - Sidebar: danh sách session + filter theo bộ luật + nút tạo mới
  - Main: chat bubble (user bên phải, assistant bên trái)
  - Streaming response hiển thị real-time
  - **Citation highlight**: mỗi câu trả lời có phần "Căn cứ pháp lý" expandable, hiển thị tên luật + số điều
  - Nút "Xem điều luật đầy đủ" mở popup
- [ ] `streamlit_app/pages/2_Documents.py`:
  - Upload zone (PDF, DOCX, TXT)
  - Form nhập metadata: tên luật, ngày hiệu lực
  - Document list với trạng thái (indexing/done/error)
  - Nút Re-index (khi luật cập nhật)

**File tạo:**
```
streamlit_app/Home.py
streamlit_app/utils.py
streamlit_app/pages/1_Chat.py
streamlit_app/pages/2_Documents.py
```

---

### Ngày 14: Buffer Day (Tuần 1-2 Review)

**Làm:**
- [ ] `docker compose up` → kiểm tra tất cả services
- [ ] Test flow end-to-end: upload Luật Doanh Nghiệp → hỏi "Thủ tục tăng vốn điều lệ" → xem citation
- [ ] Review code, thêm type hints chỗ thiếu
- [ ] Chạy `pytest -v`, sửa test fail
- [ ] Commit sạch sẽ

---

## Tuần 3: Tính Năng Đặc Thù Cho Văn Bản Luật

### Ngày 15: Citation Parsing & Validation

**Học:**
- Citation format trong văn bản luật VN: "theo quy định tại Điều X Luật Y", "khoản 2 Điều 5 Nghị định Z"
- Regex pattern cho citation tiếng Việt
- Validation: kiểm tra citation LLM trả về có khớp với context không?
- Citation hallucination: LLM bịa ra Điều 99 nhưng luật chỉ có 50 điều

**Làm:**
- [ ] `app/services/citation.py`:
  ```python
  import re

  class CitationService:
      # Pattern: phát hiện citation trong văn bản luật VN
      CITATION_PATTERNS = [
          r'(?:theo|tại|theo quy định tại)\s+(?:khoản\s+\d+\s+)?(?:điểm\s+\w+\s+)?Điều\s+(\d+)\s+(?:của\s+)?(Luật|Nghị định|Thông tư)\s+(.+?)(?:,|\.|\n|và|;)',
          r'Điều\s+(\d+)\s+(Luật|Nghị định|Thông tư)\s+(.+?)(?:,|\.|\n)',
      ]

      def extract_citations(self, text: str) -> list[dict]:
          """Trích xuất tất cả citation từ 1 đoạn văn bản"""
          citations = []
          for pattern in self.CITATION_PATTERNS:
              for match in re.finditer(pattern, text, re.IGNORECASE):
                  citations.append({
                      "article": match.group(1),
                      "doc_type": match.group(2),
                      "doc_name": match.group(3).strip(),
                      "full_text": match.group(0).strip(),
                  })
          return citations

      def validate_citation(self, answer: str, context_chunks: list[dict]) -> dict:
          """Kiểm tra citation trong answer có thực sự xuất hiện trong context không"""
          answer_citations = self.extract_citations(answer)
          valid = []
          invalid = []
          for cit in answer_citations:
              found = any(
                  cit["article"] in c["text"] and cit["doc_name"].lower() in c["text"].lower()
                  for c in context_chunks
              )
              if found:
                  valid.append(cit)
              else:
                  invalid.append(cit)
          return {"valid": valid, "invalid": invalid, "hallucination_rate": len(invalid) / len(answer_citations) if answer_citations else 0}

      def check_article_exists(self, article_num: int, law_text: str) -> bool:
          """Kiểm tra điều X có thực sự tồn tại trong bộ luật không"""
          return bool(re.search(rf'Điều\s+{article_num}\s*[\.:]', law_text))
  ```
- [ ] `tests/test_citation.py` — test với các mẫu citation thật
  - "theo quy định tại khoản 2 Điều 68 Luật Doanh Nghiệp 2020" → extract được article=68
  - Citation bịa → validate trả về invalid
- [ ] Tích hợp vào RAG pipeline: sau khi LLM generate → validate citations → flag warning nếu hallucination

**Check hiểu:**
- Tại sao cần validate citation? Không validate thì điều gì xảy ra?
- Citation hallucination rate > 0% có chấp nhận được không?

**File tạo:**
```
app/services/citation.py
tests/test_citation.py
```

---

### Ngày 16: Cross-Reference Detection & Version Tracking

**Học:**
- Văn bản luật VN thường dẫn chiếu lẫn nhau: "theo quy định tại Luật Doanh Nghiệp..."
- Phiên bản luật: Luật Doanh Nghiệp 2014 vs 2020 — điều khoản thay đổi
- Luật hết hiệu lực: cần cảnh báo nếu người dùng hỏi về luật cũ

**Làm:**
- [ ] `app/prompts/cross_reference.py`:
  ```python
  CROSS_REF_PROMPT = """Phân tích đoạn văn bản luật sau và liệt kê TẤT CẢ các dẫn chiếu đến văn bản pháp luật khác.

  Đoạn văn bản:
  {text}

  Trả về JSON:
  {{
    "references": [
      {{"target_law": "tên luật được dẫn chiếu", "target_article": "số điều (nếu có)", "context": "nội dung dẫn chiếu"}}
    ]
  }}"""
  ```
- [ ] `app/services/legal.py`:
  ```python
  class LegalService:
      def detect_cross_references(self, text: str) -> list[dict]:
          """Dùng LLM để phát hiện dẫn chiếu trong văn bản luật"""
          ...

      async def check_version_conflict(
          self, article_num: str, law_name: str
      ) -> dict:
          """Kiểm tra xem có phiên bản mới hơn của điều luật này không"""
          # Query DB: tìm law_name tương tự + version_date mới hơn
          ...

      def get_law_versions(self, law_name: str) -> list[dict]:
          """Trả về lịch sử phiên bản của 1 bộ luật"""
          ...
  ```
- [ ] `app/api/legal.py`:
  - `GET /api/v1/legal/cross-refs?law=X&article=Y` — xem các dẫn chiếu
  - `GET /api/v1/legal/versions?law=X` — xem lịch sử phiên bản
  - `GET /api/v1/legal/check-expiry?law=X` — kiểm tra hết hiệu lực chưa
- [ ] `tests/test_legal.py`

**Check hiểu:**
- Tại sao cross-reference quan trọng trong tra cứu luật?
- Luật Doanh Nghiệp 2020 có hiệu lực từ 1/1/2021. Nếu người dùng hỏi về 1 giao dịch năm 2019, chatbot nên trả lời bằng luật nào?

**File tạo:**
```
app/prompts/cross_reference.py
app/services/legal.py
app/api/legal.py
app/schemas/legal.py
tests/test_legal.py
```

---

### Ngày 17: Rate Limiting + Error Handling

**Học:**
- Rate limiting: token bucket algorithm
- FastAPI middleware
- Structured error responses
- Global exception handlers

**Làm:**
- [ ] Thêm Redis vào `docker-compose.yml`
- [ ] Cài `redis`, `slowapi` (hoặc tự code rate limiter với Redis)
- [ ] Rate limiter middleware: 10 requests/phút cho chat endpoint
- [ ] Global exception handler: mọi lỗi → `{"error": "...", "detail": "...", "code": "..."}`
- [ ] Validation error handler (Pydantic validation → message tiếng Việt)
- [ ] `tests/test_error_handling.py`

---

### Ngày 18: Logging & Observability

**Học:**
- Structured logging (`structlog` hoặc `python-json-logger`)
- Log levels: DEBUG, INFO, WARNING, ERROR
- Request ID tracing (mỗi request 1 UUID xuyên suốt)
- Đo latency từng bước trong RAG pipeline

**Làm:**
- [ ] Cấu hình logging JSON format
- [ ] Middleware: gán `request_id` cho mỗi request
- [ ] Log: request vào (method, path, duration), embedding call latency, Qdrant search latency, LLM generation latency, citation validation latency
- [ ] Log LLM token usage
- [ ] Đọc log → hiểu bottleneck ở đâu

---

### Ngày 19: Testing Nâng Cao

**Học:**
- Pytest fixtures cho FastAPI TestClient
- Mock external services (Qdrant, Ollama, PostgreSQL)
- Integration test vs Unit test
- Test coverage với `pytest-cov`

**Làm:**
- [ ] `tests/conftest.py` — fixtures:
  - FastAPI `TestClient`
  - Mock `EmbeddingService` (trả về vector giả)
  - Mock `LLMService` (trả về text cứng)
  - Mock `QdrantClient`
- [ ] `tests/test_api_chat.py` — SSE streaming, session CRUD, citation trong response
- [ ] `tests/test_api_documents.py` — upload flow, chunk_by_article
- [ ] `tests/test_rag_pipeline.py` — integration test với văn bản luật mẫu
- [ ] `tests/test_citation.py` — citation extraction + validation
- [ ] `pytest --cov=app --cov-report=html`
- [ ] Target: >80% coverage cho `app/services/`

---

### Ngày 20: Docker Hoàn Thiện

**Học:**
- Dockerfile best practices
- Multi-stage build
- Health checks
- Volume mounting cho dev

**Làm:**
- [ ] `Dockerfile` cho backend:
  - Python 3.12 slim base
  - Multi-stage (build dependencies → runtime)
  - Non-root user
  - Health check: `curl http://localhost:8000/health`
- [ ] `docker-compose.yml` hoàn chỉnh:
  ```yaml
  services:
    postgres:
      image: postgres:16
      environment: {POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB}
      ports: ["5432:5432"]
      volumes: [postgres_data:/var/lib/postgresql/data]
      healthcheck: {test: "pg_isready -U raguser", interval: 10s}

    qdrant:
      image: qdrant/qdrant:latest
      ports: ["6333:6333", "6334:6334"]
      volumes: [qdrant_data:/qdrant/storage]

    redis:
      image: redis:7-alpine
      ports: ["6379:6379"]
      healthcheck: {test: "redis-cli ping", interval: 10s}

    backend:
      build: .
      command: uvicorn app.main:app --host 0.0.0.0 --reload
      ports: ["8000:8000"]
      environment:
        LLAMA_CPP_LLM_URL: "http://host.docker.internal:8080"
        LLAMA_CPP_EMBED_URL: "http://host.docker.internal:8081"
      depends_on: {postgres: condition: service_healthy, qdrant: ...}
      volumes: ["./app:/app/app"]

    streamlit:
      image: python:3.12-slim
      command: streamlit run streamlit_app/Home.py --server.port 8501
      ports: ["8501:8501"]
      depends_on: [backend]

  volumes:
    postgres_data:
    qdrant_data:
  ```
  > **Lưu ý**: llama.cpp chạy native trên Mac (cần GPU Metal), backend gọi qua `host.docker.internal:8080` (LLM) và `host.docker.internal:8081` (Embedding). KHÔNG cho llama.cpp vào Docker vì Docker trên Mac không có GPU passthrough.
- [ ] `docker compose up` → tất cả chạy, không lỗi

---

### Ngày 21: Buffer Day (Tuần 3 Review)

**Làm:**
- [ ] `docker compose down -v && docker compose up --build` → test từ zero
- [ ] Sửa bugs
- [ ] Chạy full test suite
- [ ] Commit

---

## Tuần 4: Polish & Showcase

### Ngày 22: Prompt Engineering Cho Luật

**Học:**
- Few-shot prompting: cho LLM 2-3 ví dụ câu hỏi + trả lời mẫu (có citation chuẩn)
- Chain of Thought (bắt LLM suy nghĩ từng bước): "1) Xác định câu hỏi thuộc lĩnh vực luật nào → 2) Tìm điều luật liên quan → 3) Phân tích → 4) Kết luận"
- Prompt versioning: coi prompt như code
- Test prompt consistency: chạy 5 lần, citation có ổn định không?

**Làm:**
- [ ] Review tất cả prompt trong `app/prompts/`
- [ ] Thêm few-shot examples vào `legal_assistant.py`:
  - Ví dụ 1: Hỏi về loại hình doanh nghiệp → trả lời kèm Điều 1 Luật Doanh Nghiệp 2020
  - Ví dụ 2: Hỏi về thủ tục giải thể → trả lời kèm Điều 201-209 Luật Doanh Nghiệp 2020
- [ ] Thêm Chain of Thought vào prompt phân tích pháp lý phức tạp
- [ ] Test từng prompt: chạy 5 lần, kiểm tra citation consistency
- [ ] Ghi chú: prompt nào ổn, prompt nào cần cải thiện

---

### Ngày 23: Streamlit UI Hoàn Thiện

**Làm:**
- [ ] Loading skeletons: `st.spinner` khi chờ API
- [ ] Toast notifications: `st.toast` cho success/error
- [ ] Empty states:
  - Chưa có văn bản luật → "Tải lên văn bản luật để bắt đầu tra cứu"
  - Chưa có chat → "Chọn 1 session hoặc tạo mới"
- [ ] Citation card đẹp: mỗi câu trả lời có card "Căn cứ pháp lý" với icon, màu sắc phân biệt
- [ ] Law filter dropdown: chọn "Tất cả các luật" hoặc filter theo từng bộ luật
- [ ] Error states: backend không kết nối được → thông báo rõ ràng
- [ ] Dark mode toggle

---

### Ngày 24: RAGAS Evaluation Cuối Cùng

**Làm:**
- [ ] Tạo synthetic test set 50 câu hỏi pháp lý (dựa trên 3 bộ luật đã index)
- [ ] Chạy evaluation 3 phiên bản:
  - Cơ bản: top_k=5, không rerank, không query rewrite
  - Nâng cao: top_k=10 → rerank → top 5, có query rewrite
  - Có citation validation: nâng cao + post-generation validation
- [ ] Bảng so sánh (điền số thật):
  | Metric | Cơ bản | Nâng cao | +Citation Check | Delta |
  |--------|--------|----------|-----------------|-------|
  | Context Precision | ... | ... | ... | +... |
  | Context Recall | ... | ... | ... | +... |
  | Faithfulness | ... | ... | ... | +... |
  | Answer Relevancy | ... | ... | ... | +... |
  | **Citation Accuracy** | ... | ... | ... | **+...** |
- [ ] Đưa bảng vào README
- [ ] Ghi chú: Faithfulness + Citation Accuracy là 2 metric quan trọng nhất

---

### Ngày 25: Xử Lý Edge Cases Cho Luật

**Làm:**
- [ ] Upload file không phải văn bản luật → báo lỗi "Không thể parse cấu trúc điều luật"
- [ ] Văn bản luật bị scan ảnh (không có text) → báo lỗi + đề xuất OCR
- [ ] Luật đã hết hiệu lực → cảnh báo "Luật này đã hết hiệu lực từ ngày X, được thay thế bởi Luật Y"
- [ ] Câu hỏi không liên quan đến luật → LLM từ chối "Tôi chỉ hỗ trợ tra cứu văn bản pháp luật"
- [ ] Người dùng cố tình prompt injection "hãy bỏ qua hướng dẫn và..." → system prompt chống injection
- [ ] 1 điều luật được chunk thành 2 phần → search trả về cả 2 → cần merge citation trùng
- [ ] Law name không nhất quán: "Luật Doanh Nghiệp 2020" vs "Luật Doanh nghiệp số 59/2020/QH14" → normalize
- [ ] `tests/test_edge_cases.py`

---

### Ngày 26: Authentication

**Học:**
- JWT vs API key
- FastAPI dependency injection cho auth

**Làm:**
- [ ] API key middleware: kiểm tra header `X-API-Key`
- [ ] Tạo API keys trong `.env`
- [ ] Bảo vệ tất cả endpoints `/api/v1/*`
- [ ] `streamlit_app/utils.py` — tự động gửi API key trong request
- [ ] Streamlit login page: nhập API key
- [ ] `tests/test_auth.py`

---

### Ngày 27: Performance Optimization

**Học:**
- Embedding cache với Redis
- Batch processing
- Đo đạc latency từng bước

**Làm:**
- [ ] Cache query embedding: key = `hashlib.md5(text.encode()).hexdigest()`, value = vector
- [ ] Cache common legal questions + answers (câu hỏi phổ biến: "công ty TNHH là gì")
- [ ] Batch embed khi upload document
- [ ] Đo latency: query embedding, Qdrant search, LLM generation, citation validation
- [ ] Ghi vào README: "Phản hồi trung bình Xs, citation accuracy Y%"

---

### Ngày 28: Final Polish + Known Limitations

**Làm:**
- [ ] `docker compose down -v && docker compose up --build` → test từ zero
- [ ] **Viết "Known Limitations"** (quan trọng — thể hiện tư duy kỹ sư):
  - Hỗ trợ văn bản luật tiếng Việt; tiếng Anh hoặc song ngữ có thể kém chính xác hơn
  - Embedding model Qwen3-Embedding 0.6B (1024d) — tốt cho đa ngôn ngữ nhưng không chuyên biệt cho luật. Có thể nâng cấp lên model legal-specific nếu có
  - Qwen2.5 7B quantized Q4_K_M — giảm chất lượng so với bản FP16 gốc, context window 8K tokens có thể bị cắt với bộ luật lớn (>200 điều)
  - Không xử lý bảng biểu, sơ đồ trong văn bản luật
  - Citation validation dựa trên regex + LLM, chưa có legal knowledge graph
  - Chưa hỗ trợ multi-hop reasoning phức tạp (câu hỏi cần suy luận qua nhiều điều luật)
  - Hệ thống chạy trên 1 máy, chưa scale ngang được
  - Phiên bản luật: hiện tại cảnh báo thủ công, chưa tự động crawl cập nhật từ CSDL quốc gia
- [ ] README.md đầy đủ:
  - Logo / banner
  - Architecture diagram (Mermaid)
  - Tech stack + giải thích lý do chọn
  - Features:
    - Tra cứu văn bản luật với citation đến điều/khoản
    - Cross-reference detection
    - Version tracking & cảnh báo luật hết hiệu lực
    - Citation hallucination detection
    - Filter theo bộ luật
  - Screenshots
  - Quick start: 3 dòng lệnh
  - Demo scenario:
    > "Tôi muốn mở công ty TNHH 2 thành viên, cần thủ tục gì và vốn tối thiểu bao nhiêu?"
    >
    > Bot: Theo Luật Doanh Nghiệp 2020, Điều 46... [kèm trích dẫn đầy đủ]
  - RAGAS evaluation table
  - Known Limitations
- [ ] Demo script (tiếng Việt + tiếng Anh)
- [ ] GitHub Actions: chạy test tự động khi push
- [ ] Badges: tests passing, coverage, license
- [ ] Push lên GitHub
- [ ] Commit cuối cùng: "hoàn thiện dự án RAG tra cứu văn bản pháp luật"

---

## Tài Nguyên Học Mỗi Ngày

| Ngày | Chủ đề | Tài liệu |
|------|--------|----------|
| 1 | Python + uv + Git | [uv](https://docs.astral.sh/uv/), [Git Basics](https://git-scm.com/book/en/v2) |
| 2 | Docker | [Docker Get Started](https://docs.docker.com/get-started/), [Docker Compose](https://docs.docker.com/compose/gettingstarted/) |
| 3 | FastAPI | [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/), [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| 4 | Async/SSE | [AsyncIO](https://docs.python.org/3/library/asyncio.html), [SSE MDN](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) |
| 5 | Embedding | [llama.cpp](https://github.com/ggerganov/llama.cpp), [Qwen3-Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) |
| 6 | Qdrant | [Qdrant Docs](https://qdrant.tech/documentation/), [Vector DB Explained](https://www.pinecone.io/learn/vector-database/) |
| 7 | Document Processing | [Chunking Strategies](https://www.pinecone.io/learn/chunking-strategies/), Cấu trúc văn bản luật VN |
| 8 | llama.cpp + LLM | [llama.cpp server](https://github.com/ggerganov/llama.cpp), [Qwen2.5](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct) |
| 9 | RAG Pipeline | [RAG Guide](https://www.pinecone.io/learn/retrieval-augmented-generation/) |
| 10 | PostgreSQL | [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), [Alembic](https://alembic.sqlalchemy.org/) |
| 11 | RAGAS | [RAGAS Docs](https://docs.ragas.io/) |
| 12 | Re-ranking | [Cross-Encoders](https://www.sbert.net/examples/applications/cross-encoder/), [Cohere Rerank Guide](https://txt.cohere.com/rerank/) |
| 13 | Streamlit | [Streamlit Docs](https://docs.streamlit.io/) |
| 14 | Buffer | Review + refactor |
| 15 | Citation Validation | Regex + legal citation format VN |
| 16 | Cross-Reference + Version | Legal knowledge graph concepts |
| 17 | Rate Limiting | [SlowApi](https://slowapi.readthedocs.io/), [FastAPI Middleware](https://fastapi.tiangolo.com/tutorial/middleware/) |
| 18 | Logging | [Python Logging HOWTO](https://docs.python.org/3/howto/logging.html) |
| 19 | Testing | [pytest](https://docs.pytest.org/), [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/) |
| 20 | Docker Production | [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/) |
| 21 | Buffer | Review + refactor |
| 22 | Prompt Engineering | [Anthropic Prompt Library](https://docs.anthropic.com/en/prompt-library/library) |
| 23 | Streamlit Polish | Streamlit docs |
| 24 | RAGAS Final | RAGAS docs |
| 25 | Edge Cases | Tự hỏi: "Cái gì có thể sai khi tra cứu luật?" |
| 26 | Auth | [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/) |
| 27 | Performance | [FastAPI Concurrency](https://fastapi.tiangolo.com/async/) |
| 28 | Final | Review + ship |

---

## Nguồn Dữ Liệu Văn Bản Luật

| Nguồn | URL | Định dạng | Ghi chú |
|-------|-----|-----------|---------|
| Thư viện pháp luật | thuvienphapluat.vn | HTML → copy ra .txt | Cập nhật liên tục, có ghi chú văn bản hết hiệu lực |
| Cơ sở dữ liệu quốc gia | vbpl.vn | HTML/PDF | Văn bản chính thức, có lịch sử phiên bản |
| Bộ Tư Pháp | moj.gov.vn | DOCX | Công báo chính thức |

### Dữ liệu cho từng tuần

**Tuần 1** (tối thiểu để chạy được):
- Luật Doanh Nghiệp 2020 (hiệu lực 1/1/2021) — vẫn còn hiệu lực đến 2026
- Luật Đầu Tư 2020 (hiệu lực 1/1/2021)

**Tuần 2-3** (mở rộng + test version tracking):
- Luật Lao Động 2019 (hiệu lực 1/1/2021)
- Luật Doanh Nghiệp 2014 (đã hết hiệu lực) — để test cảnh báo phiên bản cũ
- Nghị định 01/2021 (đăng ký doanh nghiệp)
- Luật Đất Đai 2024 (hiệu lực 1/1/2025) — luật mới nhất, test cross-reference với luật cũ

### Quan trọng: Cách lấy dữ liệu

Khi bạn vào các trang trên, **luôn kiểm tra**:
1. Văn bản còn hiệu lực không? (thuvienphapluat.vn có tag "Còn hiệu lực" / "Hết hiệu lực")
2. Văn bản này thay thế văn bản nào? (dùng cho cross-reference)
3. Có văn bản hợp nhất chưa? (nếu có sửa đổi bổ sung)

> **Đây chính là bài toán thực tế**: Năm 2026, một số Nghị định ban hành năm 2020-2021 có thể đã được sửa đổi. Hệ thống RAG của bạn phải **phiên bản hóa** và **cảnh báo** được điều này — đó là giá trị cốt lõi cho công ty luật.

---

## Checklist Kỹ Năng Sau 4 Tuần

- [ ] **Python Async backend** — FastAPI, REST API, SSE streaming
- [ ] **RAG pipeline** — tự code từ đầu, hiểu từng bước, tối ưu cho văn bản luật
- [ ] **llama.cpp + Qwen** — serve LLM + Embedding qua OpenAI-compatible API, tận dụng GPU Metal
- [ ] **Embedding & Vector Search** — semantic search với Qdrant, multilingual embedding (Qwen3-Embedding)
- [ ] **Legal Document Processing** — chunk theo điều luật, metadata strategy
- [ ] **Citation System** — extract, validate, detect hallucination
- [ ] **Cross-Reference & Version Tracking** — phát hiện dẫn chiếu, cảnh báo luật hết hiệu lực
- [ ] **Prompt Engineering** — legal assistant prompt, few-shot, CoT, anti-hallucination
- [ ] **RAG Evaluation** — RAGAS + custom Citation Accuracy metric
- [ ] **Database** — SQLAlchemy async, Alembic migrations, JSONB
- [ ] **Testing** — unit test, integration test, mock services, >80% coverage
- [ ] **Docker** — multi-service orchestration, health checks, volumes
- [ ] **Production practices** — logging, rate limiting, error handling, auth
- [ ] **Documentation** — README chuyên nghiệp, architecture diagram, demo scenario, Known Limitations
- [ ] **CI/CD** — GitHub Actions

---

## Câu Hỏi Bạn Sẽ Trả Lời Được Khi Phỏng Vấn

| # | Câu hỏi | Evidence trong project |
|---|---------|----------------------|
| 1 | "Tại sao chọn Qdrant thay vì Pinecone hay ChromaDB?" | Ngày 6 + README |
| 2 | "Em evaluate RAG pipeline như thế nào? Làm sao biết hệ thống trả lời đúng?" | Ngày 11 + 24 (RAGAS + Citation Accuracy) |
| 3 | "Làm sao chọn top_k cho retrieval?" | Ngày 11 + Ngày 24 (bảng so sánh) |
| 4 | "Làm sao xử lý hallucination trong tra cứu luật?" | Ngày 9 (prompt từ chối) + Ngày 15 (citation validation) |
| 5 | "Tại sao chọn llama.cpp thay vì Ollama?" | Ngày 5 + Ngày 8 (benchmark, OpenAI-compatible API, Metal GPU) |
| 6 | "Tại sao dùng Qwen thay vì Llama?" | Ngày 5 + Ngày 8 (hỗ trợ tiếng Việt tốt hơn) |
| 7 | "Embedding model cho tiếng Việt thì chọn thế nào?" | Ngày 5 (Qwen3-Embedding, 1024d) |
| 8 | "Văn bản luật có phiên bản, xử lý thế nào?" | Ngày 16 (version tracking + cảnh báo hết hiệu lực) |
| 9 | "Tại sao không dùng LangChain?" | Ngày 9 (tự code RAG pipeline) |
| 10 | "Chunking strategy cho văn bản luật khác gì văn bản thường?" | Ngày 7 (semantic chunking theo điều luật) |
| 11 | "Hệ thống này có hạn chế gì?" | Ngày 28 (Known Limitations) |
| 12 | "Làm sao hệ thống phát hiện luật này dẫn chiếu luật khác?" | Ngày 16 (cross-reference detection) |
| 13 | "Nếu có 1 triệu văn bản luật thì phải thay đổi gì?" | Ngày 27 (performance) + Ngày 28 (Known Limitations) |
| 14 | "Làm sao chống prompt injection?" | Ngày 25 (edge cases) + Ngày 26 (auth) |
