# Session handoff

## Hiện trạng

- Milestone: M2/T3.1–T3.4/M3 completed trong supported scope; T4 evaluation tiếp theo.
- Task vừa hoàn thành: T3.4 — adversarial behaviour, context instruction/hash/scope guards.
- Task tiếp theo: T4.1 — dataset100/required facts/evidence/filters/split và held-out freeze.
- Git: T3.3 initial commit `3407c07`; commit T3.4 xem `git log -1`.
  Theo yêu cầu người dùng, mỗi bước hoàn tất kiểm chứng phải commit rồi báo mã/kết quả;
  quy tắc lưu trong `AGENTS.md`.
- Runtime: Docker Desktop đang chạy, `regularag-db-1` healthy. Server HTTP smoke đã
  tự dừng; dùng Uvicorn theo `docs/development.md` để chạy API lâu dài.

## Đã thực hiện

- Tạo Conda environment `ragschool` với Python 3.12.15.
- Cài 70 package đã khóa, gồm FastAPI, Psycopg, PyMuPDF, PyTorch CPU,
  Sentence Transformers, Transformers, llama.cpp CPU, pytest và Ruff.
- Tạo `pyproject.toml`, `environment.yml`, `requirements.lock`, `.env.example`.
- Tạo FastAPI app, structured JSON logging và `/health` kiểm tra cả PostgreSQL lẫn
  extension pgvector.
- Tạo `compose.yaml` và `scripts/db/init.sql`.
- Hiện có276 tests (169 unit/107 PostgreSQL integration với schema riêng).
- Tạo `docs/development.md` với hướng dẫn tạo environment và chạy local.
- Mở rộng `.gitignore` cho secrets, Python artifacts và PDF raw không được cấp phép
  tái phân phối.
- Tạo `src/regularag/ingestion/` gồm cleaner, parser theo trang, tokenizer, chunker và
  pipeline có kiểm SHA-256 nguồn.
- Pin tokenizer `BAAI/bge-m3` theo revision
  `5617a9f61b028005a4858fdac845db406aefb181`; cấu hình target 700, hard ceiling 800,
  overlap 100 trong `configs/ingestion/baseline.json`.
- Parse 4 PDF text/55 trang thành 48 chunk trong `data/processed/baseline/`; lưu raw
  text, cleaned text, PDF page, printed page và content hash.
- Tạo `scripts/parse_baseline.py`, `scripts/validate_baseline.py`, thống kê CSV và báo
  cáo manual review 20 chunk.
- Tạo hai migration cho baseline vector storage và embedding fingerprint.
- Index 46 chunk của 159, 790, 956 bằng E5-small 384 chiều; re-index không tăng số bản ghi.
- Thêm API `/api/v1/ask`, Qwen2.5-1.5B GGUF Q4_K_M, quote selection và validation
  nguyên văn; context focus giữ cửa sổ đoạn liên tiếp và đoạn lân cận.
- Tạo `scripts/migrate.py`, `scripts/index_baseline.py`, `scripts/run_baseline_samples.py`,
  `scripts/smoke_http.py`, `scripts/check_environment.py`.
- Lưu thống kê 10 câu gốc, 4 controls và báo cáo `docs/rag-baseline-review.md`; full
  output và model trace nằm trong `data/processed/`, bị Git ignore.
- Thêm migration 003, `ingestion_runs`, trạng thái pending/processing/ready/failed,
  per-document transaction, advisory lock, cache skip, update/delete và recovery worker.
- Thêm CLI `scripts/ingest.py` cho file/thư mục/status/history/delete; report CSV được
  flush theo từng tài liệu. Indexer processed baseline dùng chung lifecycle.
- Snapshot T2.1: 15 registry/3 ready/46 chunk; xem `docs/ingestion-lifecycle-review.md`.
- T2.2: cài Tesseract5.5.2 native, vie+eng; preparation135 OCR/53 native pages.
- Migration004 lưu structure/source spans/quality/coverage. Pipeline structured-ocr-v2,
  correction/page-review hash gate; publication thêm1393, hiện4 ready/97 chunk.
- Review32 chunk; validator97 span/token/hash pass; pending121/excluded23 page.
  Báo cáo: `docs/structure-ocr-review.md`, native hash: `data/manifests/ocr_runtime.json`.
- T2.3 migration005 thêm FTS/simple/unaccent/GIN, refresh triggers text/metadata;
  keyword query accent-fold/mã văn bản/số điều, `ts_rank_cd` không gọi BM25.
- RRF/dedup, branch/rank/raw score provenance, config default hybrid và API override
  vector/keyword/hybrid. Keyword-only không gọi embedder, giữ chung publication/model gate.
- Comparison23 câu ×3 mode, CSV69 rows; full hits/config/query diagnostics ignored.
  Báo cáo: `docs/hybrid-retrieval-review.md`, summary: `data/manifests/retrieval_comparison.csv`.
- T2.4 migration006 typed metadata/date/cohort, normalization theo evidence; filter chung
  hai nhánh trước LIMIT/RRF, API filters/applied_filters và source scope/unknown legal status.
- `cohort_scopes.csv` bind956 cohort_from2026 với sourceSHA/Điều1 khoản3 PDF2; load_manifest
  bỏ review stale. 790 effective date null do nguồn chỉ ghi học kỳ.
- 30 câu development/reference/evidence do assistant review,19 bound chunks,180 results:
  `data/manifests/development_questions.csv`, `development_evidence.json`,
  `development_retrieval.csv`, `development_manual_review.csv` và
  `docs/metadata-development-review.md`.
- M2 đối chiếu133 pages của11 nguồn, full/sparse post-edit hash-bound; serialize43/308
  tables; clear unsupported308 cohort2025-only, record851 start01September2024.
- `source_metadata_reviews.csv` và cohortreviews giữ các scope/date có evidence; API
  metadata_note/omitted_layout_pdf_pages, partial không tự thành full khi bỏ diagram.
- Active15/15 ready/307 chunk/0 pending pages;15 unchanged ởlượt2. Báo cáo:
  `docs/m2-corpus-review.md`, snapshot `data/manifests/m2_publication_snapshot.json`.

## T3.1 — Hiện trạng mới nhất

- Reranker `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`, revision
  `1427fd652930e4ba29e8149678df786c240d8825`, CPU/batch1/2threads/window512/32/maxlogit.
  Default20candidates/top8/context6/maxinput4096; bật/tắt qua config.
- `document_versions.csv`/`document_relations.csv` hash-bound15issue dates và4relations;
  oldaffectedclauses bị loại, latestcompanion reserve, unavailable/filtered/changed
  latest hoặc budgetmissing dẫn abstention trướcgeneration. Historical as_of tôn trọng cutoff.
- `shared-query-refs-v1` constrain mã văn bản cảdense/keyword trướcLIMIT; callerfilters
  vẫnstrict. API latestissued/sourcechecked/firststage/rerank provenance.
- Portal/PDF15 rechecked09October2026:15listed/bytesunchanged; khônglivefetch mỗiask.
  `source_freshness_checks.csv` lưu groups/indexhashes/checked_at. Source drift chặn sau
  metadata refresh; cần review attachmentdates/relations khi cập nhật nguồn.
- Hai completedruns216rows mỗi lượt, final20 scoped hybrid-off18→on29/30goldtop1,
  stagep504.653s; unfiltered28/30/p509.110s. Identifierprobes12/12 với sharedrefs.
- API12:1supported M212 từ894/PDF8; F05 old790-only filter abstains208ms khônggeneration.
  M204 correctrowS2 nhưngciteS1 bịreject; các case khác JSON/quote/sourceIDfailure.
  `t3_1_api_audit.json`:0provenance/excerpt/filter/latestanchor/citation violations;
  end-to-end p50~104s/p95~153s. Báo cáo `docs/reranker-freshness-review.md`.
- Final187tests/pipcheck/lock70/Ruff119files pass; dependency scoreSQL castdouble cho
  diagnosticJSON. `t3_1_publication_snapshot.json`:15ready/307FTS/15unchanged/0unfinished,
  19goldbindings unchanged. Migrations001–006 không đổi.

## T3.2 — Hiện trạng mới nhất

- Default`rag-bound-passages-v3` / `verified_passages`, modelQwen unchanged. LLM chỉ
  trảpassageIDs perrequest; strictschema/enum/unknownID/duplicate guards vàtốiđa1retry.
  Backend resolve source/charoffset/textSHA, lấynguyênvăn vàDBcitationmetadata.
- Input2304/output64/max8passages/context6. Atomicconditions/no midblocktruncation,
  supportfacets, literal signature dependency, programme filters vàsemantic sourceprior.
  Low-memory release E5/CE trướcllama vàGGUF finally; CPUcoldload vẫn35–39s ởprocess mới.
- Acceptance12:11primarysource-supported answers,1correctF05stalefilterabstention,
  p5013.572s/p9525.958s vsold104/153s. F03extraneousgradeI removed ởtargeted rerun;
  F06fullhistorical412 conditions/Cgrade5years retained, nofuture513.
- M204 đúngrow vàsourceID, M211 literal01/9/2024, M212 source894**Điều9/PDF8**,
  D15/D30 literalconditions; source/article15 trongreportT3.1 làdocumentationerror.
- Widerdevelopment30 run29answered/1SVfalseabstention; manualD13/D26wrongtopics và
  D28/D29otherprogrammes fixed/retested. Somegenericqueries cònextra material;
  khôngđếmstatusanswered hoặc ghépreruns làmheld-outaccuracy.
-210tests, Ruff124files/lock70/pipcheckpass. Corpus15ready/307chunks/19goldbindings
  intact. `docs/passage-citation-review.md`, `t3_2_acceptance_audit.json`,
  `t3_2_freshness_audit.json`, `t3_2_publication_snapshot.json` vàmanualreviewCSVs.
- Legacyconfig `configs/rag/quotes-v9.json` đểreproduceoldcopypolicy.
  API `evidence_passages` làpromptspans cóoffset/hash/cited; `sources.excerpt` làfull
  approvedsourcechunk đểđối chiếu. Allfulltext/modeltraces ignored.

## T3.3 — Hiện trạng mới nhất

- Pipeline `rag-scoped-answers-v1`, behaviour `clarify-scope-v1`; model pins, embedding
  fingerprint, freshness/reranker và passage prompt v3 giữ nguyên. Restart API khi đổi config.
- Optional `scope`: cohort_year/applies_to/programmes/as_of/design_years/project_type;
  structured reply stateless bằng câu hỏi gốc + scope, không tự rewrite/hội thoại memory.
- Missing/conflicting cohort/audience/programme/date hỏi lại trước model/DB; caller filters
  giữ strict. Response thêm requested_filters/resolved_scope/clarification/version_notes.
- Behaviour20 final: 8 clarify / 7 abstain / 5 supported primary answers; 20 HTTP200,
  5 generation; audits span/citation/filter/source/latest errors0. Clarify 22–131 ms.
- Positive12:11 supported answers/1 correct stale-filter abstention; p50/p95
  20,279/43,983 ms. Historical412 fullconditions retained; không future513.
- Development30 full batch30 answered nhưng manualD23 sai topic; 29 primary supported.
  Tight prerequisite-edge guard và annual-unit fix rerunD22/D23/D26 đúng. Reaudit cũ
  `t3_3_development_reaudit.json` intentional support failureD23; không ghép thành30/30.
- C17 pilot sai8-credit registration/header thay vì6-credit module vàcohort; fixed
  final277Điều1/PDF3/chunk0004. Allfailedtraces giữ ignored `data/processed/t3-3-*/`.
- Version comparison/unknownlegalstatus trả metadata riêng/base-amendment/date/scope,
  không tự consolidated legalanswer. Legal status vẫn unknown toàn corpus.
- `docs/clarification-abstention-review.md`; manual/audit summaries `t3_3_*` manifests.
  247tests/Ruff/lock70/pipcheck pass. Snapshot15ready/307FTS/19goldbindings unchanged.

## T3.4 / M3 — Hiện trạng mới nhất

- Pipeline `rag-guarded-passages-v1`, behaviour `guarded-behaviour-v1`; same model pins,
  input2304/output64/passages8/context6/reranker20/freshness. Restart API để load config.
- `generation/guards.py`: explicit out-of-scope tasks/another-institution requests
  abstain trước model; source hash hoặc assistant-control instruction trong context
  abstain trước budgeting. Detector fold không sửa bound text/hashes; whole context
  blocked, không bỏ required companion để dùng base. Prepare/resolve có cùng guard.
- 24real API cases:pilot16pass/8fail, final24pass (11primarysupported/13abstain).
  10post-retrieval fixtures:pilot3pass/7fail, final10pass (2controls/8abstain). RealQwen;
  synthetic retriever không mutate/benchmark publicDB. SQLinjectiontests schemas riêng.
- Positive12 final11supported/1correctabstention; historical412 fullconditions vàcaller
  old-only/domain/cohort/date filters giữ đúng. Binding/citation/filter/latest audits0.
- 276tests/Ruff/lock70/pipcheck pass; snapshot15ready/307FTS/19goldbindings unchanged,
  307chunks0instructiondetectorhits,0unfinished. Scope/instruction patterns còn declared
  lexicalheuristics, không general entailment/complete injection protection.
- `docs/adversarial-behaviour-review.md`, `t3_4_*` manifests; pilot failures vàraw traces
  giữignoredprocessed. Regexfixture serialization sửa sangarrays không đổi query/status/body.
- M3 technical acceptance đạt34pass/failcases; nextT4.1. API vẫnstateless structuredscope,
  optionalrewriting không triển khai. Chưa independent/held-out answeraccuracy.

## Kiểm chứng

- `conda run -n ragschool python --version`: Python 3.12.15.
- `python -m ruff check .`: pass.
- `python -m ruff format --check .`: pass.
- `REGULARAG_RUN_DB_TESTS=1` và `python -m pytest`:276 passed.
- Lock integrity: 70 dependency, không có version mismatch; `pip check` pass.
- `docker compose config --quiet`: pass.
- Runtime hiện tại: Docker đã recovery sau lúc bị dừng; `docker compose ps` healthy.
  15 registry/15 ready,307 unique chunks/307 FTS,0 run pending/processing.
- Kiểm chứng T1.3 trước đó: PostgreSQL 17.11, pgvector 0.8.7 và `GET /health` trả
  HTTP 200, `status=ok`.
- PyMuPDF smoke test: đọc được 27 trang và 64.127 ký tự từ PDF 790.
- Baseline validation: 4 tài liệu, 55 trang, 48 chunk, 478-705 token; token count,
  content hash, chunk index và page mapping đều hợp lệ.
- Manual review: 20/20 chunk đúng page mapping; 18/20 đọc được.
- Mười câu gốc: HTTP 200 và source trace 10/10; 8 bị chặn do thiếu 1393, 2 output model
  không hợp lệ. Chưa có answered trên bộ gốc.
- C03 bổ sung và smoke HTTP thật: quote 1 học kỳ chính (15 tuần) đúng nguồn 159,
  PDF 1–2, citation `[S1]`; `/health` và `/api/v1/ask` cùng trả 200.
- T2.1 corpus: retry 159 sau timeout thành công; batch đầu đầy đủ có 2 ingested +
  1 unchanged, batch sau 3 unchanged; không thêm chunk. Run cũ của 159 ghi interrupted.
- Integration đã kiểm corrupt PDF không phá batch, rollback update, hide stale chunks,
  delete cascade, history sau delete, khóa worker, recovery và report khi bị ngắt.
- T2.2 re-ingest4 unchanged; active OCR1393 giữ70 SV/12 tín chỉ/1 tháng/điểmM.
- API OCR smoke3 câu HTTP200 nhưng chưa đạt: 2 dense thiếu1393 trong context,1 JSON lỗi;
  `data/manifests/ocr_api_smoke.csv` ghi kết quả, không gọi đây là answer accuracy.
- Migration001–005 chạy lại skip; FTS97/97 populated, `unaccent`1.1 và GIN hiện diện.
- T2.3 document hit@1/@2/@5 trên23 câu: vector15/16/23, keyword22/22/22, hybrid22/22/23.
  C03 hybrid mất159 khỏi top2; query chung có thể đúng tài liệu nhưng sai article.
- Hybrid API smoke3/3 có1393 trong context: OCR01 answered nhưng quote sai relevance;
  OCR02 invalid_json, OCR03 unverified_quote bị chặn. Xem `hybrid_api_smoke.csv` và
  `hybrid_api_manual_review.csv` trong `data/manifests/`.
- Migration001–006 chạy lại skip; re-index4 ingested sau config/filter version, giữ97 unique IDs.
- Development30 scoped gold hit@1/@2/@5: vector27/30/30, keyword14/22/27, hybrid18/28/30.
  Scope violations0; hybrid18 top1/10 top2, D15 rank5/D30 rank3 vắng context2.
  Reference do assistant biên soạn sau source read, chưa independent/held-out evaluation.
- M2 pages:103 approved/40 native/45 excluded/0 pending; review/correction do assistant,
  không independent human.19 gold chunk bindings còn nguyên, không auto-rebind.
- M2 scoped development30 giữ vector27/30/30,keyword14/22/27,hybrid18/28/30; unfiltered
  hybrid11/16/23.12 identifier probes documenttop1 vector9/12,keyword/hybrid12/12.
- Filtered API smoke: M204 answered quote2012/4.5years dù hỏi2018/4years; không success.
  M201 schema/M211 metadataquote/M212 JSON failures. `m2_api_manual_review.csv` giữ lỗi.

## Quyết định kỹ thuật

- Dùng Python 3.12 thay vì Python hệ thống 3.14 để giảm rủi ro tương thích ML/OCR.
- Dùng Psycopg đồng bộ cho health endpoint đồng bộ; FastAPI chạy endpoint trong
  thread pool. Cách này tránh giới hạn Psycopg async với ProactorEventLoop trên
  Windows mà không thay event-loop policy toàn ứng dụng.
- PaddleOCR chưa cài; embedding/reranker/generation chạyCPU. Reranker dùng dependency
  SentenceTransformers đã khóa và pinnedweights trongHFcache.
- Dùng tokenizer thật của BGE-M3 thay vì ước lượng theo ký tự; revision model được pin
  trong config để tái lập chunk.
- Giữ `pdf_page_number` và `printed_page_number` riêng; printed page không rõ được để
  `null`, không suy diễn từ vị trí PDF.
- Cho phép tail chunk đến 800 token để tránh một chunk gần như chỉ chứa overlap; ngưỡng
  500 là mềm nhằm ưu tiên không cắt giữa đoạn.
- API vẫn khởi động khi database lỗi nhưng `/health` trả 503 `degraded`; Compose và
  deploy có thể dùng trạng thái này để quyết định readiness.
- Config cuối: `configs/rag/baseline.json`, prompt `bound-passage-selection-v3`,
  pipeline `rag-guarded-passages-v1`; reranker/freshness/behaviour enabled, low-memory generation.
- RAM trống thấp khi Docker bật nên E5-small thay BGE-M3 ở embedding; tokenizer chunk
  vẫn BGE-M3. E5 prefix query/passage, window 512/32 và pooling được fingerprint.
- Qwen GGUF chọn quote; backend bỏ diễn giải tự do, kiểm quote có thật và dựng citation.
  Quote đúng không tự chứng minh relevance hay đủ điều kiện/phạm vi áp dụng.
- Retrieval lọc allowlist, trạng thái ready và model revision/fingerprint. Thiếu companion
  amendment của base khiến answered chuyển sang insufficient evidence.
- Embedding runtime hiện dùng batch 1 / 2 CPU threads sau lần chậm/timeout; fingerprint
  bỏ hardware params. Model/revision, dimension và window/pooling vẫn như baseline.
- Ingest nhận nguồn đã khai báo trong manifest; scan/chưa được duyệt không publication.
  Artifact mỗi lần parse ở `data/processed/ingestion-runs/<run_id>/<document_id>/`.
- Update failed bị chặn khỏi search dù có chunk cũ. Retry thành công mới ready; delete
  cascade chunk nhưng audit còn `document_id_snapshot`.
- CLI mặc định `configs/ingestion/structured.json`; baseline truyền explicit.
  Indexer processed mặc định m2-publication. Header/footer theo bbox, không xóa body số.
- 1393 review/post-edit bind source/OCR hash, correction toàn văn ở
  `data/processed/ocr-corrections`; clone thiếu correction cần review lại, không bypass gate.
- Companion phải full/ready VÀ có trong context; source chỉ index chưa đủ. 159/790/956
  partial có warnings; hierarchy không suy qua excluded page/appendix.
- Retrieval hiện hybrid: top8/candidate20, rrf_k60, weights1:1. Cosine>=0.55 áp trước
  fusion; keyword>0 và RRF>0 dùng ngưỡng riêng, không so với cosine.
- Mã văn bản trong query hiện constrain cảdense/keyword; request filters chung hai nhánh.
  Article phrase có thể khớp reference trong body, không chỉ điều sở hữu của chunk.
- Document-hit metrics chỉ cần một candidate document, không chứng minh đủ bộ base +
  amendment hoặc đúng clause. Query cache/cold-start khác nhau, không so latency của run.
- Filter tags exact, OR trong list/AND giữa fields; audience không tự inherit.
  Cohort unknown bị loại khi lọc year; as_of là interval ghi nhận, không xác nhận current.
- Development binding giữ canonical dataset/hash/pages; đổi câu hỏi/evidence cần review lại,
  không rebind im lặng vượt drift. Artifact toàn văn ở ignored processed.
- Audience source có nhiều exacttags phân tách`;`; filter membership không taxonomyinherit.
  412/513 regular+distance, jointprogram exclusion là điều kiện source cần giữ khi trả lời.
- M2 all15 allowlist đã review; không auto-infer current.112 sourceappendixyear2023 khác
  main2024 và697 appendixdifferentacademicperiods được ghi metadata_note, không sửa ngầm.

- Latest nghĩa verified family/source dates trongcorpus/snapshot, không globalnewest
  haylegalactive. Mã790 trongquery có thể thêm1393 qua verifiedrelation; explicit790-only
  filter khôngđược nới và sẽabstain nếu thiếu1393. as_of không suy từcohort/issuedyear.
- Reranklogits khôngconfidence; giữ raw scores/modelrevision riêng. Candidate20 chọn
  sau lượt30 chậm; sharedrefs cũng đổi, không attribution toàn bộ cho candidatecount.
- Whole-clause exclusion bảo thủ cho14.1.b/unknownboundaries có thể mấtunchangedparts;
  finer-grained views cần source-bound review.

## Blocker

- Không còn document/page publication pending. Supported scope có45 excluded pages,
  gồm TOC/blanktemplates/diagram và chưa durable row-column tables;832 bỏ regions3/5.
-43 đã OCR/table serialization/full publication, còn legal_status unknown và phạm vi
  lịch2012–2019. SQLcohortfilter vẫndocument-level; T3.1 promptfocus chỉ chọnliteralrow
  khi câu hỏi nêu rõcohort/design duration vàrow duy nhất, chưa giải quyếtmọi ambiguity.
-697 extension fee/remuneration swimlane,790 grade table và956 merged tables còn ngoài
  evidence hỗ trợ. Không coi15ready là toàntext hoặc hiện hành pháp lý đã chứng minh.
- Model nhỏ còn lỗi output/selection; retrieval có thể đúng tài liệu nhưng sai đoạn.
  Scope/facets hiện lexical, chưa general entailment. Câu hỏi chung còn extra material.
- Hybrid cũng có regression C03; cần gold theo clause và review thủ công. OCR01 qua quote
  validation nhưng không trả lời câu hỏi, không được tính answer success.
- Một deprecation warning trong FastAPI/Starlette TestClient còn tồn tại; không ảnh
   hưởng runtime và chưa cần đổi sang thư viện `httpx2` chưa ổn định trong baseline.
- T3.1 ranking cải thiện nhưng11generationcalls chỉ1supportedanswer; medianwalltime104s.
  Wrong sourceIDs, metadataquotes, paraphrase/noncontiguousquotes/truncatedJSON được chặn.
  Không nới validator hoặc đếm statusanswered/documenthit làm answeraccuracy.

## Phiên tiếp theo

1. T4.1: hoàn thiện dataset100 theo plan (60development/40held-out), mọi mẫu có category/
   expectedstatus; answered có reference/requiredfacts/evidencepages/passages. Giữparaphrase
   cùngsplit, freezeheldout trước tuning cuối; T3.4cases làdevelopment khôngrelabelheldout.
2. Giữ acceptance12/frozen30/19gold vàT3.3/T3.4failures; scope/instruction guards còn hẹp,
   cần thêm biến thể/falsepositivecontrols. Không nới citation/filter/source/latest guards
   hoặc rebind gold để vượt evaluation. Chưa cógeneralentailment.
3. PositiveCPU p50~22s/cold~57s ởlượtT3.4, tải máybiến thiên; đo riêngcold/warm trướcclaims.
   Public sourcecheckpoint09October2026,45excludedpages vẫnngoàisupported scope.
4. Chốt step sau kiểm chứng bằng progress/handoff vàcommit theo `AGENTS.md`, báomã.
