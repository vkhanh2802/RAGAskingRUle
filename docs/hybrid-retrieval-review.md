# Keyword search và RRF — T2.3

Ngày: 2026-10-08. Migration `005_keyword_search`; keyword query `vi-simple-v1`.
T2.3 hoàn thành về index, ba chế độ retrieval, dedup và provenance. Chất lượng
đáp án và nghiệm thu toàn corpus M2 còn công việc riêng được ghi bên dưới.

## Index và query

- PostgreSQL `simple` + `unaccent` lưu `search_text` và weighted `search_vector`;
  GIN index `chunks_search_vector_gin_idx`. Ranking dùng `ts_rank_cd` với normalization
  32, không phải BM25 hay điểm cosine.
- Document number/title có weight A, heading/article/clauses B, body C. Trigger cập
  nhật khi chunk đổi text/structure/document hoặc document đổi title/number. Delete
  document cascade chunk; FTS không phải một kho dữ liệu tách rời lifecycle.
- Query case-fold, bỏ dấu và chuyển đ thành d; chỉ word lexemes được đưa vào tsquery.
  Stop words bị loại; tối đa 80 terms nối OR để tránh query dài không khớp vì một từ.
  Mã như `1393/QĐ-ĐHCNTT`, `quyet dinh so 159`, `quy dinh 956` constrain keyword
  branch theo số văn bản. `Điều 14` thêm phrase `dieu <-> 14`.
- Article phrase có thể khớp một điều được nhắc trong body, không chỉ article metadata
  của chunk. Đây là lookup lexical, chưa phải bộ lọc cấu trúc/phạm vi áp dụng.
- Hai nhánh dùng chung allowlist, ingestion/publication ready, embedding model/revision/
  fingerprint và chunk quality approved. Keyword-only không gọi embedding weights,
  nhưng vẫn yêu cầu cùng corpus/model fingerprint để so sánh với vector nhất quán.

Snapshot DB thật: 15 registry, 4 ready/11 failed-blocked; 97 chunk/97 unique ID và
97 search vectors không rỗng. `vector` 0.8.7, `unaccent` 1.1; GIN hiện diện. Chạy lại
migration skip đủ 001–005, không thêm bản ghi; 0 run pending/processing và 0 chunk
chưa approved. Coverage/review vẫn như T2.2:
1393 full; 159/790/956 partial; 121 trang preparation còn pending.

## Ba chế độ và hợp nhất

`configs/rag/baseline.json` hiện chọn `hybrid`; có thể override từng request bằng
`retrieval_mode`: `vector`, `keyword`, `hybrid`.

| Tham số | Giá trị |
|---|---:|
| top_k | 5 |
| candidate_k mỗi nhánh | 20 |
| minimum_score dense cosine | 0.55 |
| minimum_keyword_score, chấp nhận lớn hơn ngưỡng | 0 |
| rrf_k | 60 |
| dense_weight / keyword_weight | 1 / 1 |
| generation context_chunks | 2 |

Dense hits dưới ngưỡng bị loại trước fusion. RRF chỉ dùng thứ hạng:

```text
RRF(chunk) = dense_weight / (rrf_k + dense_rank)
           + keyword_weight / (rrf_k + keyword_rank)
```

Nhánh không có chunk không góp điểm. Dedup theo chunk ID cả trong từng nhánh và
giữa hai nhánh; duplicate không tăng điểm. Tie ở fusion được giải theo keyword
rank, dense rank rồi chunk ID. Không cộng trực tiếp cosine với `ts_rank_cd`, không
so điểm keyword/RRF với ngưỡng cosine 0.55.

Mỗi source giữ `score_kind`, `retrieval_branches`, overall `rank`, `dense_rank`,
`keyword_rank`, `dense_score`, `keyword_score`, `rrf_score`. Ví dụ OCR01 top hit
`uit_1393_2023:chunk:0001` có dense rank 3/keyword rank 1; RRF = 1/63 + 1/61
= 0.0322664585. Rank/score branch và full hit nằm trong local `results.jsonl`;
response API cũng serialize các trường này, không cần suy branch từ độ lớn score.

`top_k` là giới hạn retrieval; API sources là context sau giới hạn số chunk/token,
nên có thể ít hơn top_k. Cổng companion full/ready và amendment-in-context vẫn giữ.
Mã văn bản trong query chỉ constrain keyword branch ở T2.3; filter request giống
nhau cho cả hai nhánh thuộc T2.4.

## So sánh trên cùng câu hỏi

Chạy 23 câu: 10 mẫu gốc + 4 controls + 3 OCR + 6 keyword probes. Cùng corpus 97
chunk, config/model pins và top_k5/candidate_k20; 23 query vectors encode một lần
và dùng lại cho vector/hybrid. Run kết thúc `2026-10-08T12:12:45.742583+00:00`;
embedding fingerprint `4ede9feda4e55ce5cd7a7eae73396f6de45877bb5e1e59204ea52fd42ed9d9e0`.

| Chế độ | Document hit@1 | Document hit@2 | Document hit@5 |
|---|---:|---:|---:|
| Vector-only | 15/23 (65.2%) | 16/23 (69.6%) | 23/23 (100%) |
| Keyword-only | 22/23 (95.7%) | 22/23 (95.7%) | 22/23 (95.7%) |
| Hybrid RRF | 22/23 (95.7%) | 22/23 (95.7%) | 23/23 (100%) |

Hit là có ít nhất một tài liệu trong `candidate_document_numbers` ở top-k, không
phải khớp điều khoản hay đủ bộ base + amendment. Bộ này là development smoke có
identifier probes, chưa phải 30 câu gold hoặc held-out evaluation. Vector lượt đầu
có cold-start, hybrid dùng query cache; không dùng latency trong run để kết luận
hybrid nhanh hơn hoặc đo end-to-end inference.

Quan sát cụ thể:

- OCR01–OCR03: vector top1 là790 và1393 vắng top2; keyword/hybrid đưa1393 lên top1
  ở cả3 câu. Context thực trong hybrid API smoke cũng có1393.
- KEY01/KEY02 có dấu/không dấu cho1393 Điều1 trả cùng keyword top chunk0001;
  KEY03/KEY04 cho159 Điều3 trả cùng chunk0005. KEY05 tìm phrase Điều14;
  KEY06 tìm số956 và course codes PET01/PET02. Kết quả có trong CSV69 rows.
- C03 hồi quy: vector top1 đúng159; keyword không có159 trong top5; hybrid có159
  trong top5 nhưng vắng top2. Với context2, đây là mất evidence KLTN quan trọng.
- Q01 đúng tài liệu790 ở cả ba mode, nhưng vector top article14 còn keyword/hybrid
  top article3. Metadata weight và terms OR chung có thể đẩy glossary/điều khác lên;
  document hit không phản ánh lỗi này.

Kết luận chỉ giới hạn ở run: keyword/hybrid cải thiện document hit@1, đặc biệt query
mã văn bản. Chưa chứng minh hybrid tốt hơn về clause relevance, citation support
hay answer accuracy; hybrid vẫn có regression. Chưa tune weights trên held-out.

## Hybrid API smoke và manual review

ASGI TestClient dùng DB/model thật, `verified_quotes`, Qwen2.5-1.5B GGUF CPU:
Rà soát bên dưới do assistant đối chiếu question/response/trace; chưa là review độc lập.

| Câu | HTTP/API status | Kiểm tra thủ công |
|---|---|---|
| OCR01 — cap12 tín chỉ | 200 / answered | Quote thật từ1393 nhưng về miễn học phần Điều23; không trả lời cap12 |
| OCR02 — học phí hè | 200 / insufficient_evidence | `invalid_json`; model không hoàn tất JSON hợp lệ |
| OCR03 — thời hạn miễn học phần | 200 / insufficient_evidence | `unverified_quote`; model nối các đoạn học phí/học hè không liên tiếp, backend chặn |

1393 có trong context3/3 nhưng không có câu nào trong smoke này được manual review
xác nhận trả lời đúng đầy đủ. OCR01 minh họa giới hạn hiện tại: substring/citation
validation bảo đảm quote thật, chưa tự kiểm quote có trả lời câu hỏi. Lỗi relevance
được ghi riêng, không tính status `answered` làm thành công.

Bằng chứng public không chứa toàn văn: `data/manifests/hybrid_api_smoke.csv`,
`hybrid_api_manual_review.csv`. Response/excerpts và model traces ở ignored
`data/processed/hybrid-api-smoke/`.

## Kiểm chứng

- 87 tests pass với `REGULARAG_RUN_DB_TESTS=1`, gồm PostgreSQL integration schema riêng.
- Keyword: accent equivalence, document/article refs, SQL parameters/query operators;
  pending/processing/failed/blocked/quality/revision/fingerprint/allowlist gates.
- FTS: chunk text và document title update refresh index; delete loại kết quả search.
- RRF: common hit, branch scores/ranks, duplicate không tăng điểm, nhánh rỗng và tie.
- Routing: keyword-only không gọi embedder; dense dưới ngưỡng không lọt vào fusion;
  keyword/RRF không bị chặn bởi cosine threshold; API mode/provenance serialization.
- Ruff check/format pass (95 Python files); pip check pass; lock70/70 khớp phiên bản.
- Migration001–005 chạy lại đều skip; DB healthy; PDF/full text/model output còn Git ignore.

Warning duy nhất trong tests là Starlette TestClient dùng `httpx` deprecated, như các
task trước; không có failing test.

## Tái lập và bàn giao

Từ root repository trong `ragschool`, với database và artifact đã được review/index:

```powershell
python scripts/migrate.py
python scripts/compare_retrieval.py
python scripts/run_baseline_samples.py --questions data/manifests/ocr_smoke_questions.csv --retrieval-mode hybrid --output-dir data/processed/hybrid-api-smoke --summary data/manifests/hybrid_api_smoke.csv
$env:REGULARAG_RUN_DB_TESTS = "1"
python -m pytest
```

Comparison summary: `data/manifests/retrieval_comparison.csv` (69 rows). Full question/
query diagnostics/hits và config/metrics: `data/processed/retrieval-comparison/`.
Chạy lại có thể ghi đè run; dùng `--output-dir` và `--summary` mới khi cần giữ trace.
Nếu chưa có source/correction/review đúng hash, thực hiện lại quality gate theo
`docs/structure-ocr-review.md` trước publication.

Tiếp theo T2.4: request metadata filters áp dụng chung hai nhánh; 30 câu development
với đáp án/evidence theo điều khoản và review retrieval thủ công. Theo dõi C03 và
OCR01 như regression cases. Tiếp tục page/table review để đạt toàn corpus M2;
không suy cohort/thời gian hiệu lực từ năm ban hành. Model relevance/output còn là
giới hạn thực tế cho các task generation/evaluation tiếp theo.
