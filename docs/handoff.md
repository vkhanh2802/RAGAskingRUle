# Session handoff

## Hiện trạng

- Milestone: M2/M3/T4.1–T4.4/M4/T5.1earlyUI/T5.2/T5.3 completed;
  held-outquality targets chưađạt, M5 cònT5.4portfolio/video/interview.
- Task vừa hoàn thành: T5.3Docker/Compose/wheel/setup/localdeployment8001vàGitHubActions2jobsgreen;
 387tests/13UI. M4test vẫn19/28correct/taskcitation29/108/reject0/7.
- Task tiếp theo: T5.4; qualitybacklog cần evidence/testset mới.
- Git: T3.3 `3407c07`,T3.4 `040dd30`,T4.1 `e8cc367`,UI `61f437f`,GPA `01ecdbe`;
  T4.2 `9987bca`;T4.3 `d18cbe4`;T4.4 `221ee6f`;T5.2`d5ddd5a`;T5.3feature`da840c7`,
  closuredocscommit sauhostedCI, mãcuối xem `git log -1`.
  Theo yêu cầu người dùng, mỗi bước hoàn tất kiểm chứng phải commit rồi báo mã/kết quả;
  quy tắc lưu trong `AGENTS.md`.
- Runtime: DockerDesktoplocaldeployment **http://127.0.0.1:8001/**,servicesregularag-api-1/
  regularag-db-1healthy,pinnedPG17/originalDBvolume/namedHFCacheroot,finalmodelconfig/tracev1.
  Composeprofileapp runbookREADME; native8000/Python25460 làT5.2historicalentrypoint cầnverifyPID
  trướcstop/restart. Ownedfreshproofprojectports55432/8002/DBvolume đãcleanup,suppliedhostassets giữ.

## Đã thực hiện

- Tạo Conda environment `ragschool` với Python 3.12.15.
- Cài 70 package đã khóa, gồm FastAPI, Psycopg, PyMuPDF, PyTorch CPU,
  Sentence Transformers, Transformers, llama.cpp CPU, pytest và Ruff.
- Tạo `pyproject.toml`, `environment.yml`, `requirements.lock`, `.env.example`.
- Tạo FastAPI app, structured JSON logging và `/health` kiểm tra cả PostgreSQL lẫn
  extension pgvector.
- Tạo `compose.yaml` và `scripts/db/init.sql`.
- Hiện có387 tests (270 unit/117 PostgreSQL integration với schema riêng),13NodeUIcontracttests.
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

## T4.1 — Hiện trạng mới nhất

- `data/evaluation/v1/`:authoring/questions/evidence/manual_review/freeze.100cases đúng
  category30/20/15/15/10/10,60dev/40test;gold statuses75answered/15insufficient/10clarify.
- D01–30 vẫnoriginalqueries/answers/filters/paraphrasegroup/19goldchunksets;D31–60devexpansion;
  T01–40prospectivequestion/familyholdout.98groups/68families và11priorinputregistries kiểm leakage.
-72curatedsource spans/49chunks; source/pagerange/excerpt/Unicodeoffset/SHA bindings.
  Source_pdf_pages làchunkrange cóthểcoarse;articlemetadataNone giữNone, khônginventĐiều4/PET.
- Review100cases doassistant đốichiếuapprovedsource/conditions/roles/metadata; khôngindependenthuman.
  Noheldout E5/CE/Qwen/APIinference trongconstruction, khôngruntime tuning từtestlabels.
  Commoncorpus vàknownsourcechunks, không document-disjoint/blind test.
- FreezeUTC2026-10-10T10:45:33.610837+00:00,datasetSHA d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c;
  baselineconfig/runtime040dd30. Builder/validator khôngoverwrite lock. Refreeze rejection lưu
  `t4_1_refreeze_rejection.json`,valid rechecks giữlock. Loaderdefault chỉdev60; testexplicit.
- 300tests/Ruff/lock70/pipcheck pass; Corpus15ready/307FTS/19legacygold unchanged.
  `docs/evaluation-dataset-review.md`, `t4_1_*` validation/publicationsummaries.
- NextT4.2:runmetrics trêndevelopment trước; T4.3 chọnconfigcuối rồi heldout/T4.4reportfailures.
  Frozen labels làexpectedbehaviour, chưa modelaccuracy75/100 hoặcanswerbenchmark.

## EarlyT5.1 — UI demo hiện tại

- NativeHTML/CSS/ESmodules trong `src/regularag/web/`, sameFastAPI `/assets` và `/`;
  catalogpublicmanifest/configdefaults,no rawpaths/models/heldoutqueries. BackendRAGunchanged.
- UI/UXProMax master`design-system/regularag/MASTER.md`/pages/demo override,readability/
  highcontrast/slateblue/focus/reducedmotion,localfontfallback,noCDN. Desktop/mobileverified.
-4presetsdevelopment,typedexplicit scope/filter,actual3statuses/citation/excerpts/latest/
  sourcewarnings. Scope reply giữoriginalquestion; presetsnạp filtertươngứng/xoáscopecũ.
- Loading/elapsed/stopwaitinghonestclientabort, khôngcancelPythonclaim; textnodes/safeHTTPURLs
  vàonlyreturnedSIDbuttons, no fakeprogress/confidencemeters. Sessionfeedback/exportnoDBpersist.
-303pytest+12Nodepass;27browserfixturechecks+18actualbrowserchecks/5requests,3supported
  answers/1clarify/1correctabstention. AxeautomatedA/AA0violations,notfulla11ycertification.
- WindowsmjsMIMEfixapp-local; failedpilot/successreports`demo_ui_*`manifests, fullscreenshots/
  responses/exportignoredprocessed. OptionalPlaywright/axeQAtooling ởTemp, khôngUIdependency.
- Dataset100/legacy30/19/source/corpusguards giữ nguyên,0heldoutRAGinference. `docs/demo-guide.md`
  hướng dẫn chạy/test; root8000 HTTP200/healthok/catalog15. T4.2 vẫnnext, M4 chưabenchmark.

## Kiểm chứng

### T4.3 hiện tại

- Matrix `evals/results/t4-3-ablation/`,4modes60each +CEk4/k12sweeps=360predictions,
  samefixedsource/model/prompt/candidate20/context6/input2304/output64/freshness/gold.
  Onlydeclaredmode/CE/topkaxes; source/config/runtime/hardware/roster/predictionhash gates.
-77uniqueactual question/quote/source/scopebundles readmanually andjudgedfullconditions;
  newlocalPID/SID/responseSHA eachrun. Topk120all exactsamegroups; no newfactlabels fromproxy.
- Correctness vector41/KW35/RRF36/CE41of47;taskcitations53/75,45/69,48/71,52/71;
  noanswercorrect7/7/8/8of8. Vector/KW D43wrongtopicfalseanswer, notold50claim.
- CEvsRRF paired5winsD16/27/40/58/59,no loss;MRR .75641→.96454,p5013s vs6.572s.
  Samequalitytopk4/8/12,latencytie-breakselectCEk4p50/p9512441.294/17819.716ms;
  onepassOS/hostnoise notcausal. Modeltoken25588/479 eachCE;API0/localcomputeunpriced.
- Selectedreference **configs/rag/t4_3_selected.json**,SHA611919f4... beforeheldout;
  T4.4 fixesfinalreleasefreeze later. selectedsmokeGPA8 6supported/2correctabstentions,
  old790main30/summer1393cap12/affectedfilters unchanged; audits0errors.
-354tests107.01s,Ruff171files/12Node/lock70/pipcheck;dataset100/72spans/49chunks/
  legacy30/19/corpus15/307unchanged,0heldoutinference. SourceSHAa6d5fe1f...,
  inferencebase9987bca+dirtycode captured inconfigs/protocol.
- Publict4_3CSV/core+fullcomparison/reviews/protocol/selection/integrity/smokeaudit;
  rawquotedreports/modeltraces ignored. `docs/benchmark-ablation-review.md` hasfulltables.

### T4.2 hiện tại

- Onecommand `scripts/run_evaluation.py`, default60development; verify frozen100/source/
  corpus/quality/embedding pre/post-flight. Gold không vàoModel; rawoutputs/quotes ignored
  `evals/results/`. `--score-only`/manualdecisionsSHA dùngnomodel, không đổi predictions.
- Observerranked10samepool, originalanswer8/context6/budget2304; actualstage timers và
  usage_input/output_tokens sumgrammarretries. API/schema nội dungask giữ nguyên.
- Fullrun `t4-2-development-clause-v2`:60HTTP200/46answered/9insuf/5clarify;60manualreviews.
  Recall5=.98936/10=1/MRR10=.96454;41/47correct/57of65facts;citationtask-support52/71,
  sourcefaithful71/71;filter/citationfidelity60/60;correctreject8/8,false1/47.
- Multi7/12complete. MissingF2D33/F1D34,F1D36,F1D37,bothD38;D42missingsupportfalseabstain;
  D51needsstudyprogressquestion. Extrapassage issuesD03/08/10/16/20/27/38/57. 14issuecases
  preserved, not fixed inT4.2; nDCG N/A binarygold. Status59/60 không làfullcorrectness.
- E2eall60p50/p9513269.526/18281.750ms; CEactive50,LLMactive46,per-stageall/activequantiles.
  Input25588/output479actualtokens;API0VND,localcomputeunpriced. Windows12logicalCPU/
  CPUthreads2/4/cacheoffline/serial1/mixedcoldwarm; optionalRAMreading unavailable.
- Inferencebasecommit01ecdbe+T4.2dirtytree,exactruntimeSourceSHA559fde0a...;configSHAf6e9a4ae...
  andpredictionsSHA907d62d9... saved. Baseline.json/modelpins/fingerprint/gold/corpus unchanged.
-339pytest97.63s+targeted20,Ruff163files/12Node/lock70/pipcheck pass. Sourcefreeze100/72spans/
  49chunks/legacy30/19/corpus15ready307FTS unchanged,0heldoutRAGrequests.
- `docs/evaluation-runner-review.md`, `evals/README.md`, `t4_2_development_metrics.json`,
  `t4_2_development_decisions.json`, integrity/publicationsnapshots làfinalevidence.

### GPA / clause-scoped hotfix hiện tại

- Rootcause:1393 chỉ sửa79014.1(b)hè, oldwholeclause14:[1] đã mất1(a)main/GPA.
  Densequerytarget0.8888168>0.55; threshold/modelpins không đổi, khôngagefilter nguồn.
- `retrieval/registration.py` phân biệtmain/summer/languageprogress và explicit hierarchy;
  Freshnessv2 tạo unchanged view từ bound item witness, chỉ relevantupdate cầncompanion.
  `evidence_char_ranges` bindfulltext/hash gốc; passage resolver reject ngoài view.
  Source/fullreplacement/unknownmetadata/filters/required-update guards giữ strict.
- Querygốc/all/790-only trả30mainsemester; ĐTBC7,5 giữ14–24 vàconditional30cho≥8;
  explicit hè dùng1393cap12;790-only hè/classsize abstain;790Điều24 vẫn usable.
- Finalverified8:6supported/2correctabstain,p508761ms/p9517572.35ms;
  fixed12:11supported/1correctabstain,p5010590.5ms/p9515609.35ms. Allspan/freshness audits0.
  `gpa_credit_verified*`, manualCSV và `docs/gpa-credit-freshness-review.md` làfinalevidence.
-322pytest/75.66s, Ruffcheck/format153files,12Node,lock70/pipcheck sạch.
  Frozen100/legacy30/19/source/corpus15/307 unchanged,0heldoutRAGinference.
- Live8000:22browserassertions/5requests;3answers/1abstain/1clarification; sourceview/
  citations/provenance/mobile/Axe checks pass. FirstbrowserQA wrongly inheritedpresetdomain
  thiếuaudience; API hỏi lại đúng. Failedpilot giữ riêng; final còn kiểmexplicitreply.
- Python16956/Condawrapper38292; logs ở Temp/opencode `regularag-gpa-demo-20261010-201303-*.log`.
  Launchtool báo lỗi harness nhưng probes xác nhận server started/healthy; không spawn bản trùng.

### Các mốc kiểm chứng trước hotfix

- `conda run -n ragschool python --version`: Python 3.12.15.
- `python -m ruff check .`: pass.
- `python -m ruff format --check .`: pass.
- `REGULARAG_RUN_DB_TESTS=1` và `python -m pytest`:303 passed; Nodecontract12pass.
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
  pipeline `rag-clause-scoped-v2`, freshness `clause-scoped-v2`; reranker/behaviour enabled,
  low-memory generation. Behaviour vẫn `guarded-behaviour-v1`.
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
- Finalretrieval hybrid: top4/candidate20/CEon +guardedobligationproviderreservation,
  rrf_k60/weights1:1; baselinev2JSONtop8 vẫnarchivedreference. Cosine>=0.55 áp trước
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
  filter khôngđược nới và sẽabstain nếu relevantamendment cần1393. Unchanged1(a)/Điều24
  có thể dùng790. as_of không suy từcohort/issuedyear; oldsource khôngagefilter.
- Reranklogits khôngconfidence; giữ raw scores/modelrevision riêng. Candidate20 chọn
  sau lượt30 chậm; sharedrefs cũng đổi, không attribution toàn bộ cho candidatecount.
- Explicit bound1(b) witness +clearhierarchy đã cho phép view1(a); unknownboundaries
  vẫnwhole-clause conservative, generalfiner-grainedviews cần source-bound review.

## Blocker

- Latestheld-out40:19/28completecorrect/32of43facts/29of108taskcites/reject0of7;
  clarificationaxes0of20,p9532.707s. Binding/faithfulquotes đạt nhưng relevance/answerability/
  generalpersonal-eligibility còn hạn chế rõ; xem `docs/error-analysis-review.md`.
  Giữfrozenresults/code/config, không tune từT01–T40 rồi gọi lại làheldout.

- Không còn document/page publication pending. Supported scope có45 excluded pages,
  gồm TOC/blanktemplates/diagram và chưa durable row-column tables;832 bỏ regions3/5.
-43 đã OCR/table serialization/full publication, còn legal_status unknown và phạm vi
  lịch2012–2019. SQLcohortfilter vẫndocument-level; T3.1 promptfocus chỉ chọnliteralrow
  khi câu hỏi nêu rõcohort/design duration vàrow duy nhất, chưa giải quyếtmọi ambiguity.
-697 extension fee/remuneration swimlane,790 grade table và956 merged tables còn ngoài
  evidence hỗ trợ. Không coi15ready là toàntext hoặc hiện hành pháp lý đã chứng minh.
- Model nhỏ còn lỗi output/selection; retrieval có thể đúng tài liệu nhưng sai đoạn.
  Scope/facets hiện lexical, chưa general entailment. Câu hỏi chung còn extra material.
- Lịch sửhybridC03/OCR01wrongtopic giữ trongreports; hiện fixed12 có11primarysupported/1abstain.
  Gold theo clause vàmanualreview vẫn làbắtbuộc; status/quotevalidation không thayaccuracy.
- Một deprecation warning trong FastAPI/Starlette TestClient còn tồn tại; không ảnh
   hưởng runtime và chưa cần đổi sang thư viện `httpx2` chưa ổn định trong baseline.
- Lịch sửT3.1 1of11generationcalls supported/median104s được giữ đểso sánh; currenttest
  p9532.707s vẫn chưađạttrial10s. WrongIDs/metadataquotes/paraphrase/truncation vẫnchặn,
  không nới validator hoặc đếm statusanswered/documenthit làm answeraccuracy.

## Phiên tiếp theo

1. T5.4: hoàn thiệnREADMEportfolio/architecturediagram/screenshots/GIFdemo/reproducebenchmarks/
   failuretrade-offs/video3–5phút/interviewdecisions,CVbulletchỉsốthật; M5chưa nghiệmthu.
2. Nếu user ưu tiênquality: dùng posttestbacklog làm analysis, phát triển evidence/devversion
   và testset độc lập mới. T01–T40 đãexposed, không replay/improve rồi claimprospectiveheldout.
3. Giữimmutable100/legacy30/19/corpus15/307/source/hash/filter/latest vàfailures. Releasefreeze
   verify exactsource/config; khôngauto-rebind, không overwrite testledger/predictions.
4. T4.4reports `docs/error-analysis-review.md`; `t4_4_*`manualCSVs/IDmetrics/21failures/
   freeze/ledger/integrity. Raw `evals/results/t4-4-*`, `data/processed/t4-4-*` ignored.
5. Chốt mỗi bước bằngdocs/kiểmchứng/commit. Sourcecheckpoint09October2026;
   45excludedpages/legal_statusunknown không được thổi thành verifiedfull/currentlegal.

## T4.4 — Final release/evidence handoff

- `configs/rag/final.json` / `rag-obligation-support-v3`, behaviourv2/promptv4,
  freshnessclause-scopedv2; samepins/top4/context6/input2304/output64/retry1/lowmemory.
- Threefixgroups obligations/providerselection,calendarunits,study_progressstrict0–40;
  absentNoneexcluded khôngđổi frozen100serialization. User phảiexplicitsemester, khôngsuycohort.
- Pilot14 all13answerscorrect; iteration1full60D06falseabstention retained. Signaturedependency
  promptfix rồi exactfinal60:47/47/65of65/60of60,8/8reject,fields12/12,p9515.824s.
- Freeze07:10:12.468742UTC, claim07:11:38.800029UTC; full40onepass finished07:26:28UTC,
  source/config pre/postchecks pass. Confige1933332.../sourceca2b3803.../datasetd577... unchanged.
  `t4_4_release_freeze.json` binddevpredictions533155f2.../review92a76a83...;
  testpredictions1e604487.../finalreview713090c7..., completeassistantmanualreview40.
  T07P4partialprioritysupport đượccredit ởfinalrubriccheck; originalreview3a5cbc90... vàcorrectionlog giữ.
- Test:19/28answerscorrect/32of43facts/29of108cites/reject0of7/fields0of20.21qualityfailures
  retained, noheldout-basedinferencechanges. Testaccuracy không lấy47/47tuneddevthaythế.
-370pytest/13Node/Ruff180/lock70/pipcheck; regressionGPA8/fixed12/adversarial24,
 65browserassertions pass; allautomaticspan/source/filter/latest audits0.
- Dataset100/72spans/49chunks/legacy30/19/corpus15/307/0unfinished nguyênvẹn.
  **Globalheldoutinference40**, read-onlyvalidatorreports0 chỉ làoperation-local count.
- `python scripts/check_release.py --config configs/rag/final.json --freeze data/manifests/t4_4_release_freeze.json`
  verifyexactfrozenbytes/corpus khônggọiModels. Frozenrawdata cầnlocalcache đểre-score;
  historicalrunreproduce cần đúng sourceversion cùngconfig, không chỉ configJSON.

## T5.2 — Observability handoff

- `core/tracing.py`/`api/middleware.py`: UUID/header/bodyrequestID/contextvars,
  tracev1/64spans/100rows/16passages/strings160/omittedcounts. INFOJSONeventregularag.trace.
- service/pipeline record scopesfieldnames/queue/retrieve/CEactualbefore-after/order/context/
  registry/hash/dependency/selected/resolved/citedIDs,actualusage/0APIcost/unknownlocalcompute.
  Noquestion/source/answer/prompt/vector/rawmodel/headers/DSN/exceptionmessage logged.
- `REGULARAG_PIPELINE_TRACING_ENABLED=false` tắtcollect/emission nhưngIDvẫntrảheader/body.
  Async→syncpropagation/concurrentrequest isolation, type-onlyerrors422/503/500 vàsinkfailure
  khôngđổianswer đãkiểm;traceon/offsameoutputs, noextraretrieval/Modelcalls.
- `scripts/inspect_trace.py --log <json-lines-log> --request-id <UUID> [--output <new-json>]`
  tìm đúng1trace/schema, outputmetadata/timeline/chunks/ranks/registry/selectedIDs/largestleaf.
  Parentdurationsincludechildren khôngadditive;contextprepareincludesmodel/tokenizerload.
- `check_observability.py`7passedcases tạiignoreddata/processed/t5-2-observability/
  eventslines/response/percaseinspecteddumps;public`t5_2_observability_checks.json`.
  O02B07realextraP3familyrule:requiredsupportempty/generatorP1P3/minimizerretains;
  O05declaredselectorfixtureonlyP2→resolveincomplete dùcorrectsourcecontext, không Qwenfailureclaim.
- LiveAPI8000newrequestID9e9fd74e...header=body=log;30spans/1393effect+signature/usage592/11;
  `t5_2_live_trace_check.json`. Coldembed~30.8–30.9s,e2e~52sdiagnostic khôngbenchmarkcausal.
-383pytest/13Node/Ruff186/lock70/pipcheck,unchangedfrozen100/corpus15/307/sourceguards đạt;
  0newtestinference/global40. Noadditionaldependencies;Langfuseoptionaldeferred,
  traceDB/rotation/centralstorage/operatorretention chưaimplemented.
- M4measurements/freeze giữ original221ee6fsourcehashca2...; newinstrumentedsourcehash khác.
  Oldreleaseexactchecker đúng khi dùngmeasuredversion, khôngupdatefreeze/ledger/reviews/metrics
  từnewcode hoặc chạy lạiT40đểtuning. `docs/observability-review.md` cófullacceptance/evidence.

## T5.3 — Containers / CI / deployment completed

- RuntimeDockerAPI/UI ởhttp://127.0.0.1:8001,dbhealthy/pinnedPG17/sameoriginalvolume;
  namedHFcache đãexplicitbootstrap4pins vàcheckoffline4/4ready.
- `Dockerfile`Python3.12.15/base+frontenddigests/lock70/builderwheel/libgomp/UID10001;
  `.dockerignore`exclude.env/raw/OCR/processed/models/traces. Composeprofilesapp/tools,
  readonlyruntime/tmpfs/singleworker/sourceguard. README cómanualprerequisites/setupsteps rõ.
- Freshproofprojectregularag-t5-3-setup ports55432/8002:6applied→6skip;operatorapprovedinputs
  →15/307index→15unchanged/publicationaudits307FTS/19goldunchanged;31HTTPassertions/6knowncases.
- Defaultdeployment8001 same31checks/source-span-view hashes/correlation andold-onlyguard pass;
  raw `data/processed/t5-3-*`ignored;native8000 không containerendpoint.
-387pytestCI-equivalentmocks/downloadguard/emptyHFcache,13Node/Ruff195/lock70/pipcheck đạt;
 2jobsGHA definitionquality(fullPGtests) vàcontainer-startup(noModelweights),actionsSHA-pinned.
- User explicitcho phép **commit/push lênorigin/master saulocalchecks đểchạy/theo dõiCI**.
  Repooriginvkhanh2802/RAGAskingRUlepublic,8previouslocalcommitsaheadorigin khi bắt đầu.
  ghportabletooling ởapprovedTemp, dùngexistingcachedGitcredential transient khôngprint/storetoken;
  GH_ADMINpermission/workflowscope ready. Không updategitconfig/forcepush.
- HostedCI **success2/2jobs** run38347533640testedda840c721...,
  https://github.com/vkhanh2802/RAGAskingRUle/actions/runs/38347533640,
 13October04:39:55–04:42:02UTC; quality387passed/37.30s/13UI/Ruff/lock70/migrations6,
  containerbuild/migrate/APIUIhealth/model-freeguards/cleanup pass. RawGitHublogs via gh.
  `t5_3_hosted_ci_validation.json` bindactualfeaturecommit,closuredocsnewcommit riêng.
- `docs/container-deployment-review.md`/t5_3metadatarecords giữfailedMIMEhelperheadercase
  vàsessionrestartconnectionrefused; newcheckedrunpaths giữfailures, không đổi gold.
- Originaldataset100/M4freeze/measurements giữ nguyên;0newtestinference. ScopeT5.3deployment
  localDockerDesktop,publicpaidconditionalrate-limitkhôngapplicable. NextT5.4/M5pending.
- Ownedfreshproofcontainers/network/DBvolume cleanedup;originaldatabase/cache anddeploy8001 giữ.
  NativeT5.2PIDmetadata làhistory khônggiếtblindly. CIprivatecredentials dùngtransienthelper
  ởTemp, khôngstoreGHtokentrongrepo/logs; ghportablekhông làappdependency.
