# Môi trường phát triển

## Yêu cầu

- Miniconda hoặc Anaconda.
- Docker Desktop với Linux containers.
- Các lệnh bên dưới chạy từ thư mục gốc của repository.

## Tạo môi trường

```powershell
conda env create -f environment.yml
conda activate ragschool
```

Environment dùng Python 3.12. Dependency trực tiếp được khai báo trong
`pyproject.toml`; toàn bộ phiên bản đã cài được khóa trong `requirements.lock`.
Lock CPU cho Windows/Python 3.12 có feed wheel upstream của PyTorch và llama.cpp;
model weights được tải riêng vào Hugging Face cache, revision nằm trong config.

Nếu environment đã tồn tại:

```powershell
conda env update -n ragschool -f environment.yml
conda activate ragschool
```

## Chạy database

```powershell
docker compose up -d db
docker compose ps
```

Lần khởi tạo đầu, `scripts/db/init.sql` tạo extension `vector`. Dữ liệu PostgreSQL
được giữ trong Docker volume `regularag_postgres_data`.

## Chạy API

```powershell
python -m uvicorn regularag.main:app --reload
```

Kiểm tra:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Kết quả đạt yêu cầu có `status: ok`, tên database, phiên bản PostgreSQL và phiên
bản pgvector. Nếu database chưa chạy hoặc thiếu extension, endpoint trả HTTP 503
với `status: degraded` và không để lộ connection string.

## Cấu hình

Ứng dụng đọc biến môi trường có prefix `REGULARAG_`. Giá trị phát triển mẫu nằm
trong `.env.example`; file `.env` thật bị loại khỏi Git. Các giá trị PostgreSQL
trong file mẫu chỉ dùng cho local development, không dùng cho production.

## Quality gate

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest
python scripts/check_environment.py
python -m pip check
```

Kiểm cả integration test trên PostgreSQL, với schema riêng được xóa sau mỗi test:

```powershell
$env:REGULARAG_RUN_DB_TESTS = "1"
python -m pytest
Remove-Item Env:\REGULARAG_RUN_DB_TESTS
```

## Parsing baseline

Tokenizer BGE-M3 được khóa theo commit trong `configs/ingestion/baseline.json`. Lần
chạy đầu cần kết nối đến Hugging Face để tải tokenizer; không cần PyTorch vì bước này
chỉ token hóa text.

```powershell
python scripts/parse_baseline.py
python scripts/validate_baseline.py
```

Pipeline kiểm SHA-256 nguồn theo manifest, chỉ parse các PDF có `pdf_type=text`, và
ghi artifact vào `data/processed/baseline/`. Thư mục output chứa toàn văn nên bị loại
khỏi Git. Thống kê không chứa toàn văn được ghi tại
`data/manifests/baseline_parse_summary.csv`.

## Index và hỏi đáp baseline

Sau parsing và khi database healthy:

```powershell
python scripts/migrate.py
python scripts/index_baseline.py
```

Indexer dùng allowlist trong `configs/rag/baseline.json`, hiện đủ15 nguồn sauM2;
mặc định đọc `data/processed/m2-publication/`, artifact/review đúng hash cần có sẵn. Vector384 chiều của
E5-small lưu cùng model revision và embedding fingerprint.
Re-index đi qua lifecycle theo từng tài liệu, không tạo duplicate và có audit run.

Lần đầu cần mạng để tải E5-small, pinned mmarco-mMiniLMv2 reranker và Qwen2.5-1.5B
GGUF Q4_K_M. Embedding/reranker dùng batch1/2CPUthreads; generation dùng4threads,
một worker API vàserialized inference. Sau khi cache đủ mới bật HF/Transformers offline.
Có thể dùng HTTP download khi Xet
không hoạt động trong môi trường local:

```powershell
$env:HF_HUB_DISABLE_XET = "1"
python -m uvicorn regularag.main:app --host 127.0.0.1 --port 8000
```

Hỏi ở một terminal khác đã activate `ragschool`:

```powershell
$body = @{ question = "Thời gian thực hiện KLTN thông thường là mấy học kỳ chính và bao nhiêu tuần?" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/ask -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

Response gồm `status`, `answer`, nguồn/trang/đoạn trích, score, prompt version,
`response_policy`, `retrieval_mode`, token count và failure reason. Với `verified_quotes`,
answer chỉ chứa đoạn nguyên văn do backend kiểm lại; citation lấy metadata từ database.
Câu trả lời dựa trên base bị abstain nếu applicable companion chưa full/ready hoặc
vắngcontext. T3.1 còn loại affectedoldclauses và trả latestissued/rerank provenance;
explicit historicalas_of không buộc futureamendment. Chi tiếtT3.1 ởphần dưới.

Lưu mười kết quả mẫu hoặc chạy smoke qua HTTP thật:

```powershell
python scripts/run_baseline_samples.py
python scripts/smoke_http.py
```

`run_baseline_samples.py` dùng ASGI TestClient với model/database thật; config và
toàn văn output nằm trong `data/processed/rag-baseline-v8/` bị Git ignore. CSV tóm tắt
nằm trong `data/manifests/rag_baseline_samples.csv`. `smoke_http.py` tạo server tạm trên
port 8765 và tự dừng. Kết quả đúng/thất bại cùng giới hạn nằm tại
`docs/rag-baseline-review.md`.

Nếu chạy bằng Conda wrapper trong PowerShell thay vì activate:

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
conda run --no-capture-output -n ragschool python scripts/run_baseline_samples.py
```

Cấu hình UTF-8 này tránh lỗi stdout Unicode của `conda run` với code page cp1252.

## Ingestion lifecycle — T2.1

Áp dụng migration rồi ingest PDF từ file hoặc thư mục:

```powershell
python scripts/migrate.py
python scripts/ingest.py ingest data/raw/uit/p0 --report data/manifests/ingestion_lifecycle.csv
python scripts/ingest.py ingest data/raw/uit/p0/159-qd-dhcntt_05-03-2024_khoa-luan-tot-nghiep.pdf
```

Nguồn được đối chiếu với `local_path` trong `data/manifests/documents.csv`. PDF chưa
đăng ký ghi lỗi riêng; nguồn scan/chưa được duyệt cũng có run failed riêng. Thư mục được
duyệt đệ quy và file tốt vẫn xử lý sau file hỏng. Mã thoát: 0 hoàn tất, 1 có lỗi từng
tài liệu, 2 lỗi config/database. Corpus P0 hiện trả 1 vì 11 file còn chờ quality review.
Progress ghi vào stderr; stdout là JSON. `--report` lưu CSV sau từng tài liệu hoàn tất.

Xem trạng thái hoặc lịch sử, không tải embedding weights:

```powershell
python scripts/ingest.py status
python scripts/ingest.py history --document-id uit_159_2024
```

Cập nhật nguồn đã đăng ký: cập nhật SHA-256/metadata có bằng chứng trong manifest rồi
ingest file mới với `--document-id` của tài liệu. `--force` buộc parse/embed lại khi nguồn
và config trùng; SHA-256 vẫn phải khớp manifest. Global options đứng trước subcommand:

```powershell
python scripts/ingest.py --config configs/rag/baseline.json ingest path/to/updated.pdf --document-id DOCUMENT_ID
python scripts/ingest.py ingest data/raw/uit/p0/159-qd-dhcntt_05-03-2024_khoa-luan-tot-nghiep.pdf --force
python scripts/ingest.py delete DOCUMENT_ID
```

Delete xóa database document/chunk và giữ audit history. Update lỗi bị chặn khỏi search;
retry thành công mới xuất bản lại. Nếu worker bị ngắt, lần ingest/delete tiếp theo sở hữu
advisory lock sẽ đóng run cũ thành interrupted.

Artifact từng lần parse nằm dưới `data/processed/ingestion-runs/<run_id>/<document_id>/`.
Chunk lưu FK đến run tạo nó; run unchanged trỏ lại artifact trước. `data/processed/` vẫn
bị Git ignore. Kết quả corpus và kiểm thử nằm trong `docs/ingestion-lifecycle-review.md`.

Sau khi model đã cache, có thể chạy ingest offline:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
python scripts/ingest.py ingest data/raw/uit/p0
```

## OCR và chunking cấu trúc — T2.2

`environment.yml` thêm Tesseract 5.5.2 với traineddata vie/eng. CLI ingest mặc định
`configs/ingestion/structured.json`; baseline cũ dùng global option
`--ingestion-config configs/ingestion/baseline.json` trước subcommand.

```powershell
python scripts/ocr_probe.py --document-id uit_1393_2023
python scripts/prepare_structured.py --output-dir data/processed/structured-final
python scripts/export_page_review.py --input-dir data/processed/structured-final
python scripts/validate_structured.py --input-dir data/processed/structured-final
```

Preparation lưu pages/candidate chunks/chunks publishable riêng; giữ native/raw OCR,
render/TSV/hash, post-edit, confidence, lề đã bỏ và review status. `page_reviews.csv`
bind quyết định bằng source/cleaned-text hash. Pending không auto ready.
`--ignore-page-reviews` tạo candidate để xem lại khi parser/cleaning đổi hash.

1393 có post-edit đối chiếu ảnh ở `data/processed/ocr-corrections/`; clone chưa có
post-edit/review đúng hash cần review lại. TạiT2.2 indexer đọc structural-final;
hiện mặc định m2-publication và dùng lifecycle. Source API thêm chapter/article/clauses/extraction;
warnings báo coverage partial và amendment không có trong context.

```powershell
python scripts/ingest.py ingest data/raw/uit/p0 --report data/manifests/structural_ingestion.csv
python scripts/ingest.py status --document-id uit_1393_2023
python scripts/run_baseline_samples.py --questions data/manifests/ocr_smoke_questions.csv --output-dir data/processed/ocr-api-smoke --summary data/manifests/ocr_api_smoke.csv
```

Hiện 4 document ready/97 chunk; batch thư mục vẫn exit 1 do 11 nguồn chưa được duyệt.
Companion phải full/ready; có trong DB nhưng vắng context vẫn khiến base answer bị chặn.
Kết quả và giới hạn: `docs/structure-ocr-review.md`.

## Keyword/hybrid retrieval — T2.3

Migration005 thêm extension `unaccent`, weighted `simple` FTS và GIN, backfill chunk
hiện có. Trigger refresh khi text/structure hoặc document title/number đổi; delete
chunk xóa entry khỏi cùng index. Ranking `ts_rank_cd` không phải BM25.

Config default `retrieval.mode="hybrid"`; API nhận override `vector`, `keyword`,
`hybrid`. Ví dụ lookup mã1393 và số điều:

```powershell
$body = @{
    question = "1393/QĐ-ĐHCNTT Điều 1 học kỳ hè tối đa bao nhiêu tín chỉ?"
    retrieval_mode = "keyword"
    top_k = 5
} | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/ask -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

Keyword-only không gọi embedder. Cả hai nhánh giữ allowlist/ready/approved và model
revision/fingerprint gates. TạiT2.3 query mã chỉ constrain keyword; hiệnT3.1
`shared-query-refs-v1` constrain cảdense/keyword trướcLIMIT. Request metadatafilters
chung hai nhánh xem phầnT2.4. Article phrase có thể khớp reference
trong body, không bảo đảm passage chính là điều cần trả lời.

Candidate20 mỗi nhánh; RRF k60/weights1:1, dedup chunk ID; dense cosine>=0.55 áp trước
fusion, keyword>0. Source response thêm `score_kind`, `retrieval_branches`, `rank`,
`dense_rank`, `keyword_rank`, `dense_score`, `keyword_score`, `rrf_score`. Các thang
score khác nhau không cộng trực tiếp hay dùng cùng threshold. API trả context sau
budget (hiện tối đa6 chunk/4096inputtokens), không nhất thiết trả toàn bộ top_k candidates.

So sánh23 câu cố định trên ba mode và ghi hybrid API smoke:

```powershell
python scripts/migrate.py
python scripts/compare_retrieval.py
python scripts/run_baseline_samples.py --questions data/manifests/ocr_smoke_questions.csv --retrieval-mode hybrid --output-dir data/processed/hybrid-api-smoke --summary data/manifests/hybrid_api_smoke.csv
```

`compare_retrieval.py` dùng chung query vector cho vector/hybrid, lưu69 rows vào
`data/manifests/retrieval_comparison.csv`; full hits/diagnostics/config/metrics vào
ignored `data/processed/retrieval-comparison/`. Có `--questions` lặp lại để đổi bộ,
`--output-dir`/`--summary` để giữ các run riêng. Query cache/cold-start khác nhau,
không dùng latency của run này làm benchmark giữa mode.

`run_baseline_samples.py --retrieval-mode` hỗ trợ đủ ba mode. Model quote có thể
không liên quan dù nguồn đúng; `answered` không thay manual relevance review.
Kết quả và regression: `docs/hybrid-retrieval-review.md`.

## Metadata filters và development30 — T2.4

Migration006 thêm typed metadata/date/cohort columns, backfill và trigger mỗi khi
document metadata đổi. Hai nhánh dùng cùng filter SQL trước ranking/LIMIT/RRF.
API có optional `filters`; response có `applied_filters` và scope/legal_status của source.

```powershell
$body = @{
    question = "Thời gian thực hiện KLTN thông thường là bao nhiêu tuần?"
    retrieval_mode = "hybrid"
    filters = @{
        domains = @("graduation_thesis")
        applies_to = @("undergraduate_regular")
        document_types = @("regulation")
        as_of = "2026-10-08"
    }
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/v1/ask -Method Post -ContentType "application/json; charset=utf-8" -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

Filters: `document_ids`, `domains`, `document_types`, `applies_to` là lists; optional
`cohort_year` integer1980–2100 và `as_of` ISO date. OR trong list/AND giữa fields;
empty/absent không thêm restriction. Audience exact tags không tự inherit.
Unknown nested fields/invalid values trả422; filter IDs vẫn giao eligible allowlist.

Ngày phải có source evidence;790 chỉ ghi học kỳ nên không khớp as_of. API không tự
coi legal_status unknown là current, trả source/caveat tương ứng. Khi lọc cohort,
nguồn chưa có evidence-bound bounds bị loại; không suy year từ title/issued date.
`load_manifest` đọc optional `cohort_scopes.csv` cạnh manifest, chỉ dùng row đúng sourceSHA.
Hiện956 có cohort_from2026; thiếu/stale review trở lại unknown.

Review và chạy development evaluation:

```powershell
python scripts/migrate.py
python scripts/index_baseline.py
python scripts/export_development_evidence.py
python scripts/evaluate_development.py
```

`data/manifests/development_questions.csv` có30 câu/đáp án tham chiếu/evidence locator/
filters/paraphrase groups. `development_evidence.json` bind19 chunk với source/content
hashes/pages, canonical dataset hash không nhạy LF/CRLF. Reference do assistant soạn
sau source read, chưa independent human/held-out review.

Nếu đổi câu hỏi/reference/evidence, đối chiếu lại nguồn rồi chạy
`python scripts/build_development_evidence.py`; không auto-rebind để vượt drift gate.
Full evidence export/hits ở ignored `data/processed/development-evidence/` và
`development-retrieval/`. CSV180 results ở `data/manifests/development_retrieval.csv`,
manual review30 ở `development_manual_review.csv`; `--output-dir`/`--summary` giữ run mới.

So sánh3 modes có/không có caller-provided filters, không tự suy filters từ question.
Đo gold-chunk hit và complete evidence, chưa là answer accuracy; trongrunT2.4
vector+filter goldtop1 tốt hơn hybrid-off. Báo cáo: `docs/metadata-development-review.md`.
M2 đã publication15 nguồn; snapshot và phạm vi cònexcluded xem phần sau.

## Corpus publication — M2

Sau visualreview, explicit decisions ở `data/manifests/m2_*_page_decisions.csv` và
full/sparse post-edits ở ignored `data/processed/m2-reviewed/`. Helpers:
`export_review_bundles.py` chỉ xuất pendingtemplate, `apply_review_plan.py` chỉ áp
edits do reviewer chỉ định; `bind_page_reviews.py` validate hash snapshot trước sửa
manifest/correction. Không auto-approve confidence.

```powershell
python scripts/prepare_structured.py --output-dir data/processed/m2-publication
python scripts/validate_structured.py --input-dir data/processed/m2-publication --inventory data/manifests/m2_chunk_inventory.csv
python scripts/index_baseline.py
python scripts/index_baseline.py
python scripts/check_corpus_publication.py
python scripts/evaluate_development.py --output-dir data/processed/m2-development-retrieval --summary data/manifests/m2_development_retrieval.csv
python scripts/compare_retrieval.py --questions data/manifests/m2_corpus_probe_questions.csv --output-dir data/processed/m2-corpus-probes --summary data/manifests/m2_corpus_retrieval.csv
```

Snapshot15ready/307unique/307FTS/15unchanged/0unfinished.103approved/40native/45excluded/
0pending pages. Scriptcheck cũng kiểm actualPDF/chunk hashes và19goldbindings không đổi.
Clone thiếu correction/review đúnghash phải review lại trước chạypublication.

`source_metadata_reviews.csv` cạnhmanifest bổ sungscope/date có evidence đúngsourceSHA;
851 start01September2024 khácissueddate. Source audiences có thể chứa nhiều exacttags
phân tách`;`, membership không tựinherit. API source có `metadata_note` và
`omitted_layout_pdf_pages`;832 partial dùbody3/5 được giữ. Docfilter chưa row/clausefilter.

API smoke dùng questionsCSV có optional `filters_json`:

```powershell
python scripts/run_baseline_samples.py --questions data/manifests/m2_api_smoke_questions.csv --retrieval-mode hybrid --output-dir data/processed/m2-filtered-api-smoke --summary data/manifests/m2_filtered_api_smoke.csv
```

M2 smoke M204 answered quote sai2012thay2018; nhữngcase khác schema/quote/JSONfailure.
Giữ manualreview/trace, không coi answered hoặc documenthit làaccuracy. M2 report
`docs/m2-corpus-review.md`; T3.1 follow-up xem dưới. HTTPsmoke tựdừng; chạy Uvicorn để cóserver.

## Reranker và document freshness — T3.1

Baseline mặc định20candidates/top8/context6/maxinput4096, reranker CPU pinned theo
revision trongconfig. `reranker.enabled=false` bỏCE nhưng vẫn giữfreshness nếu
`freshness.enabled=true`. Config đượcload khi buildservice; restartAPI khi đổi.
`retrieval_mode=vector` chỉ đổi firststage, không tự tắt reranker.

Source-date/relationship overlays cạnhmanifest: `document_versions.csv` và
`document_relations.csv`, boundsource/content hashes. Metadata được refresh qua
unchanged lifecycle; không cần migration mới/re-embed. Dates không suy từtitle.
790→1393/412→513 cần verifiedupdate evidence; affectedoldclauses bị loại. Companion
được reserve; filters hoặc tokenbudget làm mấtlatest evidence thìabstain trướcgeneration.
`as_of` là explicit historicalcutoff, không suy từnămcohort. Ngày phát hành khácngày hiệu lực.

Recheck publicportal/PDFhashes rồi refresh metadata và đánh giá:

```powershell
python scripts/check_source_freshness.py
python scripts/index_baseline.py
python scripts/evaluate_reranker.py
python scripts/run_baseline_samples.py --questions data/manifests/t3_1_api_smoke_questions.csv --output-dir data/processed/t3-1-api-smoke --summary data/manifests/t3_1_api_smoke.csv --limit 12
python scripts/audit_reranker_samples.py
python scripts/check_corpus_publication.py --output data/manifests/t3_1_publication_snapshot.json
```

Checker lưu attachmentgroups/indexhashes/UTC timestamps trong
`source_freshness_checks.csv`. Source changed/notlisted khiếnchecker exit1; sau
metadata refresh freshness chặnnguồn đó. Attachmentdates/relations mới phải review;
hash unchanged khôngtự chứng minh toànwebsite khôngcó văn bảnmới. APIlatest nghĩa
verified corpus/snapshot; khôngnetworkcheck mỗiask hoặc tựconfirm legalactive.

API thêm `reranker_model`, `reranker_revision`, `freshness_policy`,
`query_document_codes`; sources thêm issued_date/source_checked_at/source_check_status,
latest_document_number/latest_issued_date, required_update_chunk_ids vàrerank/rank/windows.
`score`/`score_kind` vẫn làfirststage; rawCElogit khôngcosine/confidence.

Evaluation output cuối: `t3_1_retrieval_20_candidates.csv`, ignored
`data/processed/t3-1-retrieval-20/`; firststage on/off dùngfrozenpool/querycache chung.
Lượt30 lưu riêng ở `t3_1_retrieval.csv`/`t3-1-retrieval-v2/`; reproduce bằng
`--candidate-k 30 --document-reference-policy keyword-only-v1` vớioutputpath riêng.
Frozen30 goldbindings khôngauto-rebind. Modelwarm stage timing loạiqueryencoding/LLM.

Finalscoped goldtop1 hybrid18→29/30, stagep504.65s; unfiltered9.11s. API12smoke
chỉ1supportedM212 và1expectedstalefilterabstention F05, fullp50~104s. Model vẫn có
JSON/source-ID/paraphrase errors; khôngnới exactquote validation. T3.2 xửlýgeneration.
Chi tiết metrics/trade-offs: `docs/reranker-freshness-review.md`.

## Bound passage selection — T3.2

Config hiện `verified_passages` / `bound-passage-selection-v3`, input2304/output64,
max8passages/context6. LLM trảpassageIDs; backend lấynguyênvăn/citation từapproved
source ranges vàhashes. Low-memory mode release retrievalmodels trướcgeneration và
GGUF cuối mỗirequest. Coldload chậm hơnwarm, thườngsốgiâycóthể35–39s ởprocess mới.

`sources.excerpt` làfullapprovedchunk; `evidence_passages.text` làđoạn thực gửiLLM,
`char_start/end` làUnicodeindices và`text_sha256` bindnguyênvăn. IDs chỉ cógiátrị
trongrequest; `cited` chỉcác đoạn đượcbackend chọntrảlời. SourceURL/title/pages từDB.
Legacy800charcopyvalidator còn ở `verified_quotes`; configold:
`configs/rag/quotes-v9.json`. RestartAPI đểbuildservice theo policy mới.

```powershell
python scripts/run_baseline_samples.py --questions data/manifests/t3_1_api_smoke_questions.csv --output-dir data/processed/t3-2-acceptance-api --summary data/manifests/t3_2_acceptance_api.csv --limit 12
python scripts/audit_passage_samples.py --input-dir data/processed/t3-2-acceptance-api --summary data/manifests/t3_2_acceptance_audit.json
python scripts/check_corpus_publication.py --output data/manifests/t3_2_publication_snapshot.json
```

Sampler nhận development_questions.csv, deriveexpectedsource từevidenceIDs.
Fullrecords/private manual-review.md ignored; manualverdictCSV/publicaggregate không
thaygoldbindings. BoundIDs khôngtự chứngminhsemanticrelevance; xem
`docs/passage-citation-review.md`, especially olderfaileddevelopmentcases vàtargetedreruns.
Acceptance11primaryanswers/12+1expectedabstention, median13.57s; cầnT3.3 precision/clarification.

## Clarification và phạm vi áp dụng — T3.3

Config default `behaviour.enabled=true`, `clarify-scope-v1`, pipeline
`rag-scoped-answers-v1`. Hỏi lại được thực hiện trước retrieval/model khi thiếu thông
tin cần thiết hoặc scope/câu hỏi/filters mâu thuẫn. Các source/hash/filter/latest guards
vẫn dùng chung trong SQL/pipeline; không nới filter khi thiếu bằng chứng.

Request nhận optional `scope`; gửi lại **câu hỏi gốc** cùng thông tin bổ sung:

```json
{
  "question": "Sau ba học kỳ chưa đạt ngoại ngữ bị giới hạn đăng ký thế nào?",
  "scope": {
    "cohort_year": 2026,
    "applies_to": ["undergraduate_regular"],
    "programmes": ["CTA"]
  }
}
```

Scope còn có `as_of` (ISO date), `design_years` (number) và `project_type`
(`regular`/`enterprise`). Các field không biết/giá trị sai trả422. Không có server-side
conversation memory hoặc query rewriting; câu hỏi mới cần đầy đủ thông tin của nó.

Response thêm `clarification` (required_fields/questions/conflicting_fields),
`resolved_scope`, `requested_filters`, `applied_filters`, `behaviour_policy` và
`version_notes`. Filter rõ từ scope/câu hỏi chỉ thêm field còn trống; original caller
filters giữ nguyên. Khóa tuyển không suy từ năm ban hành, audience không tự inherit;
programme/design duration dùng để chọn source passages.

`no_matching_evidence`/missing support trả insufficient; hỏi tình trạng hiệu lực chưa
verified hoặc so sánh phiên bản chưa consolidated cũng abstain và trình bày metadata
nguồn riêng. Một ngày có hiệu lực trong văn bản không chứng minh còn hiện hành.
Source comparison là known metadata differences, chưa tự hợp nhất toàn bộ điều khoản.

```powershell
python scripts/run_baseline_samples.py --questions data/manifests/t3_3_behaviour_questions.csv --output-dir data/processed/t3-3-behaviour-reproduce --summary data/manifests/t3_3_behaviour_reproduce.csv --limit 20
python scripts/audit_passage_samples.py --input-dir data/processed/t3-3-behaviour-reproduce --summary data/manifests/t3_3_behaviour_reproduce_audit.json
```

Sampler đọc `scope_json` và `filters_json`. Audit giữ cả summary thất bại, tách
binding/citation/filter fidelity khỏi support. Chi tiết complete runs/targeted reruns,
known extra material và latency: `docs/clarification-abstention-review.md`.
Quy tắc commit sau mỗi bước hoàn tất kiểm chứng lưu ở `AGENTS.md`.

## Adversarial behaviour — T3.4 / M3

Default pipeline `rag-guarded-passages-v1`, policy `guarded-behaviour-v1`. Explicit
outside-scope tasks/another-institution requests trả insufficient trước retrieval.
Context hash mismatch hoặc declared assistant-control instructions trả
`passage_binding_mismatch`/`untrusted_document_instruction` trước budgeting/model.
Whole context giữ nguyên để audit; không strip/rebind hoặc bỏ amendment cần thiết.
Rule set hiện hẹp, không thay semantic review/general intent classification.

```powershell
python scripts/run_baseline_samples.py --questions data/manifests/t3_4_adversarial_questions.csv --output-dir data/processed/t3-4-adversarial-reproduce --summary data/manifests/t3_4_adversarial_reproduce.csv --limit 24
python scripts/audit_behaviour_samples.py --input-dir data/processed/t3-4-adversarial-reproduce --summary data/manifests/t3_4_behaviour_reproduce_audit.json --cases data/manifests/t3_4_behaviour_reproduce_cases.csv
python scripts/audit_passage_samples.py --input-dir data/processed/t3-4-adversarial-reproduce --summary data/manifests/t3_4_passage_reproduce_audit.json
python scripts/run_document_attacks.py --output-dir data/processed/t3-4-document-reproduce --summary data/manifests/t3_4_document_reproduce.csv
python scripts/audit_behaviour_samples.py --input-dir data/processed/t3-4-document-reproduce --summary data/manifests/t3_4_document_reproduce_audit.json --cases data/manifests/t3_4_document_reproduce_cases.csv
```

Document runner dùng synthetic **post-retrieval adapter** + Qwen thật, không ghi public
DB hoặc đo upstream retrieval. SQL tests dùng schemas riêng. Fixtures là attack specs,
không phải nguồn UIT. Full outputs/hash snapshots/model traces ở ignored processed.
34 final pass/fail cases và276tests đạt M3 technical gate. Chi tiết failed pilots,
positive controls, timings và limits: `docs/adversarial-behaviour-review.md`.

## Dừng dịch vụ

```powershell
docker compose down
```

Không thêm `--volumes` nếu muốn giữ dữ liệu local.
