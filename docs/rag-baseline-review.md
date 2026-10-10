# Rà soát retrieval và generation baseline — T1.5

Ngày kiểm chứng: 2026-10-08. Đây là bộ câu hỏi development/smoke, chưa phải held-out
evaluation hay cam kết độ chính xác của hệ thống.

Các thông số batch/thread trong báo cáo này là snapshot T1.5. T2.1 sau đó giảm runtime
embedding xuống batch 1 / 2 threads; model/revision/window/pooling fingerprint không
đổi. Config hiện tại và lịch sử ingest nằm trong `docs/ingestion-lifecycle-review.md`.

## Cấu hình cuối

| Thành phần | Cấu hình |
|---|---|
| Embedding | `intfloat/multilingual-e5-small`, 384 chiều, CPU, batch 8 |
| Embedding revision | `614241f622f53c4eeff9890bdc4f31cfecc418b3` |
| Chunk embedding | Cửa sổ không quá 512 token, overlap 32, mean pooling rồi chuẩn hóa |
| Prefix E5 | `query: ` / `passage: ` |
| Retrieval | pgvector cosine, HNSW, top-k 5, ngưỡng score 0.55 chưa calibration |
| Corpus ready | 159, 790, 956; 3 tài liệu / 46 chunk |
| LLM | `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, Q4_K_M, llama.cpp CPU, 4 threads |
| LLM revision | `91cad51170dc346986eccefdc2dd33a9da36ead9` |
| GGUF | `qwen2.5-1.5b-instruct-q4_k_m.gguf`, 1.117.320.736 byte |
| Context | Tối đa 2 chunk; cửa sổ đoạn liên tiếp phù hợp câu hỏi và đoạn lân cận |
| Token budget | Toàn bộ ChatML tối đa 3072 input token, 384 output token |
| Response policy | `verified_quotes`; backend chỉ dựng answer từ đoạn trích đã xác thực |
| Prompt version | `evidence-only-quotes-v8` |

Config đầy đủ nằm tại `configs/rag/baseline.json`. Fingerprint của embedding gồm
model/revision, prefix, cửa sổ và pooling; retrieval loại vector không cùng fingerprint.
Pipeline kiểm document/chunk identity và content hash trước khi thay index trong transaction.
Chạy lại index không nhân đôi chunk.

BGE-M3 vẫn là tokenizer chunking của T1.4. Embedding dùng E5-small vì khi Docker
khởi động chỉ còn khoảng 0,2–0,8 GB RAM trống; không có phép đo so sánh chất lượng
E5 với BGE-M3 trong phiên này. Toàn bộ model chạy local, không có phí API.

## Mười câu hỏi gốc

`data/manifests/rag_baseline_samples.csv` ghi kết quả cuối. Cả 10 câu đi qua endpoint
FastAPI với database và model thật; 10/10 trả HTTP 200, gọi generator và có nguồn truy vết.
Context của 10/10 chứa một tài liệu dự kiến trong manifest câu hỏi. Đây chỉ là
**document-level hit**, không phải recall theo điều khoản hay answer accuracy.

| Kết quả | Số câu | Câu |
|---|---:|---|
| `insufficient_evidence`: thiếu amendment 1393 | 8 | Q01, Q02, Q04, Q06–Q10 |
| `insufficient_evidence`: model không hoàn thành JSON | 1 | Q05 |
| `insufficient_evidence`: schema không hợp lệ | 1 | Q03 |
| `answered` | 0 | — |

Không coi 10 response HTTP 200 là 10 đáp án đúng. Văn bản 790 mới được index như
nguồn kỹ thuật; phần cập nhật 1393 còn là PDF scan. Backend chủ động chặn kết luận
dựa trên 790 khi companion chưa ready. Q09/Q10 còn cần clarification về khóa/chương
trình; quote-mode hiện chưa tự phân loại clarification, là việc của T2.4/T3.3.

Latency end-to-end của lần chạy cuối khoảng 5,3–51,0 giây/câu, gồm cold-start ở Q01.
Không dùng con số này làm benchmark giữa các model hoặc thiết bị.

## Bốn câu kiểm soát bổ sung

`data/manifests/baseline_control_questions.csv` và
`data/manifests/rag_baseline_controls.csv` là bộ bổ sung, không thay thế mười câu gốc.

| Câu | Kết quả cuối | Rà soát thủ công |
|---|---|---|
| C01 — số sinh viên/đề tài KLTN trong 159 | `insufficient_evidence` | Dense retrieval ưu tiên 790, không đưa 159 vào context; lỗi retrieval cần hybrid/filter |
| C02 — PET01 tiên quyết môn nào | `insufficient_evidence`, `unverified_quote` | Model sửa/paraphrase đoạn trích; backend chặn |
| C03 — thời gian KLTN thông thường | `answered` | Đoạn nguyên văn nêu 1 học kỳ chính (15 tuần), đúng Điều 3 khoản 2 của 159, PDF 1–2, source `[S1]` |
| C04 — văn bằng cử nhân ngoại ngữ tiếng Pháp | `insufficient_evidence`, `unverified_quote` | Đoạn model chọn không khớp context; backend chặn |

C03 còn được kiểm lại qua Uvicorn và HTTP thật ở `127.0.0.1:8765`: `/health` và
`POST /api/v1/ask` cùng trả 200, answer trích đúng thời gian KLTN và citation `[S1]`.
Script smoke tự dừng server sau khi kiểm tra.

## Các lần thử thất bại được giữ lại

- SmolLM2-135M và Qwen2.5-0.5B sinh output không đúng JSON/citation.
- Qwen GGUF sinh tự do từng đảo nghĩa điều kiện và nhầm Điều 3 thành Điều 4.
- Grammar regex dùng `.*` từng cho phép text ngoài JSON bị xem là phần chuỗi answer;
  schema cuối dùng quote object với kiểu JSON chuẩn.
- Quote-only chưa focus từng trả một đoạn có thật nhưng không trả lời câu hỏi C04;
  xem `data/manifests/rag_baseline_additional_probe.csv` với manual verdict.

Những lỗi này là lý do baseline cuối chỉ cho model **chọn bằng chứng**, kiểm quote có
trong context (chỉ bỏ khác biệt khoảng trắng), rồi để backend dựng answer. Kiểm quote
ngăn nội dung được sửa/bịa; nó vẫn không tự chứng minh relevance, đủ ngoại lệ hay
phạm vi áp dụng. Các điểm đó cần evaluation thủ công và các task tiếp theo.

## Artifact và tái lập

Quality gate cuối: Ruff check/format pass; 36 tests pass (32 unit và 4 integration
PostgreSQL), `pip check` pass, lock 70/70 khớp environment. Integration dùng schema
riêng và xóa sau test; database corpus thật vẫn giữ 3 tài liệu/46 chunk.

- Public: config, script, thống kê CSV và báo cáo này; không có toàn văn PDF.
- Local, bị Git ignore: `data/processed/rag-baseline-v8/`,
  `data/processed/rag-controls-v8/`, `data/processed/rag-http-smoke.json`.
- Mỗi run lưu config, phiên bản package, fingerprint, response, nguồn, output model
  và lỗi; các run/probe cũ còn dưới `data/processed/`.

```powershell
conda activate ragschool
docker compose up -d db
python scripts/migrate.py
python scripts/index_baseline.py
python scripts/run_baseline_samples.py
python scripts/run_baseline_samples.py --questions data/manifests/baseline_control_questions.csv --output-dir data/processed/rag-controls-v8 --summary data/manifests/rag_baseline_controls.csv
python scripts/smoke_http.py
```

T1.5/M1 đạt tiêu chí luồng kỹ thuật, provenance và ghi cả ví dụ đúng/thất bại.
Chất lượng câu trả lời tổng quát còn hạn chế. Ưu tiên tiếp theo: T2.1 ingestion
lifecycle, OCR 1393 ở T2.2, hybrid RRF và metadata filtering.
