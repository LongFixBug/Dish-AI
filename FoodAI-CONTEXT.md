# FoodAI — Project Context (CV target: Fresher AI Engineer VN)

> File này là "bộ nhớ dài hạn" cho OpenCode. Khi mở OpenCode ở bất kỳ client nào
> (VSCode, JetBrains, terminal), chỉ cần nói "đọc FoodAI-CONTEXT.md rồi tiếp tục"
> để agent nắm lại toàn bộ context mà không cần nói lại từ đầu.

## 1. Mục tiêu dự án

- **Mục đích**: Project cá nhân để bỏ vào CV apply vị trí **Fresher AI Engineer** tại Việt Nam.
- **Không phải** target: Mobile Developer, Fullstack, ML Engineer (train model), MLOps.
- **Định vị**: Applied AI Engineer / GenAI Engineer — dùng LLM + RAG + agent để giải bài toán thực tế.

## 2. Ý tưởng sản phẩm

- App mobile chụp ảnh món ăn → AI nhận diện món + liệt kê thành phần (ingredient) + ước lượng gram.
- Từ đó truy xuất dinh dưỡng từng thành phần (calo, đạm, chất béo, carb, chất xơ, vitamin, khoáng chất).
- Tổng hợp thành tổng dinh dưỡng của cả món ăn.
- Đặc biệt tối ưu cho **món ăn Việt** (phở, bún, bánh xèo...) — đây là differentiator với MyFitnessPal/Lose It!.

## 3. Đã chốt / loại bỏ (decisions)

### Giữ
- Dùng **Gemini Vision API** (cloud) cho nhận diện ảnh → không train model.
- Kết hợp **RAG** với USDA FoodData Central + Vietnam Food Composition Table để tra nutrition chính xác, giảm hallucination của LLM.
- **Structured output** (Zod/Pydantic schema) cho response.
- **Agentic workflow**: nhiều bước (identify → per-ingredient lookup → aggregate → validate → retry nếu delta > threshold).
- **Eval harness**: 50 ảnh test, đo accuracy/schema compliance/hallucination rate.
- **Cost/latency optimization**: cache popular dishes, model routing.
- Backend Python + FastAPI (AI Engineer VN bắt buộc Python).

### Loại bỏ (không làm trong MVP)
- On-device offline model (phone không đủ RAM, model nhẹ nhận diện món Việt kém).
- Tự train/fine-tune model (mất 2-3 tháng, cần GPU, không fit timeline fresher).
- Chỉ wrap Gemini API suông (interviewer AI co không đánh giá cao, ai cũng làm được).
- Nutrition do LLM tự sinh (hallucinate) — bắt buộc đối chiếu database chính quyền.

## 4. Kiến trúc dự kiến

```
App mobile (Expo/Flutter - làm sau)
        │
        │  upload ảnh
        ▼
┌─────────────────────────────────────┐
│  Backend Python + FastAPI           │
│  ┌───────────────────────────────┐  │
│  │ Agentic workflow (LangGraph/   │  │
│  │   manual orchestration)        │  │
│  │  Agent 1: identify dish +      │  │
│  │          ingredients + gram    │  │
│  │  Agent 2: RAG lookup nutrition │  │
│  │           per ingredient       │  │
│  │  Step 3: Python math (gram x per_gram) = totals   │  │
│  │  Agent 4: LLM viết lời giải thích │  │
│  │  → retry Agent 1 nếu thiếu ingredient│  │
│  └───────────────────────────────┘  │
│                                     │
│  ┌────────────┐  ┌──────────────┐   │
│  │ pgvector   │  │   Redis      │   │
│  │ (USDA +    │  │ (cache热血 popular │
│  │  ViFood    │  │   dishes)    │   │
│  │  embed)    │  │              │   │
│  └────────────┘  └──────────────┘   │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ Gemini Vision API (cloud)     │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

## 5. 6 mảng AI phải chứng minh (core CV claims)

| # | Mảng | Implement | Nói gì trong CV |
|---|------|-----------|-----------------|
| 1 | **RAG** | pgvector + USDA/ViFood embedding | "RAG pipeline giảm hallucination bằng đối chiếu nutrition DB chính quyền" |
| 2 | **Structured output** | Pydantic schema + Gemini response_schema | "0 crash rate với schema-validated LLM output" |
| 3 | **Agentic workflow** | LangGraph hoặc manual orchestration | "Multi-step pipeline: Vision → RAG → Python math (không LLM tính toán) → LLM giải thích" |
| 4 | **Hallucination mitigation** | LLM không làm toán → không thể bịa số; confidence dựa trên % ingredient tìm thấy trong DB | "Nutrition được tính bằng code, không qua LLM; confidence score phản ánh độ phủ DB" |
| 5 | **Eval dashboard** | Streamlit/Next.js, 50 test images, metrics | "Eval harness đo accuracy/latency/cost, so sánh Gemini vs GPT-4o" |
| 6 | **Cost/latency opt** | Redis cache + model routing (cheap identify, expensive aggregate) | "Cache + model routing giảm 40% API cost" |

## 6. Target công ty (Fresher AI Engineer VN)

| Ưu tiên | Công ty | Ghi chú |
|---------|---------|---------|
| 1 | **Aitomatic** | GenAI/RAG focus, tuyển fresher nhiều |
| 2 | **FPT AI** | LLM team mở rộng, fresher-friendly |
| 3 | **VinAI JFE program** | program đào tạo, cạnh tranh nhưng fit |
| 4 | **Manabie** | edu AI dùng LLM, tuyển fresher |
| 5 | **Kilo / ProtonX** | startup, AI năm 1-2 kinh nghiệm accept |

Không target (cần kinh nghiệm/specialty): VinBigdata (CV model), Trusting Social (credit+SQL), VNG Zalo AI (cạnh tranh cao).

## 7. Roadmap build (8-10 tuần)

| Tuần | Milestone | Deliverable |
|------|-----------|-------------|
| 1-2 | Setup: repo, Docker, FastAPI skeleton, Gemini API key, pgvector | Hello world API |
| 3 | RAG: ingest USDA FoodData Central vào pgvector, embedding | Query ingredient → nutrition |
| 4 | Agentic workflow: Agent 1 identify + Agent 2 RAG lookup | End-to-end 1 ảnh → JSON nutrition |
| 5-6 | Aggregate + validate (sum check) + retry logic + confidence | Full agentic pipeline |
| 7 | Eval harness: 50 ảnh test, metrics, dashboard Streamlit | Eval report |
| 8 | Cost/latency: Redis cache + model routing | Optimization report |
| 9 | Hallucination mitigation polish + writeup | Blog + README |
| 10 | App mobile MVP (Expo) thin-client + video demo | CV-ready |

## 8. Câu hỏi còn mở

- [ ] Background người dùng: Python có cứu không? (AI Engineer VN bắt buộc Python)
- [ ] Tiếng Anh đọc paper: trình độ nào?
- [ ] GPU roadmap: có Kaggle/Colab/Lambda Cloud không?
- [ ] Timeline/deadline: apply khi nào?

## 9. Cách dùng file này

Khi mở OpenCode ở VSCode/JetBrains/terminal mới:
```
đọc FoodAI-CONTEXT.md rồi tiếp tục [câu hỏi của bạn]
```

Agent sẽ nắm: mục tiêu, stack, decisions, roadmap, target công ty → trả lời liền không cần nói lại.