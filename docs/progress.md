# Tiến độ RegulaRAG

Trạng thái hợp lệ: `pending`, `in_progress`, `blocked`, `completed`.

| Task | Trạng thái | Đầu ra/bằng chứng | Blocker | Bước tiếp theo |
|---|---|---|---|---|
| T1.1 | completed | `docs/project-brief.md`, `docs/architecture.md`; phạm vi UIT, 10 câu hỏi mẫu và nguồn lực đã ghi nhận | Không | Bắt đầu T1.2, kiểm kê nguồn chính thức UIT |
| T1.2 | completed | 15 PDF/13 nhóm P0; `data/manifests/documents.csv`, `data/manifests/question_sources.csv`, `docs/data-sources.md` | 11 PDF scan cần OCR trước retrieval | T1.3 dựng repository; T1.4 parse 4 PDF text trước |
| T1.3 | completed | Conda `ragschool` Python 3.12; FastAPI `/health`; PostgreSQL 17 + pgvector 0.8.7; 4 tests; Ruff sạch | Không | Bắt đầu T1.4 với 4 PDF text; lập kế hoạch OCR cho 11 PDF scan |
| T1.4 | completed | Parse 4 PDF/55 trang thành 48 chunk; BGE-M3 tokenizer pin revision; validation và review 20 chunk | 11 PDF scan và PDF 43 lỗi encoding cần OCR/reparse trước retrieval | T1.5 index ba tài liệu đọc tốt; không dùng PDF 43 |
| T1.5 | completed | 3 tài liệu/46 vector; E5-small + Qwen GGUF CPU; `/api/v1/ask`; 10 mẫu và 4 controls; 36 tests; HTTP smoke 200 | 1393 chưa OCR; chất lượng model/retrieval còn hạn chế, đã ghi cả lỗi | T2.1 ingestion lifecycle; ưu tiên OCR 1393 ở T2.2 |
| T2.1 | completed | Migration 003, ingestion_runs, CLI file/thư mục/status/history/delete; 53 tests; corpus 15 document/46 chunk, re-ingest 3 unchanged | 11 scan ghi ocr_required; 43 chưa được duyệt; chưa OCR | T2.2 chunking cấu trúc và OCR có điều kiện, ưu tiên 1393 |
| T2.2 | completed | Tesseract 5.5.2; OCR135/188; structural-ocr-v2; migration004; review32; 4 ready/97 chunk; 66 tests | 121 pages chờ review; bảng phức tạp/43 excluded; dense chưa kéo amendment vào context | T2.3 keyword search và RRF; tiếp tục review trước M2 |
| T2.3 | completed | Migration005 FTS/simple/unaccent; keyword/RRF/dedup/provenance; 23 câu ×3 mode; 87 tests; `docs/hybrid-retrieval-review.md` | Hybrid regression C03; API quote relevance/JSON còn lỗi; chưa clause-level gold | T2.4 filters chung hai nhánh và development30; tiếp tục page/table review trước M2 |
| T2.4 | completed | Migration006 typed metadata; filter chung/API provenance; 30 câu/19 bound chunks;180 results/manual review30;149 tests; `docs/metadata-development-review.md` | Scope document-level; chưa independent/held-out; M2 thiếu publication toàn corpus | Hoàn tất page/table review11 nguồn còn lại trước M2/T3.1 |
| M2 | completed | 15/15 ready/307 unique chunks;188 pages/0 pending;133 page decisions;15 unchanged;156 tests; `docs/m2-corpus-review.md` | Supported scope có45 excluded pages/omitted regions; generation và clause relevance còn lỗi | T3.1 reranker trên corpus M2; tiếp tục layouts ngoài scope và citation/relevance tasks |
| T3.1 | completed | Pinned CPU cross-encoder/window-max;20 candidates/top8/context6/budget4096; verified issue dates/relations/latest guards;432 completed evaluation rows;187 tests; `docs/reranker-freshness-review.md` | Generation p50~104s và1/12 supported smoke answer; conservative clause exclusion và excluded layouts | T3.2 source-bound span/source-ID selection, citation support và generation latency; T3.3 clarification |
| T3.2 | completed | BoundpassageIDs/offsets/SHA/strictschema/enum/boundedretry;210tests;12acceptance+30development+targetedregressions;11supportedprimaryanswers/12 và1correctabstention;median13.57s; `docs/passage-citation-review.md` | Genericqueries cònextra material; coldloads35–39s; chưaheld-out/clarification | T3.3 scope/clarification vàprecision; T3.4 behaviorcases trướcM3 |
| T3.3 | completed | `clarify-scope-v1`; structured scope/clarification/version notes; 20 cases: 8 clarify / 7 abstain / 5 supported answers; positive12; development30 và targeted fixes; 247 tests; `docs/clarification-abstention-review.md` | Lexical scope/facets chưa general entailment; extra material và variable CPU latency; chưa held-out | T3.4 adversarial/ngoài phạm vi/giả định sai, ít nhất20 cases trước M3; commit sau mỗi bước hoàn tất |
| T3.4 / M3 | completed | 24 API cases +10 injected-context cases:34/34 final pass; source-instruction/hash/scope guards; positive12:11 supported/1 correct abstention;276 tests; `docs/adversarial-behaviour-review.md` | Declared heuristics chưa general scope/entailment/injection defense; extra quotes, CPU latency và excluded layouts; chưa held-out | T4.1 dataset100, required facts/evidence/filter/split và held-out freeze; commit sau bước hoàn tất |
| T4.1 | completed | Dataset100 đúng6category quotas;60development/40test;72curatedspans/49chunks;source/offset/hash/filter/split validators;freeze trước finaltuning;300tests; `docs/evaluation-dataset-review.md` | Assistant source review chưaindependent; commoncorpus/question-familyholdout; chưa accuracybenchmark100 | T4.2 runner/metrics trênfrozen data, defaultdevelopment; test sauconfigchốt; commitstep |
| T5.1 early demo | completed | UI/UXProMax/nativeweb trênFastAPI;scope/filter/devpresets/citation/excerpts/feedbackexport;303pytest+12Node;27fixture/18realbrowserassertions; `docs/demo-guide.md`, `docs/demo-ui-review.md` | Currentbaseline/localdemo; M4benchmarks còn pending; sessionfeedback chưaDBpersist | Người dùngmanualtestUI, sauđóT4.2; giữtest40freeze |
| Demo feedback — GPA/freshness | completed | Clause-scopedv2/unchangedsourceviews;8cases6supported/2correctabstain;regression12 giữ11supported/1abstain;322pytest+12Node/22livebrowserassertions; `docs/gpa-credit-freshness-review.md` | Finer hierarchy/facets còn hẹp; M4benchmark pending | Người dùng thử bản sửa ở8000, rồiT4.2; giữfreeze40 |
| T4.2 | completed | One-command frozen evaluator/realASGI/rank10/stageusage/manualhash-boundreview;60dev47answerable;Recall5=.98936/MRR10=.96454;41/47correct/52/71taskcitation;339tests; `docs/evaluation-runner-review.md` | Multi-clause7/12;extraquotes/D42falseabstain/D51missingprogress;heldout chưa chạy | T4.3 fixed-corpus/LLM/budget ablation4variants; giữfailures/gold vàcommitstep |
| T4.3 | completed | 4variants×60+topk4/12×60=360newpredictions/77reviewgroups;vectors41/KW35/RRF36/CE41of47;selectedCEk4/52of71citations/p9517.820s;354tests; `docs/benchmark-ablation-review.md` | Completeness/precision/D42/D51;one-passlatencyvariation;0heldoutbenchmark | T4.4 erroranalysis/fixes trênselectedreference rồifreezefinal/test;commitstep |
| T4.4 / M4 | completed |20errorcases/3fixgroups;dev47/47correct/65of65facts/60of60taskcites;exactreleasefreeze→40test19/28correct/29of108taskcites;370tests/13Node/65browserassertions; `docs/error-analysis-review.md` | Held-outquality:reject0/7,clarificationaxes0/20,p9532.707s;chưa đạt chất lượng tổng quát | T5.2observability;qualitybacklog với evidence/dev/testversion mới,giữfailedheldout/freeze;commitstep |
| T5.2 | completed |ServerUUID/header/bodyID→ContextVar→pipeline; boundedtracev1/CLI/stages/ranks/context/selection/usage;7contracts+liveHTTP đạt;383pytest/13Node/Ruff186; `docs/observability-review.md` | OptionalLangfuse/storage/rotation deferred; M4qualitylimits còn | T5.3Docker/CI/deployment;giữM4evidence vàcommitstep |

## Nhật ký kiểm chứng

### T1.1

- Ngày: 2026-10-05.
- Đã đọc toàn bộ `RegulaRAG-Project-Plan.md` và xác nhận workspace ban đầu chỉ có
  file kế hoạch.
- Đã lấy cấu hình máy bằng PowerShell/CIM: Windows 11, Intel Core i5-12450HX,
  11,8 GB RAM, RTX 3050 6 GB.
- Đã kiểm tra công cụ: Python 3.14.5, Docker 29.7.2, Git 2.53.0.
- Đã chốt qua người dùng: trường UIT, ngân sách API 0 VND, 10 giờ/tuần, chưa có
  deadline portfolio.
- Đã đối chiếu checklist T1.1: mô tả bài toán, người dùng, năm nhóm câu hỏi, phần
  ngoài MVP, 10 câu hỏi, nguồn lực và kiến trúc ban đầu đều có artifact.

### T1.2

- Ngày: 2026-10-05.
- Đã kiểm tra danh mục chính thức `portal.uit.edu.vn` và tải 13 nhóm P0 vào
  `data/raw/uit/p0/`; hai văn bản gốc bắt buộc được tải thêm cho hai amendment,
  tổng cộng 15 PDF/188 trang/40.367.168 byte.
- Kiểm tra bằng PyMuPDF: 15/15 mở được; 4 file có text layer, 11 file scan toàn phần.
- Đã tính SHA-256 cho từng file và lưu vào `data/manifests/documents.csv`.
- Đã ghi quan hệ `790 + 1393` và `412 + 513`; không loại văn bản gốc vì amendment
  không chứa toàn văn quy định.
- Đã gắn 10 câu hỏi mẫu với nguồn dự kiến trong
  `data/manifests/question_sources.csv`.
- Portal ghi bản quyền thuộc UIT nhưng không có giấy phép tái phân phối rõ ràng;
  PDF thô được loại khỏi Git bằng `.gitignore`.
- Tiêu chí T1.2/M0 đạt về số lượng nguồn, phạm vi và manifest. OCR/table review của
  file scan là công việc bắt buộc trước khi các file đó được đưa vào retrieval.

### T1.3

- Ngày: 2026-10-05.
- Đã khởi tạo Git repository, không commit.
- Đã tạo Conda environment `ragschool` tại
  `C:\Users\Khanh\miniconda3\envs\ragschool` với Python 3.12.15.
- Đã cài project và dependency trong environment; `requirements.lock` có 36 package
  và khớp 36/36 phiên bản đã cài.
- Đã tạo package `src/regularag`, Pydantic settings, structured JSON logging,
  FastAPI `/health` và database health query.
- Đã tạo `compose.yaml`; PostgreSQL 17.11 và pgvector 0.8.7 khởi tạo thành công,
  container `regularag-db-1` healthy.
- Smoke test Uvicorn thực tế: `/health` trả HTTP 200 với database `regularag`.
- Quality gate: Ruff check pass, Ruff format pass, pytest 4/4 pass.
- PyMuPDF 1.28.2 đọc thử `790/QĐ-ĐHCNTT`: 27 trang, 64.127 ký tự text.
- Cảnh báo không chặn: Starlette báo `TestClient` dùng `httpx` đã deprecated và đề
  xuất `httpx2`; runtime API không phụ thuộc TestClient.

### T1.4

- Ngày: 2026-10-06.
- Đã thêm parser PyMuPDF theo trang, cleaner bảo toàn nội dung, chunker theo đoạn và
  tokenizer `BAAI/bge-m3` pin revision
  `5617a9f61b028005a4858fdac845db406aefb181`.
- Cấu hình baseline: target 700 token, ngưỡng mềm 500, hard ceiling 800, overlap 100.
- Đã kiểm SHA-256 nguồn rồi parse 4 PDF text/55 trang thành 48 chunk; khoảng thực tế
  478-705 token. Hai chunk dưới 500 giữ ranh giới đoạn dài; không có chunk vượt 800.
- Artifact toàn văn nằm trong `data/processed/baseline/` và bị Git ignore; thống kê nằm
  tại `data/manifests/baseline_parse_summary.csv`.
- Validation kiểm lại token count, content hash, chunk index và page reference: pass.
- Kiểm tra thủ công 20 chunk: page mapping đúng 20/20; 18/20 đọc được. Hai chunk của
  `43/TB-ĐHCNTT` lỗi encoding font nhúng và bị loại khỏi retrieval cho đến khi OCR hoặc
  reparse. Ba tài liệu còn lại đạt nghiệm thu T1.4.

### T1.5

- Ngày: 2026-10-08.
- Đã bật Docker Desktop; PostgreSQL/pgvector healthy. Áp dụng hai migration cho
  `documents`, `chunks`, HNSW và embedding fingerprint; chạy lại được skip.
- Đã index hai lần corpus thật: 3 tài liệu `159`, `790`, `956`, luôn giữ 46 chunk.
  Vector E5-small 384 chiều, batch 8, CPU; dùng cửa sổ/pooling cho chunk dài và pin
  model revision. PDF 43 và 11 PDF scan không vào retrieval.
- Đã thêm `POST /api/v1/ask`, generation GGUF Q4_K_M local, JSON grammar, context theo
  cửa sổ đoạn liên tiếp, ChatML token budget và kiểm quote/source ID từ backend.
- Mười câu gốc qua API thật ở tầng ASGI: 10/10 HTTP 200 có nguồn; 8 abstain do thiếu
  amendment 1393, 1 lỗi JSON, 1 lỗi schema. Không coi document hit hay HTTP 200 là
  answer accuracy.
- Bốn controls bổ sung: C03 trả quote đúng 1 học kỳ chính (15 tuần) từ 159; ba câu
  khác bị chặn vì nguồn/quote chưa đủ. Lỗi sinh tự do và quote không liên quan được
  giữ lại trong báo cáo `docs/rag-baseline-review.md`.
- Smoke Uvicorn/HTTP thật: `/health` 200, `/api/v1/ask` 200 và C03 `answered` với
  citation `[S1]`, PDF 1–2. Server smoke tự dừng; database còn healthy.
- Quality gate: Ruff check/format pass, 36 tests pass (32 unit + 4 integration
  PostgreSQL), `pip check` pass, lock 70/70 khớp phiên bản đã cài.
- T1.5/M1 đạt tiêu chí luồng kỹ thuật và truy vết; quality hạn chế đã được ghi rõ.

### T2.1

- Ngày: 2026-10-08.
- Áp dụng migration `003_ingestion_lifecycle`, giữ index M1 và thêm lifecycle
  pending/processing/ready/failed cùng run/config/hash/model/error/timestamp.
- Ingest/delete theo từng document, advisory lock theo schema/document. Publication
  là transaction thay chunk + ready; update lỗi giữ chunk để audit nhưng chặn search.
- `scripts/ingest.py` hỗ trợ file/thư mục, metadata manifest, status/history/delete,
  override document ID, force và CSV report được flush sau từng kết quả.
- Indexer processed cũ cũng đi qua lifecycle; retrieval yêu cầu cả ingestion/publication ready.
- Lần đầu corpus bị timeout ở 159. Retry đóng run cũ thành interrupted và khôi phục
  ready; giảm runtime embedding xuống batch 1 / 2 threads, dùng cache offline.
- Hai batch đầy đủ 15 PDF: ready 3, failed 12; batch thứ hai có 3 unchanged, 0 ingest
  mới. Database có 46/46 chunk ID duy nhất, 46 chunk trỏ đến run, 0 run chưa hoàn tất.
- 11 scan ghi ocr_required; 43 ghi quality_not_approved. Exit 1 là partial failure
  đã dự kiến, không phải lỗi khiến batch dừng.
- Quality gate: 53 tests pass (32 unit + 21 integration PostgreSQL), Ruff check/format
  pass, pip check pass, lock 70/70. Test delete/update/corrupt/rollback dùng schema riêng.
- Bằng chứng: `docs/ingestion-lifecycle-review.md` và ba CSV
  `data/manifests/ingestion_lifecycle_{resume,first,second}.csv`.

### T2.2

- Ngày: 2026-10-08.
- Cài native Tesseract5.5.2 trong ragschool, vie+eng; pin environment và ghi engine/
  traineddata/config hash. Preparation188 trang: 135 OCR, 53 native text.
- Thêm structural parser/chunker chương/điều/khoản, giữ clause vừa budget, title repeat,
  geometric header/footer, hierarchy reset qua excluded pages và appendix boundary.
- Giữ native/raw OCR/image/TSV/hash/confidence và post-edit provenance. OCR/page/table
  review bind source/cleaned-text hash, không auto approve confidence.
- 1393 so raster2 trang, post-edit giữ công thức, 70 SV, 12 tín chỉ, 1 tháng, điểm M
  và hiệu lực từ ngày ký. Ready/full với 3 OCR chunk.
- Duyệt glossary790/3 và JLPT/NAT956/7; merged tables/flowchart/TOC excluded. 43 đã
  OCR nhưng chưa publication. Snapshot121 pending/23 excluded/4 approved/40 native pages.
- Review32 chunk và validator97/97 token/hash/page-span pass. Migration004 lưu
  structure/extraction/quality/coverage; 4 ready/97 chunk, 11 blocked, re-ingest4 unchanged.
- API smoke3 câu OCR: HTTP200 nhưng2 thiếu amendment context,1 JSON lỗi. Đã giữ cổng
  amendment-in-context, không coi source đã index là đủ để áp dụng base thiếu đối chiếu.
- Quality gate66 tests (43 unit/23 integration) pass, Ruff/format, pip check, pip lock70/70
  pass. Tesseract là native dependency riêng. Báo cáo: `docs/structure-ocr-review.md`.

### T2.3

- Ngày: 2026-10-08.
- Migration005 thêm weighted FTS/simple/unaccent/GIN và triggers chunk/document metadata;
  backfill97/97. Migration001–005 chạy lại skip; DB giữ4 ready/11 failed-blocked/97 unique chunks.
- Keyword query tiếng Việt có dấu/không dấu, mã văn bản và phrase số điều; ranking
  `ts_rank_cd`, không gọi BM25. Publication/model/quality gate dùng chung vector branch.
- RRF k60/weights1:1, candidate20, top5; dedup theo chunk ID, giữ branch/rank/raw score.
  Config default hybrid; API `retrieval_mode` override vector/keyword/hybrid, source provenance.
- 23 câu ×3 mode =69 results. Document hit@1/@2/@5: vector15/16/23, keyword22/22/22,
  hybrid22/22/23. Đây là development document-level smoke, không phải answer accuracy;
  query cache khiến latency hai mode không dùng để so tốc độ.
- OCR01–03 keyword/hybrid top1 đúng1393, API context3/3 có1393. C03 hybrid mất159
  khỏi top2; query chung có thể đúng tài liệu nhưng sai điều khoản.
- Hybrid API smoke: OCR01 answered nhưng quote không trả lời cap12; OCR02 invalid_json;
  OCR03 unverified_quote bị chặn. Manual review CSV giữ cả lỗi; không coi answered là đúng.
- Quality gate87 tests pass, Ruff/format95 files pass, pip check/lock70/70 pass. PDF và
  full-text/results/model trace còn Git ignore. Báo cáo: `docs/hybrid-retrieval-review.md`.
- T2.3 đạt ba chế độ/index/provenance; T2.4 tiếp theo. M2 còn toàn corpus review và
  30 câu development/evidence, metadata filtering cùng hai nhánh.

### T2.4

- Ngày: 2026-10-08.
- Migration006 typed domain/type/audience/date/cohort và metadata trigger. ISO dates/bounds
  cần evidence;790 học kỳ2022-2023 để null, legal_status unknown không coi là current.
- Review956 Điều1 khoản3 PDF2 bind sourceSHA trong `cohort_scopes.csv`; không dùng stale
  review, không suy khóa/hiệu lực từ title/issued year.
- `RetrievalFilters` chung SQL hai nhánh trước LIMIT/RRF; API filters/applied_filters và
  source scope/unknown legal status. Empty/absent không thêm restriction.
- Re-index4 ingested sau config version, vẫn97 unique chunks;001–006 chạy lại skip.
- 30 reference questions do assistant đọc source rồi biên soạn,19 gold chunks bind hashes/
  pages/article/clauses. Manual review30; chưa independent/held-out; public không toàn văn.
- Evaluation180 results: scoped vector hit@1/@2/@5=27/30/30, keyword14/22/27,
  hybrid18/28/30; complete evidence@2 vector29/hybrid28. Scope violations0.
- D07/C03-related duration hồi phục vào hybridtop2; D15 CBPB/D30 Việt-Nhật ngoài context2.
  Vector+filter top1 tốt hơn hybrid trên bộ này; hit không phải answer accuracy.
- Quality gate149 tests (66 unit/83 integration), Ruff/format, pip check/lock70/70
  pass. DB4 ready/11 failed-blocked/97 chunk; M2 blocked publication toàn corpus.

### M2 — Review/publication backlog

- Ngày hoàn tất:2026-10-09. Đối chiếu133 pages của11 nguồn với raster/text, post-edit
  mã/ngày/điều kiện và serialize43/308 tables; không approve theo confidence.
- Giữ412+513; verifier307 token/hash/span pass. Supported scope15 ready/307 IDs;
  page status103 approved/40 native/45 excluded/0 pending;832 mixed layouts partial.
- Source metadata review bind hashes;851 start01September2024;277 cohortfrom2024;
 308 cohort2025-only bỏ vì không có evidence;112/697 source inconsistencies giữ notes.
- Publication hai lượt:15 ingested rồi15 unchanged,307 FTS/0 unfinished;19 development
  goldchunks giữ nguyên. Docker dừng gâytimeout đã recovery và rerun sạch.
- Expanded development30 scopedmetrics vector27/30/30,keyword14/22/27,hybrid18/28/30;
  unfiltered hybrid11/16/23.12 newprobes documenttop1 vector9,keyword12,hybrid12.
- API smoke giữ cả lỗi: M204 answered wrongcohort2012 thay2018; ba scopedcases còn
  schema/quote/JSON failure. Không tính statusanswered hay document hit làm accuracy.
-156 tests (67 unit/89 integration), Ruff/format/pip check/lock70/70 pass. M2 đạttechnical
   supported scope, không phải answer quality. Báo cáo `docs/m2-corpus-review.md`.

### T3.1 — Reranker và freshness

- Ngày:2026-10-09. Pin mmarco-mMiniLMv2-L12-H384-v1 revision1427fd652930e4ba29e8149678df786c240d8825;
  CPU/batch1/2threads; window512/32/max-pooling, raw logits riêng retrieval scores.
- Verify15 source issue dates và1393→790/513→412 amendment maps theo source/content hashes;
 697→244/894→172 replacement witnesses. Freshness chọn theo verified family, không globalnewest.
- Portal hai publicpages/15PDF re-fetch:15 unchanged/listed, sourcechecks UTC08:23 ngày09October2026.
  Metadata refresh giữ15unchanged/307chunks/19goldbindings; không đổi schema/embedding fingerprint.
- Catalog nhìn cả blocked/latest outsideallowlist; oldaffectedclause bị loại, companions được
  reserve; filters/budget/missing/hash/revision/quality/latest-source drift dẫn abstention.
  Historical as_of không buộc futureamendment. Shared querydocumentrefs trướcLIMIT cả hai nhánh.
- Hai lượt216rows:30candidate→20candidate+sharedrefs. Final scoped goldtop1 vector27,
  hybrid-off18,hybrid-on29/30; top2/top5 hybrid-on30/30. Unfiltered hybrid-on28/28/30.
  Scope/missing-update violations0; identifiers12/12. Stagep50 scoped4.653s/unfiltered9.110s.
- API12 realrequests HTTP200:1supported M212/894 (30paperdegree/5digital),1expected stalefilter
  abstention F05 khônggeneration/208ms. Các case khác invalidJSON/unverifiedquote/sourceID;
  M204 correctrow ởS2 nhưng modelciteS1, bị chặn. End-to-end CPU p50~104s/p95~153s còn blockerUX.
- StoredAPI audit source hashes/excerpts/scopes/latestanchors/citations pass;187tests
  (88unit/99integration), Ruff119files/pipcheck/lock70 pass. Tiếp theoT3.2, chưa M3complete.

### T3.2 — Bound passages/citation support

- Ngày2026-10-09. LLM chọnPIDs, backend resolve nguồn/offset/textSHA vàdựng answer;
  no model-copy/URL/page. Llama grammar enum perrequest, strictparse/duplicatechecks,
  tốiđa1structuralretry; rawattempts ignored. Legacyquotes giữ validator cũ.
- Atomicconditionblocks/no midcondition truncation; supportfacets/queryprogram/date
  vàsignaturedependencies. Lowmemoryrelease E5/CE trướcLLM vàGGUF finally.
- Config`rag-bound-passages-v3`, output64/input2304/max8passages/context6;
  archivequotes `configs/rag/quotes-v9.json`. Corpus15/307/gold19/FTS giữ nguyên.
- Acceptance12 realAPI:11answered primarysource-supported,1expectedF05 no-gen;
  p5013.572s/p9525.958s vsT3.1~104/~153s. Audits0binding/citation/filter/latestviolations.
- Development30 finalrun29answered/1falseSVabstention; manualfindsD13wrongtopic,
  D26wrongschedule vàD28/D29overinclusiveprogramme, đãsửa/reruntargeted; giữfailures.
  Một sốcases cònextra material, khôngghép các reruns thànhheld-outaccuracy/latency.
-210tests109unit/101integration, Ruff124files/lock70/pipcheck pass. T3.2complete;
  nextT3.3 clarification/scope vàT3.4 behavioralacceptance. `docs/passage-citation-review.md`.

### T3.3 — Clarification/abstention

- Ngày 2026-10-10. Policy `clarify-scope-v1`, pipeline `rag-scoped-answers-v1`;
  optional request `scope`, response clarification/resolved_scope/requested_filters/
  applied_filters/version_notes. Missing/conflicting scope hỏi lại trước retrieval/model.
- Explicit cohort/audience/date thêm filter còn trống, programme/design duration lọc
  passage; không thay caller filters hoặc suy hiệu lực từ ngày ban hành. Nguồn cụ thể
  tách khỏi áp dụng cá nhân; 43 historical/current fee và legal-status-unknown abstain.
- Complete behaviour20: 8 clarification / 7 abstention / 5 supported answers, 20 HTTP200,
  chỉ 5 generation; 0 binding/citation/filter/latest errors. Clarification 22–131 ms.
- Positive12: 11 primary supported answers + 1 old-only-filter abstention; p50 20,279 ms,
  p95 43,983 ms, mixed cold/warm. Không so tốc độ policy từ tải CPU/RAM khác nhau.
- Frozen development30: 30 answered nhưng D23 wrong progress/prerequisite topic;
  manual 29 primary supported. Guard prerequisite mới và annual-unit fix rerun D22/D23/D26
  đúng; reaudit output cũ reject D23 và lưu failure. Không ghép thành single-run30/30.
- Corpus 15 ready/307 chunks/307 FTS/15 unchanged, 19 gold bindings nguyên vẹn;
  103 approved/40 native/45 excluded pages, 0 unfinished ingestion runs.
- Docker dừng làm một pytest timeout; đã recovery. Final 247 tests (143 unit/104 DB)
  pass; Ruff/format/pipcheck/lock70 sạch. Báo cáo `docs/clarification-abstention-review.md`.
- Người dùng yêu cầu commit sau mỗi bước hoàn tất từ đây; ghi tại `AGENTS.md`.
  Commit T3.3 là initial commit của trạng thái project đã kiểm chứng đến bước này.
  Tiếp theo T3.4 ít nhất20 adversarial/ngoài phạm vi cases; M3 chưa nghiệm thu.

### T3.4 — Adversarial behaviour / M3

- Ngày2026-10-10. 24 câu khai báo expected status/facts trước pilot,10 synthetic context
  fixtures. Pilot16/24 và3/10 pass; giữ8out-of-scope/fabrication và7injection/topic failures.
- Scope task/institution rules trả insufficient trước retrieval/model; context hash đúng
  vẫn không cho assistant-control instructions. Whole-context abstention giữ companions,
  không strip/rebind text. Escape chat markers dùng chung llama/Transformers.
- Config `rag-guarded-passages-v1` / `guarded-behaviour-v1`; model pins/embedding fingerprint
  không đổi. Final24/24 (11supported/13abstain), injected10/10 (2controls/8abstain).
- Positive12 giữ11supported/1old-filterabstention; p50/p95 21,987/38,628ms mixedcold/warm.
  Source/citation/filter/latest audits0errors; không dùng medianadversarial làmLLMbenchmark.
- 276tests169unit/107schema-isolatedDB, Ruff/format/pipcheck/lock70 đạt. FixtureSharedQuery
  sửa contenthash phù hợp text, không thay runtimehashguard hoặc frozen19gold bindings.
- Corpus15ready/307chunks/307FTS/15unchanged/0unfinished,307bodychunks không có detectorhit;
  source PDF/hash và19gold nguyên vẹn. Allraw/model traces ởignored processed.
- MandatoryT3.4 vàM3 technical gate đạt; structuredscope/stateless không rewrite.
  Báo cáo `docs/adversarial-behaviour-review.md`; nextT4.1 dataset100 vàheld-outfreeze.

### T4.1 — Dataset100 / held-out freeze

- Ngày2026-10-10.100canonicalcases trong `data/evaluation/v1/`:30single/20multi/15scope/
  15noanswer/10clarification/10adversarial;60dev/40test;expected75answered/15insufficient/10clarify.
- 30queries/answers/filters/19gold giữ nguyên; mởrộng30development,40newprospective test.
  98paraphrasegroups/68rulefamilies và11exposureregistries đượckiểm khôngcrosssplit/tunedtest.
- 72curatedspans/49approvedchunks, SourceURL/source/content/excerptSHA,Unicodeoffsets,
  PDFchunkranges/locator/article/clauses/quality;contrast khôngđượcpromotegoldanswer.
- Assistantmanualsource/behaviourreview100cases, inheritedM2page/hashreview; chưaindependenthuman.
  Không RAGinference trênheldout; metadata/gold SELECT only, commoncorpus khôngdoc-disjoint.
- FreezeUTC10:45:33/datasetSHA `d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c`,
  baseline runtime040dd30. Refreeze attempt rejectexpectedexit1, resultlưu riêng; lockunchanged.
- Full300tests188unit/112schema-isolatedDB,109.19s,Ruff/pipcheck/lock70 đạt; Corpus15/307/
  19gold/0unfinished giữ nguyên. `docs/evaluation-dataset-review.md`,nextT4.2 chưaM4complete.

### T5.1 early — UI/manual test trướcT4.2

- Ngày2026-10-10,user yêu cầuUI demo trước evaluationrunner. UI/UXProMax verified
  knowledge-docs/Swissdesign,slateblue/light,tokens/focus/reducedmotion/nativeSVG; master/pageoverridepersisted.
- FastAPI `/`/webassets vàcatalog publicmanifestdefaults,sameoriginask; noNodebuild/UIruntimepackage.
  Explicit scope/filter/4devpresets,backendanswer/citation/source/excerpt/versionnotes,3statuses,
  loading/elapsed/error/stopwaiting,session-onlyfeedback vàexportactualJSON.
-27browserfixturechecks/18realbrowserchecks5requests đạt. Cap12/1393,clarify rồiscopeCTA
  cap16/IEL05,old790onlyfilterabstention,851effect01Sept2024. Firstask~24.4s; khôngheldoutbenchmark.
- Axeinitial/result0A/AAviolations; responsive375/812landscape/768tablet/nohorizontaloverflow;
  textnodes+safeURLs/XSS/citationfocus/dialogEscape/network503/abort tested. Screenshots/records ignored.
- MIMEWindowsmjs banđầutext/plain gâypilotfail; app-localJScontenttype fix vàQAfullrerun pass.
 303pytest191unit/112DB+12Nodepass,Ruff/pipcheck/lock70clean. Datasetfreeze d577... giữ nguyên/0testinference.
- UI/serverlocal127.0.0.1:8000 đãstarted/HTTP200/healthok/catalog15,Conda wrapperPID21564 tạihandoff.
 `docs/demo-guide.md` córestartcommands và5manualflows. NextT4.2 sauuserreview, chưaM4/M5complete.

### Demo feedback — GPA / điều khoản không bị sửa đổi

- Ngày2026-10-10. Pilotquery GPA trả hè12 hoặc790-only bịlatestexcluded; rawtarget
  cosine0.8888168 vượt0.55.1393 chỉ sửa14.1(b), không phải1(a)mainsemestercap30.
- Source/hash-bound item witness +parent1→a→b tạo Unicode view trên chunk/hash gốc;
  unaffectedarticle24 không cần unrelatedcompanion. Applicable amendments/replacement/
  unknownhierarchy/source drift/filters/requiredcompanions vẫn được kiểm.
- Pipeline `rag-clause-scoped-v2`, freshness `clause-scoped-v2`; threshold0.55/modelpins/
  corpus/metadata/relationmanifest/frozenQA giữ nguyên. Olddocument không bịagefilter.
- Finalverified8:6primarysupported/2correctabstain, p508.761s/p9517.572s;
  fixed12:11supported/1correctabstain, p5010.591s/p9515.609s. Bothaudits0source/span/
  citation/support/filter/latestviolations. Pilotreaudit rejectG01/G02 vàgiữfailure.
-322tests208unit/114schema-isolatedDB/75.66s, Ruff153files/12Node/lock70/pipcheck pass.
  Frozen100 datasetd577.../legacy30/19gold/corpus15/307/0heldoutinference giữ nguyên.
- Live8000 đãrestart:Python16956/Condawrapper38292;22Edgebrowserassertions/5requests
  đạtcap30/all/790-only,summerabstain vàpersonal-domainclarification/explicitaudiencereply.
  Browserpilot inheriteddomainmissingaudience giữfailure; QA sửa setup, không bỏscopeguard.
- `docs/gpa-credit-freshness-review.md`, `gpa_credit_*`aggregates/manualreview; fullsource/
  modeloutputs/screenshots ignored. Chốt hotfix, T4.2 vẫn pending sauuserreviewdemo.

### T4.2 — Evaluation runner

- Ngày2026-10-10. `python scripts/run_evaluation.py` tạo requiredreports mộtlệnh,
  defaultdev60;read-only source/freeze pre/post-flight,rawpredictions flush/ignored.
  Actualrank10samepool,answerdefault8/context6/budget2304; no gold vàoLLM/noextraModelcall.
- Semanticmanualreview60 requiredfacts/actors/conditions vàactualcitedblocks bind
  prediction/responseSHA. Proxyspancoverage không thaycorrectness; nDCG N/A binarylabels.
  Input/outputprovider tokens sum retries; timingretrieval/CE/generate/e2e vàsamples rõ.
- Full60:46answered/9insufficient/5clarify,60HTTP200; status59/60, facts57/65,
  completecorrect41/47 (87.23%), citationtask-support52/71 (73.24%), faithful71/71.
  Recall5=.98936/10=1,MRR10=.96454;complete@10=47/47;noanswer8/8correctreject.
- Multi7/12đủý;D33/D34/D36/D37partial,D38wrongtopic,D42falseabstention,D51missingprogress.
 19extrablocks/14distinctissuecases giữtraces/reviews; khôngsửaModel/gold trongmeasurement.
- p50/p95e2e13.270/18.282s,all60mixedstatus/coldwarm;activeLLM46 p504.354/p958.462s.
  Input25588/output479 actualselectionJSONtokens,API0VND/localcomputeunpriced.
-339tests223unit/116DB,97.63s;targeted20/re-score noModel/hash/overwrite guards;
  Ruff163files/12Node/lock70/pipcheck pass. Frozen100/legacy30/19 vàcorpus15/307giữ nguyên,
  0heldoutinference. Publict4_2metrics/decisions/integrity/snapshot; rawevals/results ignored.
- T4.2technicalacceptance đạt, M4 in_progress; nextT4.3 fourretrievalvariants rồiT4.4,
  citation90%/p95target10s chưađạt. `docs/evaluation-runner-review.md`.

### T4.3 — Benchmark / ablation

- Ngày2026-10-11local, inferenceUTC10October15:47–16:51;4freshprocessvariant runs
  cùng60dev/models/prompt/budget/corpus/candidate20/evaluator;topk4/8/12samecontextceiling6.
- Full360actualpredictions;77actualsemanticgroupsmanualreview, strictsource/quote/scope
  equality/newPID/SID/responseSHA for everyrow. ExistingT4.2review không đượcghépreruns;
  alltopkoutputs exactlymatchedalreadyreviewedgroups, newmemberbindingsverified.
- Vector/KW/RRF/CE Recall5 .98936/.85106/.94681/.98936,MRR .89787/.65674/.75641/.96454;
  fullcorrect41/35/36/41of47;taskcitation53/75,45/69,48/71,52/71. Reject7/7/8/8of8.
- CE vsRRF paired5wins(D16/27/40/58/59),0loss;extraCEtime, e2ep50/p9513.000/20.997s
  vsRRF6.572/14.032. VectorprimaryequalCE nhưngD43falseanswer+lowerprecision.
- Topk4/8/12identicalclaims/tokens/41of47quality;predeclaredobservedlatencytie-break
  selectsCEk4,p50/p9512.441/17.820s;notcausalspeedup. SelectedconfigSHA611919f4...,
  configs/rag/t4_3_selected.json+selectionseal; Source/runtimeSHAa6d5fe1f... base9987bca dirty.
-354tests237unit/117DB107.01s,Ruff171files/12Node/lock70/pipcheck. SelectedGPA8smoke
  6supported/2correctabstain/audits0;rawtraceignored. Frozen100/30legacy19/corpus15/307
  keepbinding,0heldoutinference. Allfailurecases/protocol/CSV/comparison/reviews retained.
- T4.3 completed; nextT4.4 completeness/precision/falseabstention/clarificationfixes then
  finalreleaseconfigfreeze andtest40. `docs/benchmark-ablation-review.md`.

### T4.4 — Error analysis / final release / M4

- Ngày2026-10-11. Inventory20cases/19queries: generation5/citation7/retrieval6/
  abstention1/clarification1; không có evidence parsing/OCR/chunking/reranking là primarycause
  ởinventory này. Source/hash/quality/filter/latest/corpus/immutablegold/exposureregistries giữ.
- Ba nhóm: lexicalmulti-obligations +sameguardedpoolproviderreservation +minimumfullcoverage;
  explicitcalendar khácunitcount; strictstudy_progress0–40 quaAPI/UI/clarification.
  AbsentNoneexcluded giữdatasetSHA d577..., không infersemester từcohort/issuedyear.
- Pilot14:13/13answerable/21of21facts/20of20taskcites; fulliteration1:46/47correct
  (D06model chọnsignatureP2riêng). Giữfailure, exposebounddependency/signature_date trongprompt,
  targetedD06pass rồi fullfinal60 exactcode:47/47correct/65of65facts/60of60taskcites;
  Recall5/10=1/MRR=1;reject8/8/false0/47;clarificationfields12/12;status/filter/fidelity60/60.
- ReferenceT4.3CEk4:41/47/57of65/52of71→final47/47/65of65/60of60; multi7/12→12/12.
  Finalp50/p9512.351/15.824s,input28862/output443; onepass khôngcausalspeedupclaim.
- FreezeUTC07:10:12.468742, confige1933332.../sourceca2b3803..., fullreviewed60;
  testledgerclaim07:11:38.800029, complete40test07:11–07:26UTC, pre/postreleasechecks pass.
  Runtimebased18cbe4+dirtyT4.4exactbytehash; pipeline `rag-obligation-support-v3`,
  configs/rag/final.json/top4/CEon/samepins/budgets/freshnessv2.
- Held-outmanualreview40:19/28correct(67.86%),32/43facts,29/108taskcitations(26.85%);
  sourcefaithful108/108/filter/citationfidelity40/40,Recall5/10=1/MRR=.9375.
  Correctreject0/7,false2/28,clarificationstatus1/5/requiredaxes0/20,status27/40.
  p50/p9521.552/32.707s,input44519/output576,37generation,API0VND/localcomputeunpriced.
-21qualityfailures giữ: partialT10/13/14/15/22, falseabstainT16/20, wrongtopicT36/38,
  unsupportedrequestsT24–30 vàmissingclarificationT31–35. T16literalconditionsfacet vàT20
  doc112nexttoSVcountintentmisparse; chỉpost-testdiagnostics, khôngcode/config/goldtuning.
-370tests253unit/117schema-isolatedDB,Ruff/format180files/13Node/lock70/pipcheck đạt;
  GPA8 giữ6primarysupported/2abstain,fixed12 giữ11/1,adversarial24contracts24/24,
  source/span/filter/latest audits0. GenericprobeG08/B07 cònextraquotedmaterial.
- EdgeQA27fixture/18realpreset/22realGPA assertions;10developmentrequests,explicitCTA/
  progress3→cap16/IEL05,presetclear/unchanged790GPA/sourceproof/Axe/responsive đạt.
  LocalAPI8000Python38296 đãloadfinalv3; DBhealthy,rawlogs/screenshotsignored.
- Read-only revalidate100/72spans/49chunks/legacy30/19/datasetfreeze unchanged;
  corpus15ready/307unique/307FTS/15unchanged/0unfinished,103approved/40native/45excluded.
  Validatoroperation0testinference khác tổng **40testrequests đã chạy**.
- M4methodology/artifacts nghiệm thu đạt; correctness/supportprecision/rejection/p95targets
  held-outchưađạt. Giữlocaldemo/evaluation snapshot; nextT5.2 vàqualityevidence mới.
  `docs/error-analysis-review.md`, `t4_4_*`ID-only metrics/manualreviews/failures/freeze/ledger.
- Finalrubric check creditT07P4partialprioritysupport(F1) dù trùng ý; score-only29/108
  thayinitial28/108, noextraModelcall/gold/codechange. Correctionlog vàinitialboundreview giữ.

### T5.2 — Observability

- Ngày2026-10-12. ServerUUID trảX-Request-ID/bodyrequest_id, ASGImiddleware/ContextVars
  truyền từasync sangsyncworkers/retrieval/generation; boundedJSON `pipeline-trace-v1`.
  Parent/spanIDs/start/duration/skipped/error_type, queuewait riêng vàresetcontext từngrequest.
- Snapshot actualbranch/fusion/freshness/CE-before-after/guardedorder/topk/context/registry/
  chosen/resolved/citedIDs/offsets/SHA/dependencies; samecalls/modelinput/sourceguards.
  Actualproviderusage sumretries;unknownnull≠nogeneration0;localAPIcost0/computeunpriced.
- Metadataallowlist64spans/100chunkrows/16passages/160charstrings/omittedcounts, noquery/
  answer/source/prompt/rawmodel/header/DSN/exceptionmessage intrace; httpxINFOquiet,
  Uvicornnoaccesslog. RequestID còn có khitraceflagfalse; sinkerrorskhôngđổiinferenceresult.
-7/7checks:4realdevcontrols,wrongselectorfixturewithrealretrieval,backenderrorfixture,
  validation. O02actualB07citesP1/P3extrafamilyrule; O05onlyP2→incomplete_passage_support
  atresolve dùrule/signature trongcontext; diagnosedkhôngfixquality/tuneheldout.
- O01coldquery.embed30.904s,generationusage592/11; O02generate12.450s; timingsdiagnostic,
  parentinclusive khôngadditive/causalbenchmark. LiveHTTP ID9e9fd74e...header=body=JSONlog,
  inspectorcomplete30spans/cited1393effect+signature;52.526s/equivalentcoldembed30.836s.
-383pytest266unit/117schema-isolatedDB,13Node,Ruff/format186,lock70/pipcheck đạt;
  13newtrace/privacy/error/queue tests, traceon/offoutputsame,mockdelegates1call,
  concurrentIDsisolated/queue≥20msfixture,422/503/500/type-only/errorsink/disabledverified.
- Dockerđầustepdừng, mởlạiDesktop/dbhealthy. FinalAPI8000Python25460/ragschool,
  finalmodelconfig/tracingtrue/--no-access-log;rawlogs/response/tracefilesignored.
- Frozen100/72spans/49chunks/legacy30/19/d577... giữ;corpus15/307/307FTS/15unchanged/
  0unfinished/103approved/40native/45excluded. T5.2operation0testinference,globalvẫn40.
- OriginalM4freeze/sourcehashca2.../predictions/reviewsđúng221ee6f; telemetrycode làsourceversion
  mới,nêncurrentcheck_release vớioldfreezephảimismatch, khôngoverwrite/bypass đểgiảreproduction.
- Langfuseoptional deferred; localJSON/CLI đạtT5.2mandatorycriterion. Noexternalupload/
  dependencies/traceDB. NextT5.3,logrotation/storage/operatorretention còncôngviệc riêng.
