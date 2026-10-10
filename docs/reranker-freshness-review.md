# T3.1 — Reranker và phiên bản nguồn mới nhất

Ngày hoàn tất: **2026-10-09**. T3.1 đạt pipeline, freshness guards và evaluation
trên corpus M2. Generation còn chậm và thường abstain; chưa nghiệm thu M3.

## Cấu hình và luồng thực hiện

- Corpus15 nguồn/307 chunks;19 development gold bindings giữ nguyên.
- Hybrid lấy20 candidates mỗi nhánh, RRF k60/weights1:1; pool rerank tối đa20.
- Reranker CPU `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision
  `1427fd652930e4ba29e8149678df786c240d8825`; batch1/2 threads. Apache-2.0;
  MMARCO có tiếng Việt dịch máy, chưa fine-tune cho quy chế UIT.
- Query–passage pairs dùng title/article/body. Cửa sổ512 tokens/overlap32, chấm
  **mọi cửa sổ**, lấy maximum logit theo chunk. Không truncate đuôi im lặng.
- Logit chỉ dùng thứ tự, không phải confidence hoặc cosine. Giữ score_kind/raw
  dense/keyword/RRF, thêm first_stage_rank/rerank_rank/rerank_score/rerank_windows.
- Top8 retrieval, mục tiêu6 context chunks, toàn ChatML tối đa4096 input tokens;
  Qwen GGUF/output384, prompt `evidence-only-quotes-v9`. Context thực có thể ít
  hơn vì nguồn phù hợp ít hoặc token budget; không padding hay bỏ companion im lặng.
- `reranker.enabled` bật/tắt khi build service. `retrieval_mode` chọn first stage;
  reranker áp dụng cả ba mode nếu bật. Freshness có config riêng, đang bật mặc định.
- `shared-query-refs-v1`: mã văn bản nêu rõ trong câu hỏi constrain **cả dense và
  keyword trước LIMIT**. Amendment được bổ sung qua quan hệ đã kiểm; caller filters
  vẫn tuyệt đối, không tự nới document_ids/type/audience/as_of để thêm nguồn.

## Freshness và nguồn đã kiểm

`document_versions.csv` bind issued_date/signature witness với sourceSHA.
`document_relations.csv` bind updating source, target source khi có trong corpus,
affected article/clause, evidence chunk ID và contentSHA. Metadata được overlay
qua `load_manifest()` và refresh trong lifecycle unchanged; không cần migration
mới hay re-embed. Issued date vẫn khác effective date.

Quan hệ đã kiểm:

| Cập nhật | Văn bản gốc | Phần ảnh hưởng |
|---|---|---|
|1393, ngày29/12/2023|790, ngày28/09/2022|Điều4 khoản3; Điều12 khoản1; Điều14 khoản1 mụcb; Điều23 khoản1|
|513, ngày08/05/2026|412, ngày27/03/2025|Điều1 khoản3; Điều3 khoản1|
|697, ngày12/07/2024|244, ngày22/03/2024|Explicit replaces, nguồn244 ngoài corpus|
|894, ngày29/07/2026|172, ngày08/03/2023|Explicit replaces, nguồn172 ngoài corpus|

Policy chỉ đi theo verified successors của đúng document family. Văn bản mới
nhưng khác domain/đối tượng không tự thay thế nguồn cũ. Clause đã bị sửa không
được đưa vào generation; phần base còn dùng phải có bound amendment evidence
trong context. Metadata latest_document_number/latest_issued_date nối citation
với bản cập nhật, kể cả khi quote từ phần base không đổi.

Catalog nhìn cả blocked/out-of-allowlist versions. Latest không ready/full với
amendment, revision/quality/hash mismatch hoặc bị filters loại thì abstain, không
fallback quy định cũ. Missing companion sau top-k/token budget cũng chặn **trước
generation**. Historical as_of không buộc amendment được ban hành/hiệu lực sau
cutoff; không suy as_of từ năm khóa hay tên file. Source drift đã ghi nhận được
truyền vào metadata refresh và chặn trả lời current từ nguồn đó.

`check_source_freshness.py` đã re-fetch hai trang public Portal và hash15 PDF ngày
09/10/2026: **15/15 vẫn được liệt kê, bytes không đổi**. Snapshot attachment groups,
index hashes và UTC checked_at ở `source_freshness_checks.csv`; đối chiếu các
nhóm P0 không thấy attachment mới hơn thay cho selected sources. Checkpoint này
không kiểm tài liệu nội bộ hoặc mọi nguồn ngoài Portal. API là latest **đã kiểm
trong corpus tại snapshot**, không fetch website mỗi request và không tự xác
nhận legal_status active. Cần kiểm lại attachment dates/relations khi cập nhật nguồn.

Giới hạn bảo thủ: item-level update14.1.b hiện loại toàn clause14.1; unknown
article/clause boundaries cũng không được coi là unchanged. Có thể mất evidence
cho phần liền kề không đổi; cần finer-grained, source-bound views ở giai đoạn sau.

## Evaluation cùng frozen dataset

Hai lượt hoàn chỉnh, mỗi lượt216 rows: development30 ×2 conditions ×3 variants
và12 identifier probes ×3 variants. On/off dùng **cùng frozen hybrid pool**, shared
cached query vectors, warmed models/database. Scope violations/missing companion
context đều0. Gold metrics là retrieval, chưa là answer accuracy.

### Cấu hình cuối:20 candidates/shared document references

| Condition/variant | Gold@1 | Gold@2 | Gold@5 | Complete@2 | Complete@6 trước LLM budget | Stage p50/p95 |
|---|---:|---:|---:|---:|---:|---|
|Scoped vector/off|27/30|30/30|30/30|29/30|30/30|0,086/0,112s|
|Scoped hybrid/off|18/30|28/30|30/30|28/30|30/30|0,120/0,153s|
|Scoped hybrid/on|**29/30**|30/30|30/30|29/30|30/30|**4,653/5,406s**|
|Unfiltered vector/off|25/30|28/30|30/30|27/30|30/30|0,125/0,164s|
|Unfiltered hybrid/off|15/30|19/30|25/30|19/30|25/30|0,186/0,213s|
|Unfiltered hybrid/on|28/30|28/30|30/30|27/30|30/30|9,110/12,203s|

Identifier documenttop1: vector/off12/12, hybrid/off12/12, hybrid/on12/12.
D15/D30 gold lên firstcontext; D23 scoped còn rank2. D06 cần cả signature và
effective clause, không chỉ một chunk hit.

Stage timing gồm SQL/catalog/first stage và reranking, **loại query encoding,
LLM/token budgeting**. Warm query encoding p50/p95:62/99ms. Model-load measurements
trong process này: E5/import23,8s, reranker2,17s; không trộn vào warm stage numbers.

### Trade-off so với lượt30 candidates

Lượt30/keyword-only references: scoped hybrid/on29/30 top1, stage p50/p95
6,336/7,101s; unfiltered27/30 top1,17,130/19,512s. Identifier hybrid/on11/12;
M208 bị dense promote790 dù query nêu112, D06 unfiltered mất1393 khỏi top5.

Đổi sang20 **và** shared reference gate giữ29/30 scoped top1, cải thiện explicit
document constraints và giảm latency. Đây là hai thay đổi đồng thời, không quy
toàn bộ cải thiện cho candidate count. Cấu hình cuối ưu tiên chi phí CPU; model
vẫn chưa có relevance threshold calibrated hay held-out evaluation.

Artifacts: `t3_1_retrieval.csv`/ignored `t3-1-retrieval-v2` là lượt30;
`t3_1_retrieval_20_candidates.csv`/ignored `t3-1-retrieval-20` là lượt cuối.
Lượt đầu aborted ở D06 vì dependency score SQL numeric thành Decimal trong JSON;
đã cast double precision, thêm integration serialization assertion, giữ partial
trace trong ignored `t3-1-retrieval/`.

## Real API/generation smoke và manual review

12 requests ASGI TestClient với PostgreSQL/E5/reranker/Qwen thật:12 HTTP200,
11 generation calls, **1 supported answer** và1 expected stale-filter abstention.

- F01–F04:1393/513 cập nhật ở firstcontext; merged/noncontiguous quote hoặc JSON
  truncated bị từ chối. Không trả cap10/minimum50 từ clause cũ.
- F05:790-only filter loại1393, `latest_excluded_by_filters`; không gọi generation,
 208ms. Đây là pass về abstention, không phải supported answer.
- F06:412 tại01/12/2025, không buộc future513; scope đúng nhưng JSON failure.
- M201: effectiveness quote của S4 bị gắn S1, không trả lời online question; rejected.
- M204: wrong-cohort rows bị bỏ; correct2018/4-year row ở S2. Model copy đúng row
  nhưng gắn S1, backend reject. Không nới validation để biến thành answered.
- M211: model lại quote ISO metadata thay literal source; rejected.
- **M212**: source894/Điều9/PDF8/chunk0017 hỗ trợ30days paperdegree,
 15papercertificate,5digital; quote khớp, latest-issued29/07/2026 và source check đúng.
- D15: gold firstcontext nhưng model paraphrase/missing condition; rejected.
- D30: gold firstcontext nhưng model thêm từ sauJAN02; rejected.

End-to-end p50/p95 **103,908/152,603s**, gồm mixed cold/warm model/generation;
không so với stage p50 như cùng metric. Reranking giảm được cost, nhưng CPU
generation/context/output là bottleneck lớn, chưa đạt interactive UX.

Audit stored answers so với manifest và actual DB chunk hashes/excerpts:0 provenance,
excerpt, scope hoặc latest-anchor mismatch; answered missing-update/quote-mismatch/
old-affected-clause violations0. Chỉ một answered sample nên không suy chất lượng
toàn hệ thống. Manual review do assistant, chưa independent/held-out.

Artifacts: `t3_1_api_smoke_questions.csv`, `t3_1_api_smoke.csv`,
`t3_1_api_manual_review.csv`, `t3_1_api_audit.json`; full trace ignored tại
`data/processed/t3-1-api-smoke/`.

## Quality gate và reproduction

-187 tests pass:88 unit/99 PostgreSQL integration isolated schemas.
- Ruff check/format119 files pass; pip check pass; dependency lock70/70 không đổi.
- Corpus15ready/307unique/307FTS/15unchanged/0unfinished;19gold bindings unchanged,
  `t3_1_publication_snapshot.json`. Migrations001–006 không đổi.
- PDF/raw OCR/model traces vẫn ignored; model weights chỉ ở HF cache.

Chạy từ root với environment `ragschool`, UTF-8 và model cache đã có:

```powershell
python scripts/check_source_freshness.py
python scripts/index_baseline.py
python scripts/evaluate_reranker.py
python scripts/run_baseline_samples.py --questions data/manifests/t3_1_api_smoke_questions.csv --output-dir data/processed/t3-1-api-smoke --summary data/manifests/t3_1_api_smoke.csv --limit 12
python scripts/audit_reranker_samples.py
python scripts/check_corpus_publication.py --output data/manifests/t3_1_publication_snapshot.json
```

Giữ run mới bằng `--output-dir`/`--summary`; reproduction lượt30 dùng
`--candidate-k 30 --document-reference-policy keyword-only-v1`. Offline flags chỉ
bật sau khi model pinned đã cache. Thay config reranker/freshness cần restart service.

## Tiếp theo

T3.2: giảm copy/paraphrase và source-ID errors bằng source-bound passage/span
selection; kiểm clause/conditions support, nhất là513/851 và table rows. Đo lại
generation latency/resource lifetime, context budget và output policy trên cùng
failure cases; không nới exact-quote checks. T3.3 xử lý ambiguity/cohort/program
và clarification.45 excluded pages/832 omitted regions vẫn ngoài supported scope.
