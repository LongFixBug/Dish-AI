# FoodAI — Lộ Trình Học + Build (8 Tuần)

> **Trình độ hiện tại**: Mới bắt đầu Python
> **Mục tiêu**: Vừa làm project chất lượng bỏ CV, vừa học đủ skill để apply các vị trí AI Engineer (CV + GenAI + RAG)
> **Sản phẩm**: App mobile chụp ảnh món ăn → AI nhận diện món + phân tích dinh dưỡng từ database chính quyền
> **Differentiator**: Tối ưu cho **món ăn Việt**, tự train CV model + RAG pipeline, không chỉ wrap API
> **Thời gian**: 8 tuần full-time
> **UI**: Streamlit (Python-native, không cần JavaScript/React)

---

## 1. Tại sao chọn chủ đề "Nhận diện món ăn + phân tích dinh dưỡng"?

| Yếu tố | Lý do |
|--------|-------|
| **Đúng domain** | Công ty AI VN làm về CV + LLM đều cần; món ăn Việt là differentiator với MyFitnessPal |
| **Cover được nhiều skill** | CV (PyTorch) + LLM (Qwen3.7 Plus + llama.cpp) + RAG + Agentic + Deploy cloud |
| **Dữ liệu công khai** | USDA FoodData Central + Vietnam Food Composition Table có sẵn, miễn phí |
| **Bài toán thực tế** | Người VN muốn kiểm soát dinh dưỡng từ món ăn hàng ngày — chưa có app nào làm tốt |
| **Độ khó kỹ thuật đa dạng** | Fine-tune CV model cho món Việt, RAG với nutrition DB, validate hallucination |
| **Dễ demo** | Chụp tô phở → AI trả về calo, đạm, carb, chất béo → dễ hiểu, dễ check |

---

## 2. Triết lý học

- **Build để học, không học để build** — mỗi ngày code ra thứ chạy được
- **Sâu > Rộng** — 1 pipeline đúng + có test + đo lường được > 10 tính năng nửa vời
- **Code trước, đọc sau** — xem ý tưởng → code → gặp lỗi → đọc doc sửa
- **Testing không phải việc cuối cùng** — viết test mỗi ngày, không dồn vào ngày chót
- **Commit mỗi ngày** — message tiếng Việt rõ ràng
- **Chất lượng dữ liệu > Mô hình xịn** — data preparation + cleaning quyết định 80% chất lượng
- **Hiểu bản chất > Dùng framework** — tự code RAG trước, học LangChain sau khi đã hiểu

---

## 3. Tech Stack Cuối Cùng

### Backend
| Layer | Chọn gì | Tại sao |
|-------|---------|---------|
| API Server | **FastAPI** (async) | Async, auto-docs, type-safe, industry standard |
| Package Manager | **uv** (thay pip) | Tốc độ gấp 10-100x, lock file chuẩn |

### AI / ML
| Layer | Chọn gì | Tại sao |
|-------|---------|---------|
| **CV Model (local)** | **PyTorch** + ResNet50/EfficientNet | Tự train/fine-tune để hiểu CV, deploy lên cloud |
| **Vision API (cloud)** | **Qwen3.7 Plus** (qua OpenCode API) | So sánh local model vs cloud API, cost/latency analysis |
| **LLM Server** | **llama.cpp** | OpenAI-compatible API, tận dụng GPU Mac Metal |
| **LLM Model** | **Qwen2.5 7B** (GGUF) | Hỗ trợ tiếng Việt vượt trội, Apache 2.0 |
| **Embedding Server** | **llama.cpp** (server mode, `/v1/embeddings`) | Cùng 1 server cho cả LLM + Embedding |
| **Embedding Model** | **Qwen3-Embedding 0.6B** (GGUF) | Multilingual, hỗ trợ tiếng Việt tốt, 1024d |

### Data / Storage
| Layer | Chọn gì | Tại sao |
|-------|---------|---------|
| Vector DB | **pgvector** (PostgreSQL extension) | Gộp chung 1 DB, đỡ phải maintain 2 service |
| Database | **PostgreSQL** (SQLAlchemy async) | Chat history, document metadata, nutrition cache |
| Cache | **Redis** | Cache món phổ biến, giảm API cost |

### RAG
| Layer | Chọn gì | Tại sao |
|-------|---------|---------|
| RAG Framework | **Tự code trước**, tuần 8 học thêm LangChain | Hiểu sâu → dùng framework có chủ đích |
| RAG Evaluation | **RAGAS** + custom eval harness | Đo lường retrieval accuracy, hallucination rate |

### UI & Deploy
| Layer | Chọn gì | Tại sao |
|-------|---------|---------|
| UI | **Streamlit** | Python-native, 30 dòng là có UI |
| Container | **Docker Compose** | 1 lệnh `docker compose up` |
| Cloud Deploy | **AWS/GCP** (chọn 1) | Deploy CV model + API lên cloud |

---

## 4. Kiến Trúc Tổng Thể

```
┌──────────────────────────────────────────────────────────────────────┐
│                        FOODAI PLATFORM                               │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                      STREAMLIT UI                            │    │
│  │   Upload ảnh → Kết quả dinh dưỡng → Chat hỏi thêm            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│                              ▼                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    FASTAPI BACKEND                            │    │
│  │                                                               │    │
│  │  ┌───────────────────────────────────────────────────────┐   │    │
│  │  │              ORCHESTRATOR (Agentic)                    │   │    │
│  │  │                                                       │   │    │
│  │  │  Step 1 ──► Step 2 ──► Step 3 ──► Step 4 ──► Done    │   │    │
│  │  │  CV        RAG per    Python     LLM giai             │   │    │
│  │  │  Identify  ingredient math x     thich ket             │   │    │
│  │  │                                       │qua              │   │    │
│  │  │                                       └──► done ───────│   │    │
│  │  └───────────────────────────────────────────────────────┘   │    │
│  │                                                               │    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │    │
│  │  │ CV Model │  │Qwen3.7+  │  │ RAG      │  │ LLM      │     │    │
│  │  │ PyTorch  │  │ Vision   │  │ Pipeline │  │ Qwen 7B  │     │    │
│  │  │ (local)  │  │ (cloud)  │  │ (custom) │  │ llama.cpp│     │    │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘     │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              │                                       │
│         ┌────────────────────┼────────────────────┐                 │
│         ▼                    ▼                     ▼                 │
│  ┌──────────┐  ┌──────────────────────┐  ┌──────────────┐         │
│  │ pgvector │  │ PostgreSQL (metadata) │  │    Redis     │         │
│  │ (USDA +  │  │ chat_history         │  │  (cache      │         │
│  │  ViFood) │  │ eval_results         │  │   món phổ    │         │
│  │          │  │                      │  │   biến)      │         │
│  └──────────┘  └──────────────────────┘  └──────────────┘         │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │               EXTERNAL (tuần 8 optional)                 │        │
│  │   AWS/GCP: CV model serving + API hosting                │        │
│  └─────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Các Skill Học Được — Map Với Yêu Cầu JD

| # | Skill | Implement trong FoodAI | Match JD |
|---|-------|----------------------|----------|
| 1 | **Python thành thạo** | FastAPI async + Pydantic + typing + asyncpg | ✅ Bắt buộc |
| 2 | **PyTorch** | Fine-tune ResNet50/EfficientNet phân loại món Việt + detect ingredients | ✅ Bắt buộc |
| 3 | **Computer Vision** | Preprocess dataset, augmentation, training loop, evaluation metrics | ✅ Bắt buộc |
| 4 | **Generative AI / LLM** | llama.cpp Qwen2.5 7B, Qwen3.7 Plus Vision API, prompt engineering | ✅ Bắt buộc |
| 5 | **RAG** | Tự code pipeline: chunk → embed → search → rerank → generate | ✅ Lợi thế |
| 6 | **Embedding** | Qwen3-Embedding + pgvector HNSW index + similarity search | ✅ Lợi thế |
| 7 | **Structured Output** | Pydantic schema + Qwen3.7 Plus structured JSON output | ✅ Lợi thế |
| 8 | **Agentic Workflow** | Multi-step orchestration + self-validation + retry | ✅ Lợi thế |
| 9 | **Evaluation** | RAGAS + custom eval harness 50 ảnh test | ✅ Lợi thế |
| 10 | **Deploy Cloud** | Docker + AWS/GCP model serving | ✅ Bắt buộc |
| 11 | **ML/DL Pipeline** | Data prep → training → eval → export → deploy | ✅ Bắt buộc |
| 12 | **LangChain** (bonus) | Tuần 8: refactor 1 phần RAG sang LangChain để biết | ⭐ Bonus |

---

## 6. Lộ Trình 8 Tuần Chi Tiết

### Tuần 1-2: Foundation + CV Dataset
**Mục tiêu**: Setup xong infrastructure + có dataset món Việt sẵn sàng train

| Ngày | Làm gì | Skill học |
|------|--------|-----------|
| 1-2 | ✅ FastAPI skeleton (đã xong), ✅ Docker Compose postgres+pgvector (đã xong) | Docker, async Python |
| 3-4 | Setup llama.cpp: tải Qwen2.5 7B GGUF + Qwen3-Embedding GGUF, chạy server | Self-host LLM, GGUF format |
| 5-6 | **CV Dataset**: Thu thập 500-1000 ảnh món Việt (phở, bún bò, cơm tấm, bánh xèo...), gán nhãn | Dataset preparation, labeling |
| 7-8 | **CV Dataset (tiếp)**: Augmentation (flip, rotate, color jitter), train/val/test split, DataLoader | PyTorch `Dataset`, `DataLoader`, `transforms` |
| 9-10 | **PyTorch Baseline**: Load pretrained ResNet50, thay classification head, train epoch đầu tiên | Transfer learning, fine-tuning |
| 11-12 | Train model 5-10 epochs, log loss/accuracy, save checkpoint | Training loop, TensorBoard |
| 13-14 | Evaluate model: confusion matrix, precision/recall/F1 cho từng món | Model evaluation metrics |

**Deliverable cuối tuần 2**:
- llama.cpp chạy được LLM + Embedding
- CV model phân loại được 10-15 món Việt cơ bản (accuracy > 70%)
- Toàn bộ trên Docker

---

### Tuần 3: Nutrition Database + Embedding
**Mục tiêu**: Có database dinh dưỡng search được bằng vector

| Ngày | Làm gì | Skill học |
|------|--------|-----------|
| 1-2 | Parse USDA FoodData Central JSON/CSV → extract ingredient + nutrition | Data processing, JSON/CSV parsing |
| 3-4 | Parse Vietnam Food Composition Table → merge với USDA thành 1 DB thống nhất | Data cleaning, normalization |
| 5-6 | Viết `app/services/embedding.py`: gọi llama.cpp `/v1/embeddings` cho từng ingredient | Embedding API, async HTTP |
| 7-8 | Viết `app/services/document.py`: chunk text, embed, insert vào pgvector | Chunking strategy, vector insert |
| 9-10 | Index HNSW cho bảng pgvector, benchmark speed | HNSW index, query optimization |

**Deliverable cuối tuần 3**:
- ~5000 ingredients đã được embed + lưu pgvector
- Query `"thịt bò"` → trả về top-5 ingredients gần nhất kèm nutrition

---

### Tuần 4: Core RAG Pipeline (Tự Code)
**Mục tiêu**: Pipeline RAG hoàn chỉnh, từ ingredient → nutrition JSON

| Ngày | Làm gì | Skill học |
|------|--------|-----------|
| 1-2 | Viết `app/services/rag.py`: `retrieve(ingredient_name, top_k=5)` | Vector search, similarity threshold |
| 3-4 | Prompt template: `"Cho ingredient X, trả về nutrition đầy đủ từ context: {docs}"` | Prompt engineering |
| 5-6 | LLM generate: gọi llama.cpp `/v1/chat/completions` với context | Context assembly, token limit |
| 7-8 | Structured output: Pydantic schema validate LLM response | Schema validation, retry on fail |
| 9-10 | End-to-end test: `"thịt bò 100g"` → JSON `{calo, đạm, béo, carb, xơ}` | Integration testing |

**Deliverable cuối tuần 4**:
- Gọi `POST /api/v1/nutrition/lookup` với `{"ingredient": "thịt bò", "gram": 100}` → JSON dinh dưỡng chính xác

---

### Tuần 5: Agentic Workflow
**Mục tiêu**: Pipeline đầy đủ từ ảnh → dinh dưỡng, LLM không làm toán

| Ngày | Làm gì | Skill học |
|------|--------|-----------|
| 1-2 | Step 1 - Identify: Qwen3.7 Plus + CV model → tên món + list ingredient + gram | Model ensemble, response parsing |
| 3-4 | Step 2 - RAG per ingredient: loop từng ingredient → gọi RAG pipeline | Batch processing, async gather |
| 5-6 | Step 3 - Python math: gram × per_gram = nutrition cho từng ingredient | Data aggregation (toán học, không LLM) |
| 7-8 | Step 4 - LLM: Qwen2.5 7B viết lời giải thích kết quả, không làm toán | Prompt engineering cho explanation |
| 9-10 | Full pipeline test: upload ảnh tô phở → JSON dinh dưỡng + confidence từ % DB coverage | End-to-end integration |

**Deliverable cuối tuần 5**:
- `POST /api/v1/analyze` upload ảnh → full JSON nutrition + confidence score
- Pipeline chạy < 5 giây (có cache)

---

### Tuần 6: Streamlit UI + Eval Harness
**Mục tiêu**: Có UI demo + đánh giá được chất lượng

| Ngày | Làm gì | Skill học |
|------|--------|-----------|
| 1-3 | Streamlit: upload ảnh, hiển thị kết quả dinh dưỡng, biểu đồ radar macro | Streamlit components |
| 4-5 | Eval dataset: chuẩn bị 50 ảnh test + ground truth nutrition (manual label) | Test set preparation |
| 6-7 | RAGAS evaluation: context precision, recall, faithfulness, answer relevancy | RAG evaluation framework |
| 8-9 | Custom eval: accuracy metrics, schema compliance rate, hallucination rate | Custom eval harness |
| 10 | Eval dashboard Streamlit: biểu đồ, bảng so sánh Qwen3.7+ vs local model | Data visualization |

**Deliverable cuối tuần 6**:
- UI Streamlit hoàn chỉnh: upload → phân tích → kết quả
- Eval report: accuracy 80%+, hallucination < 10%

---

### Tuần 7: Optimization + LangChain
**Mục tiêu**: Tối ưu cost/latency, học LangChain

| Ngày | Làm gì | Skill học |
|------|--------|-----------|
| 1-2 | Redis cache: cache kết quả món phổ biến (phở bò, cơm gà...), TTL 24h | Caching strategy |
| 3-4 | Model routing: dùng CV local model trước → nếu confidence thấp mới gọi Qwen3.7+ | Cost optimization |
| 5-6 | Benchmark: so sánh latency + cost local-only vs Qwen3.7+-only vs hybrid | Performance benchmarking |
| 7-8 | **LangChain refactor**: viết lại 1 phần RAG pipeline bằng LangChain, so sánh với bản tự code | LangChain: chain, retriever, prompt template |
| 9-10 | Viết documentation + blog post về "Tự code RAG vs LangChain: khác biệt là gì?" | Technical writing |

**Deliverable cuối tuần 7**:
- Cost/latency optimization report: hybrid mode giảm 40% cost vs pure Qwen3.7+
- LangChain comparison: code cả 2 phiên bản, biết ưu/nhược mỗi cái

---

### Tuần 8: Cloud Deploy + Portfolio Polish
**Mục tiêu**: Deploy lên cloud, hoàn thiện CV

| Ngày | Làm gì | Skill học |
|------|--------|-----------|
| 1-2 | Export CV model → ONNX/TorchScript | Model export |
| 3-4 | Deploy CV model lên AWS SageMaker / GCP Vertex AI | Cloud model serving |
| 5-6 | Deploy FastAPI backend + Streamlit lên cloud | Cloud deployment |
| 7-8 | Viết README.md (có diagram, demo GIF, benchmark table) | Portfolio presentation |
| 9-10 | Quay video demo + viết blog technical | Communication skills |

**Deliverable cuối tuần 8**:
- App chạy trên cloud, có public URL
- GitHub README hoàn chỉnh
- Blog post + video demo
- CV-ready

---

## 7. Project Structure Cuối Cùng

```
FoodAI/
├── models/                              # GGUF model files (gitignored)
│   ├── qwen2.5-7b-instruct-q4_k_m.gguf
│   └── qwen3-embedding-0.6b-q4_k_m.gguf
├── checkpoints/                         # PyTorch model checkpoints (gitignored)
│   └── resnet50-vietfood-epoch10.pth
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app
│   ├── config.py                        # Settings từ biến môi trường
│   ├── api/
│   │   ├── __init__.py
│   │   ├── analyze.py                   # POST /analyze — upload ảnh → nutrition
│   │   ├── nutrition.py                 # GET /nutrition/search — tìm ingredient
│   │   └── eval.py                      # POST /eval — chạy evaluation
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cv.py                        # PyTorch CV model: load, inference
│   │   ├── vision.py                    # Qwen3.7 Plus API client
│   │   ├── embedding.py                 # Gọi llama.cpp /v1/embeddings
│   │   ├── llm.py                       # Gọi llama.cpp /v1/chat/completions
│   │   ├── rag.py                       # Core RAG pipeline (tự code)
│   │   ├── document.py                  # Parse, chunk, index nutrition data
│   │   ├── orchestrator.py              # Agentic workflow: 4-step pipeline
│   │   └── cache.py                     # Redis cache layer
│   ├── db/
│   │   ├── __init__.py
│   │   ├── postgres.py                  # SQLAlchemy async session
│   │   ├── models.py                    # ORM: nutrition, chat_history, eval_results
│   │   └── vector.py                    # pgvector operations
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── nutrition.py                 # Pydantic: Ingredient, NutritionInfo
│   │   ├── analyze.py                   # Pydantic: AnalyzeRequest, AnalyzeResponse
│   │   └── eval.py                      # Pydantic: EvalMetrics
│   ├── prompts/                         # Prompt templates (version controlled)
│   │   ├── __init__.py
│   │   ├── nutrition_lookup.py          # Prompt: ingredient → nutrition
│   │   └── dish_analysis.py             # Prompt: dish analysis từ context
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── ragas_eval.py                # RAGAS evaluation
│   │   └── custom_eval.py               # Custom eval harness
│   └── training/                        # PyTorch training scripts
│       ├── __init__.py
│       ├── dataset.py                   # VietFoodDataset class
│       ├── train.py                     # Training loop
│       ├── eval_model.py                # Model evaluation
│       └── export.py                    # Export ONNX/TorchScript
├── streamlit_app/                       # Streamlit UI
│   ├── Home.py                          # Trang chính — upload ảnh
│   ├── pages/
│   │   ├── 1_Analyze.py                 # Phân tích món ăn
│   │   ├── 2_Nutrition_DB.py            # Tra cứu dinh dưỡng
│   │   └── 3_Eval_Dashboard.py          # Evaluation dashboard
│   └── utils.py                         # API client helpers
├── data/
│   ├── usda_food_data/                  # USDA FoodData Central (JSON/CSV)
│   ├── vn_food_composition/             # Vietnam Food Composition Table
│   └── images/                          # Ảnh món Việt để train/test
│       ├── train/
│       ├── val/
│       └── test/
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_api_health.py
│   ├── test_rag.py
│   ├── test_cv_model.py
│   ├── test_orchestrator.py
│   └── test_nutrition_integration.py
├── scripts/
│   ├── download_models.sh               # Tải GGUF models
│   ├── ingest_nutrition.py              # Parse + embed USDA/ViFood
│   └── prepare_dataset.py               # Download + preprocess ảnh món Việt
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 8. So sánh với Yêu Cầu JD (Checklist)

### JD mẫu: AI Engineer cần CV + LLM + Cloud

| Yêu cầu | Có trong FoodAI? | Bằng chứng |
|----------|:--:|-----------|
| Python thành thạo | ✅ | FastAPI async + Pydantic + typing toàn project |
| PyTorch / TensorFlow | ✅ | Fine-tune ResNet50, training loop, DataLoader |
| Computer Vision | ✅ | Dataset preparation, augmentation, model eval |
| Generative AI / LLM | ✅ | llama.cpp Qwen2.5, Qwen3.7 Plus, prompt engineering |
| Triển khai CV model trên cloud | ✅ | ONNX export + SageMaker/Vertex AI deploy |
| Quy trình ML/DL | ✅ | Data → train → eval → export → deploy |
| RAG + Vector DB | ✅ | Tự code pipeline + pgvector HNSW |
| Agentic Workflow | ✅ | 4-step orchestration + validate + retry |
| Structured Output | ✅ | Pydantic schema + validation |
| Evaluation Framework | ✅ | RAGAS + custom harness + 50 ảnh test |
| Cost/Latency Optimization | ✅ | Redis cache + model routing |
| Docker/Container | ✅ | Docker Compose full stack |
| LangChain (bonus) | ✅ | Tuần 7: refactor so sánh |

---

## 9. Các Cột Mốc Chính (Milestones)

| Cuối tuần | Deliverable chính | Demo được gì? |
|-----------|-------------------|---------------|
| 2 | CV model phân loại món Việt | `curl POST /predict` upload ảnh → "phở bò" |
| 3 | Nutrition DB search | Query "thịt bò" → top-5 kết quả + dinh dưỡng |
| 4 | RAG pipeline hoàn chỉnh | `POST /nutrition/lookup` → JSON dinh dưỡng |
| 5 | Full agentic pipeline | Upload ảnh → JSON dinh dưỡng + confidence |
| 6 | UI + Eval dashboard | Demo Streamlit cho người khác xem được |
| 7 | Optimized + LangChain | Báo cáo benchmark cost/latency |
| 8 | Cloud deploy + Portfolio | Public URL + GitHub README + blog |

---

## 10. Ghi chú

- **LangChain**: Tự code RAG trước (tuần 3-4), học LangChain sau (tuần 7). Mục tiêu: hiểu cả 2, biết khi nào dùng cái nào.
- **CV model**: Đây là phần nặng nhất với người mới. Mục tiêu thực tế: phân loại được 10-15 món Việt phổ biến, accuracy > 75%. Không cần SOTA.
- **Món Việt differentiator**: Không cần nhận diện 1000 món — 15-20 món phổ biến nhất là đủ để khác biệt với app nước ngoài.
- **Nếu thiếu thời gian**: Có thể rút CV model xuống còn fine-tune nhẹ (5 epoch) + tập trung vào RAG pipeline. CV model là "nice to have" cho JD CV-heavy, RAG pipeline là "must have" cho JD GenAI.
