# T4.4 — Error analysis, release freeze và held-out evaluation

Ngày hoàn tất: **2026-10-11**. T4.4/M4 có đủ versioned dataset/evaluator,
benchmark và error-impact evidence. **Chất lượng held-out chưa đạt mục tiêu**:
19/28 câu có đáp án đúng đủ ý, citation support29/108, đúng từ chối0/7.

## 1. Phạm vi và phương pháp

- Reference: T4.3 `hybrid_reranked_k4`, config `configs/rag/t4_3_selected.json`.
- Frozen `data/evaluation/v1`:60development/40test, cùng corpus15/307; gold/labels,
  72spans/49chunks, legacy30/19 và11exposure registries không thay đổi.
- Evaluator `source-bound-evaluation-v1`; semantic review bởi assistant, không independent
  hoặc blind human review. Model chỉ nhận query/scope và nguồn đã truy xuất, không gold.
- Facts-spancoverage là diagnostic; chấm actual answer về actors/conditions/exceptions.
  Mỗi claim/citation unit là một atomic quoted block. Extra blocks bị trừ task precision;
  complete correctness yêu cầu đủ facts và faithful citations theo rubric T4.2.
- Một lượt40 sau releasefreeze; sau đó chỉ review/re-score/read-only diagnostics/report.
  Raw source/model traces trong ignored `evals/results/`, không đưa toàn văn vào Git.

## 2. Inventory development và ba nhóm sửa

`data/manifests/t4_4_error_cases.csv`: **20 error cases/19 distinct questions**,
14issues trên selectedreference và6variant-specific issues. D16 xuất hiện ởhai variants.
Primary stages: generation5, citation7, retrieval6, abstention1, clarification1.
Parsing/OCR/chunking/reranking đã được xét nhưng chưa có bằng chứng là primary cause
trong inventory20 này; không suy thành chứng nhận các tầng đó hoàn hảo.

`t4_4_baseline_error_analysis.json` bind baselinepredictionsSHA và ghi gold ranks,
registry/cited coverage, modelselected vsfinalcited IDs; không có model call/test tuning.

### A. Contract đủ mọi nghĩa vụ và lựa chọn nguồn/đoạn

- D33/34/36/37: single lexical facet làm block thiếu ý được coi là complete hoặc minimizer
  bỏ reviewer/archive/qualification/certificatevalidity. D38 lẫn progress với prerequisite/M.
- Bổ sung lexical obligations cho hai actors, archive/grading, prerequisite/M/credits,
  certificate date interval, extension permissions và fee formula; compact PET02/M/SV.
- Guardedpool reserve nguồn bao phủ obligations theo query trước effective top-k.
  Không thêm nguồn ngoài samepool/callerfilters, không bypass blockedprimary/hash/latest/view.
- Payload có `supports`/`required_support`; model chọn đủ phần, backend giữ fullconditions.
  Đây là lexical contracts, chưa general entailment. Thứ tự v3 là CE + obligation reservation;
  Recall/MRR mới đo thứ tự này, không phải pure-CE-only gain.

### B. Calendar/quantitative qualifiers

- D42: `ngay01-12-2025` bị hiểu count-of-days, gây falseabstention.
- Tách explicitcalendar khỏi unitintent, thêm grade/age support. Historical412 vẫn dùng
  trước513; không đổi date/source metadata/gold hoặc nới threshold0.55.

### C. Study progress trong scope/clarification

- D51 cần khóa/hệ/programme **và mốc học kỳ**, trước đó thiếu axis cuối.
- `scope.study_progress`: strictinteger0–40, explicit elapsedmainsemesters; UI numberinput
  có label/hint. Đọc số/words explicit trong query, không suy từcohort/issuedyear.
- AbsentNone không serialize nên frozen100 canonicalSHA giữ nguyên. Source lookup không
  tự bị biến thành câu hỏi áp dụng cá nhân.

Các5keyword-only retrieval issues vẫn được lưu; selectedhybrid+CE không biến toàn bộ
keyword-only thành corrected benchmark. Không claim từng component improvement độc lập.

## 3. Lượt development và regression

| Lượt | Câu | Correct answerable | Facts | Task-support citations | Ghi nhận |
|---|---:|---:|---:|---:|---|
| T4.3 selectedCEk4 |60|41/47|57/65|52/71|Reference |
| T4.4 pilot |14|13/13|21/21|20/20|13answerable +D51; không đại diện full60 |
| T4.4 iteration1 |60|46/47|64/65|58/58|D06 regression giữ nguyên |
| T4.4 final |60|**47/47**|**65/65**|**60/60**|Complete manualreview60 |

Iteration1 D06 có đủ effectivity+signature nhưng model chỉ chọn ngày kýP2; backend
`incomplete_passage_support`. Expose `required_passage_ids`/bound `signature_date` support
và chỉ dẫn cần cả rule+literaldate; standalone date vẫn không được coi là effective rule.
Targeted actualmodel rerun có đủ nguồn, rồi rerun **toàn60** trên exactfinalcode.
Không ghép targeted reruns thành một full-run result.

So reference, six answerability wins D33/34/36/37/38/42 và clarificationD51 được hoàn thiện;
không có complete-correctness loss. Multi-clause7/12→12/12; requiredfields11/12→12/12;
19extra/unsupported cited blocks trong reference→0 trên finaldevelopment, ở mức blockunit.
Whole atomic blocks vẫn có câu phụ/điều kiện, không claim precision từng sentence.

Finaldevelopment: Recall5/10=1, MRR10=1, micro53/53supportchunks,8/8correctreject,
falseabstention0/47, status60/60, filter/citationfidelity60/60.
E2ep50/p95 **12.351/15.824s**,47generation, input28862/output443actualtokens.
Referencep50/p95 **12.441/17.820s**; one-pass mixedcold/warm/hostload khác nhau,
không causal speedup/significance claim.

Regression actualmodels với finalconfig:

- GPA8:6primarysupported/2correctabstain; unchanged79014.1(a)/cap30 giữ đúng,
  affected hè/classsize vẫn cần1393. G08 có extra ĐTBHK block ngoài hai định nghĩa.
- Fixed12:11primarysupported/1correctstale-filterabstention. OldF01cap10note không làmgold.
- Adversarial24:11supported/13abstain;24/24predeclared contracts; B07 có extra familyrule.
- Source/span/citation/filter/latest audits0errors; không dùng contractpass thay taskprecision.
-370pytest (253unit/117schema-isolatedDB),13NodeUIcontracts; Ruffcheck/format,
  pipcheck vàlock70 đạt. ExistingStarlette/httpx deprecationwarning còn ghi nhận.
- BrowserQA27fixture/18realpreset/22realGPA assertions,10knownrealrequests; AxeA/AA
  scans0violations,375/812landscape/768responsive/reducedmotion/no uncaught errors.
  ExplicitCTA/progress3 reply giữ query và cap16/IEL05; presets clear staleprogress.

## 4. Freeze trước test

Finalconfig `configs/rag/final.json`: `rag-obligation-support-v3`, hybrid/top4/candidate20,
CEon, `guarded-obligations-v2`, `bound-obligation-selection-v4`, freshnessv2.
Modelpins/embeddingfingerprint/context6/input2304/output64/retry1/low-memory giữ nguyên.
`t4_4_development.json` có cùng config content; baselineJSONv2 được giữ làm reference.
Để tái tạo measurement lịch sử cần đúng source fingerprint/commit cùngconfig, không chỉconfig.

`data/manifests/t4_4_release_freeze.json` tạo **07:10:12.468742UTC** trước testclaim
**07:11:38.800029UTC**; 0held-outrequests trước freeze. Ghi exactrevieweddev60 vàquality.

| Binding | SHA-256 |
|---|---|
| Config |`e19333322b1b25e824bf57c779fbedd6a6136dcc83315f913486df4476261463`|
| Inference source |`ca2b38034cc2c2860f0723a6b873d34a8015e8c7a3b7a22162bd3814128e3f74`|
| Dataset100 |`d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c`|
| Held-out40 |`d6a9f0c97925c5db41f0257ce83f5237f1a32d20569d043888a9fca5803fb457`|
| Corpus |`b213a260c7b8be3bed5e534575002263d9d878b4c09e67c670c3246f6b5f9776`|
| Devpredictions |`533155f24afa61c2b5527fca4a8c3156deac7bfb0d840853d8773ae0f7cab4c3`|
| Devreview |`92a76a839cf63cafd0956ccd8b05aeedb73ebecb7eb16c09b554df2e3cecc862`|
| Testpredictions |`1e6044871107ba0a2fc56d8561808bd288934379ac0071b07a09eedfcac8b0ac`|
| Finaltestreview |`713090c75ed60095aad10427362c4422812bb0321117517ab9207c184693f82c`|

Sourcefingerprint bao gồm mọi `src/regularag/**/*.py` và `scripts/run_evaluation.py`
(exactbytes/lineendings). Runbasecommit `d18cbe4` +recordeddirtyT4.4worktree, exactcode hash
giữ trước/sau test; stepcommit sau khi chốt reports. Offline review/export scripts vàdocs
không thuộc inferencefingerprint. One-runledger `t4_4_release_freeze-held-out-run.json`
ngăn replay/subset; errorpaths không overwrite. Không sửa inferencecode/config saufreeze.

## 5. Held-out40 — kết quả thực tế

`evals/results/t4-4-held-out`,07:11–07:26UTC:40HTTP200,37answered/2insufficient/1clarify;
postflightintegrity vàreleasechecks đạt. **Expected28answered/7insufficient/5clarify**.
Không infer chất lượng từ HTTP/status, corpus hit hoặc exactquotes.

| Metric | Developmentfinal | Held-out40 |
|---|---:|---:|
| Correct/đủý trên answerable |47/47 (100%)|**19/28 (67.86%)**|
| Requiredfacts |65/65|**32/43 (74.42%)**|
| Taskcitation supportprecision/coverage |60/60|**29/108 (26.85%)**|
| Source-bound faithfulness |60/60|108/108|
| Source/render citationfidelity |60/60|40/40|
| Callerfilter preservation |60/60|40/40|
| MacroRecall5/10 |1/1|1/1 (micro33/33)|
| MRR10 |1|0.9375|
| Correctreject |8/8|**0/7**|
| Falsereject |0/47|2/28 (7.14%)|
| Falseclarification |0/47|0/28|
| Clarificationstatus |5/5|1/5|
| Requiredclarificationaxes |12/12|**0/20**|
| Statusmatch |60/60|27/40|
| E2ep50/p95 |12.351/15.824s|**21.552/32.707s**|
| Actualinput/outputtokens |28862/443|44519/576|

All40 được manualreview, không unknown/null semantics. Combinedcorrectcasecount19/40;
không trộn tuneddevelopment vào held-outaccuracy. Claimunit làblock nên108/108faithful
vẫn có79blocks không hỗ trợ requestedtask. nDCG N/A do binarysupportlabels.
APIcost **0VND** total/perrequest; existinglocalcompute/electricity chưa định giá.
CPUserial1, Windows11/i5-12450HX/12logicalCPU,Python3.12.15, no warmup/per-requestreload;
modelcache offline. RuntimeRAMtotalnull do optionalpsutil absent, không thêmdependency.

Finalrubric consistency check creditT07P4: đoạn mô tả thứ tựưu tiên/số1cao nhất cũng
hỗ trợ phầnpriority củaF1 dù P1 đãtrả đủ. Redundancy không tự làirrelevance; partial
requestedfact contribution được credit theo cùngcitationrubric. Vì vậy score-only
29/108 thayinitial28/108; correctness/facts/status/predictions vàcode/config/gold không đổi.
`t4_4_held_out_review_correction.json` ghiresponse/prediction/initialreviewSHA và lýdo;
initialbound `csv_reviews.json` giữlocal, finalbound `csv_reviews_final.json`/reviewSHA713090...
được publish. Không có extraModelcall hoặc điều chỉnh testlabels.

### Các lỗi được giữ lại

`t4_4_held_out_failures.csv`:21complete-quality failures, chỉ post-test analysis:

- Partial/missing linked obligations **T10/13/14/15/22**: maxstudytime/seconddegree,
  pages, reissue-vs-correction, databaseprocedure, correctionmethod.
- Falseabstention **T16/20** trướcLLM: literal `conditions=dieu kien` không khớp rule
  council/quorum; `Theo112 SV` bịcountregex coi112là sốSV. Gold vẫn trong ranked5.
- Wrongtopic **T36/38**: appendices/header hoặc databasebookrecovery thay dualdegreecap/
  one-timeissuererror exceptions, dù supportgold có trong ranked5.
- **T24–30**,7/7unanswerable: futurefee/scholarship/dorm/exam/studentrecord/diagram/
  cutoff unsupported vẫn emitquotes. Sourcefidelity không đủ làm answerabilitygate.
- **T31–35**,5/5clarification chưa đúng: missing personaleligibility/correction/admission/
  disciplinary/deferral axes. T35 đúngstatus nhưng hỏi audience thay ground/documents/date.
- Các câu đạtfullfacts cũng còn extraquotedblocks khi obligations không nhận diện,
  ví dụT01/03/05/09/19/23/39. Genericlexicalfacets/minimizer chưa tổng quát ngoàidev.

Không có sửa/tuning dựa vào các testresults. Test40 giờ đã exposed; cải thiện tiếp phải
có development/version/evidence mới và một testset độc lập mới nếu muốn đo prospective
held-out. Giữ nguyên gold/oldfailures/freeze để đối chiếu.

## 6. Nghiệm thu và quyết định snapshot

| Tiêu chí M4 | Kết quả/bằng chứng |
|---|---|
| Dataset/evaluator version vàguards |Đạt; frozen100 +evalv1,read-only source/hash checks |
| Benchmark tái chạy/re-score được |Đạt; commands/config/pins/source/commit/timing/usage/manualSHA |
|20failure inventory,2–3fixgroups/impact |Đạt;20cases/3groups,ref→pilot→iteration1→finaldev |
| Release trước40test, khôngtesttuning |Đạt; timestamp/hash/one-runledger/pre-postchecks |
| Lỗi/limits vàquyếtđịnh báo cáo |Đạt;21testfailures,publicID-onlymetrics/fulltracesignored |

Chỉ tiêu quality held-out: Recall5/citationIDfidelity/falsereject đạt; correctness≥80%,
taskcitationprecision≥90%, correctreject≥85%, p95trial<10s **chưa đạt**.
Quyết định giữv3 làm **localdemo/evaluation snapshot**, chưa đạt chất lượng hỏi đáp tổng quát.
Không claim productionready, generalentailment/injectiondefense hoặc pháp lýcurrent.
Nguồn vẫn partial45excludedpages/omittedregions; ready chỉ technicalpublication.

## 7. Tái lập và artifacts

Trong Conda `ragschool`, Docker/cache/rawPDFs/approvedartifacts/DB đãsetup:

```powershell
python scripts/run_evaluation.py --config configs/rag/final.json --run-dir evals/results/<new-development-run>
python scripts/bind_evaluation_review.py --run-dir evals/results/<run> --review-csv <new-actual-review.csv> --output evals/results/<run>/csv_reviews.json
python scripts/run_evaluation.py --config configs/rag/final.json --run-dir evals/results/<run> --score-only --review evals/results/<run>/csv_reviews.json
python scripts/publish_evaluation_summary.py --run-dir evals/results/<run> --output <ID-only-metrics.json>
python scripts/check_release.py --config configs/rag/final.json --freeze data/manifests/t4_4_release_freeze.json
```

ReviewerCSV có explicitfactIDs/faithful/relevantPIDs/forbiddenclaims/behaviour/note;
helper chỉbindresponses, không tự fillgold labels. Run mới phải reviewactualoutputs mới.
Để re-score recordedtest dùng `--run-dir evals/results/t4-4-held-out --score-only`, không
gọi thêmmodel. Lệnh40đã dùng, **ledger hiện claimed**:

```powershell
python scripts/freeze_release.py --config configs/rag/final.json --development-run evals/results/t4-4-development-final --output data/manifests/t4_4_release_freeze.json
python scripts/run_evaluation.py --config configs/rag/final.json --split test --release-freeze data/manifests/t4_4_release_freeze.json --run-dir evals/results/t4-4-held-out
```

Publicevidence: `data/manifests/t4_4_{error_cases.csv,baseline_error_analysis.json,
iteration1_metrics.json,development_metrics.json,held_out_metrics.json,held_out_failures.csv}`;
manualCSVs/reviews,releasefreeze/ledger,regressionaudits,datasetintegrity/publicationsnapshot.
Raw `evals/results/t4-4-*`, `data/processed/t4-4-*` ignored. UI/server hướng dẫn tại
`docs/demo-guide.md`. Bước kế tiếp trongplan: T5.2observability; qualitybacklog cần evidence
mới, không đánh bóng frozen40results.
