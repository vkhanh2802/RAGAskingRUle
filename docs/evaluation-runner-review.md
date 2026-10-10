# T4.2 — Evaluation runner và development baseline

Hoàn tất 2026-10-10. Evaluator `source-bound-evaluation-v1`;
run `evals/results/t4-2-development-clause-v2/` với **60development**,
47expectedanswered/8insufficient/5clarification. 40held-out chưa chạy inference.

## Runner và tính tái lập

```powershell
python scripts/run_evaluation.py
```

Một lệnh đọc frozen dataset, kiểm source/corpus/quality/model/exposure hashes trước
và sau run, rồi tạo config.json/predictions.jsonl/retrieval_metrics.json/
answer_metrics.json/operational_metrics.json/summary.md. Default60development;
`--split test` explicit dành sau khi chốt cấu hình. Không overwrite run directory;
predictions flush từngrequest, technical errors giữfailure.json.

Gold/reference/facts không gửi model. RAG nhận question/filters/scope gốc. Observer
ghi rankedpool thực để Recall@10 mà không thêm lượt inference hoặc thay answer
top8/context6/input2304/output64. Native grammar/retry/filter/latest/hash guards giữ
nguyên. Usage provider/actual generated IDs đếm input/output tokens, cộng cả retries;
missing usage lànull, abstention không generation là0.

Config runtime pipeline `rag-clause-scoped-v2`, hybrid/RRF/CE20, same E5/Qwen/prompt
pins; configSHA `f6e9a4aebb98a9a28ff25bbc2f646a52bcafe858c08fc90ada67fa688364efeb`.
Run từ basecommit01ecdbe với working tree T4.2; exact runtime source fingerprint
`559fde0a5e30e231ff40e7b8913a9d52c4bfd2db44a75369a7bd652e95d5020f` được lưu để
không coi basecommit đã chứa code evaluator. PredictionsSHA
`907d62d9c8d60bc8898eb126448849b3507df62d9bbc9f6d28e159c96b6577a6`.

Windows11/i5-12450HX,12logicalCPU, Python3.12.15, CPU E5/CE2threads/GGUF4threads,
concurrency1; existing local model cache/offline. No warmup, first process request
cold, subsequent OS/HF caches warm; low-memory per-request release/reload.
RAM~11,8GB là inventory T1; optional RAM reading trong run không có package nênnull.
Phần cứng/conditions không phải controlled multicondition latency comparison.

## Rubric và mẫu số

- Retrieval: macro fraction of unique **supportchunks** mỗi expectedanswered query;
  blocked evidence không usable, contrast/abstention/context-only không là positive
  gold. MRR dùng first relevant rank≤10; complete-recall ghi riêng tử/mẫu.
- Không có graded relevance labels: **nDCG@10 not applicable**, không invent labels.
- Automatic source/offset/hash/answer rendering/caller-filter checks. Located gold-span
  coverage là diagnostic proxy, không tự chấm semantic correctness.
- Assistant đọc **tất cả60 actual answers** cùng requiredfacts/actors/conditions/
  exceptions và goldlocators. CoveredfactIDs, faithful/relevant citedPIDs và forbidden
  claims được ghi riêng; toàn review bind predictionsSHA và responseSHA. Chưa có
  independent human reviewer/LLM-as-judge.
- Correctness trên47answerable: actualanswered, đầy đủ requiredfacts, quote/source
  fidelity, faithful claims và không forbiddenclaims. Extra unrelated quote blocks
  hạ task-support citationprecision, dù primary facts có thể vẫn đủ.
- Claimunit là **atomic quoted block** từbackend, không arbitrary sentence. Faithfulness
  ở đây là claim trong block được context nguồn hỗ trợ; không phải general entailment
  certification. Citation support thêm manual relevance với câu hỏi/phạm vi.
- Citation coverage: supported/cited blocks trên mọi answerblocks; free prose ngoài
  registry là unsupported unit. Trong run này mọi block có một citation nên precision
  vàcoverage cùng mẫu71; không đồng nhất với requiredfact coverage.
- Pending manualmetrics lànull vớiunknown count. Re-score không chạy model và không
  thay predictions; thay prediction/gold/config hoặc trộn review bị reject.

## Kết quả thật

| Metric | Kết quả |
|---|---:|
| Macro Recall@5 / Recall@10 |0.98936 /1.00000 trên47answerable |
| Micro support recall@5 /@10 |52/53 /53/53 |
| Complete support@5 /@10 |46/47 /47/47 |
| MRR@10 |0.96454 |
| Status đúng |59/60 |
| Đúng và đủ requiredfacts |**41/47 (87,23%)** |
| Requiredfact recall |57/65 (87,69%) |
| Source-faithful quoted blocks |71/71 |
| Task-support citationprecision /coverage |**52/71 (73,24%)** |
| Citation/rendering fidelity; callerfilterpreservation |60/60;60/60 |
| Từ chối đúng / từ chối nhầm |8/8 /1/47 |
| Clarification status / requiredfield recall |5/5 /11/12 |

46answered/9insufficient/5clarification; 46generationcalls,60HTTP200.
Status đúng không bảo đảm câu trả lời đủ ý. Manual overall success53/60 gồm
41answers đủ facts+8correctabstentions+4clarifications đầy đủ; D51 còn thiếu1field.

| Category | n | Recall@5 | MRR@10 | Correctness hoặc hành vi | Citation task-support |
|---|---:|---:|---:|---|---|
| single_clause |21 |1.0000 |1.0000 |21/21 |21/32 |
| multi_clause |12 |0.9583 |0.9583 |**7/12** |18/23 |
| temporal_scope |9 |1.0000 |0.9444 |8/9 |8/8 |
| adversarial |5 |1.0000 |0.8667 |5/5 |5/8 |
| no_answer |8 |N/A |N/A |8/8 correctreject |N/A |
| clarification |5 |N/A |N/A |5/5status,4/5complete |N/A |

**Latency:** all60 mixed-status requests p50 **13.270s**, p95 **18.282s**. Component
timers: retrieval excludingCE p50/p95 **0.962/1.078s** (52active), CE **6.306/8.947s**
(50active), `generate` **3.862/8.374s** (46active). ActiveLLM p50/p95 **4.354/8.462s**;
generation stage including budget/load/validation **4.869/9.452s** (47active).
Stage times không cộng trực tiếp; end-to-end còn release/validation/ASGI overhead.
Both all-sample and active counts/quantiles được lưu.

Actual inputtokens **25.588**, outputtokens **479**; mean/request426.47/7.98 kể cả
không generation. Output là selectionJSON, không đếm backendquote như generatedtokens.
API cost **0VND**; local hosting/compute cost **chưa định giá**, tách khỏi API cost.

## Failures giữ lại

| Case | Review thực tế |
|---|---|
| D33 | Chỉ10đề tài; thiếu CBPB khácCBHD/family rule |
| D34 | Chỉ20ngày nhập/gửi điểm; thiếu archive handover/5năm |
| D36 | Chỉ quy tắcCBPB; thiếu học vị/co-supervisor khi mời bên ngoài |
| D37 | Chỉ4đợt/tháng; thiếu2năm certificate validity với hai mốc |
| D38 | Progress/programme blocks thay prerequisite PET02 vàM-grade;0/2facts |
| D42 | False rejection `missing_support_candidates`, historicalC/5và5năm có nguồn |
| D51 | Hỏi khóa/hệ/programme nhưng thiếu`study_progress`/mốc học kỳ chuẩn đang xét |

Extra irrelevant blocks ở D03/D08/D10/D16/D20/D27/D38/D57: tổng19/71blocks không
task-support. 14distinct cases có completeness/clarification/precision issues.
T4.2 lưu baseline này; đây là đầu vào T4.3 ablation và T4.4 error analysis, chưa sửa
heuristics/model từ các failures này. Frozen questions/facts/spans/labels giữ nguyên.

Citationprecision73,24% chưa đạt target90%; local p9518.28s cao hơn target thử10s.
Recall và correctness tốt hơn không xoá các giới hạn này; development đã exposed/tuned
không phải held-out accuracy. M4 chưa chốt benchmark/config cuối.

## Bằng chứng và kiểm chứng

- Public `data/manifests/t4_2_development_metrics.json`: config/source/run fingerprints,
  aggregate/category/ID-only percase scores; `t4_2_development_decisions.json`: review.
- Raw run/pilot2 vàactual quotes/modeltraces ởignored `evals/results/`. Pilot tạo đủ
  reports; full60run một lượt, không ghép target reruns hoặc đổi gold để đạt.
-339pytest (223unit/116schema-isolatedPostgreSQL), full97.63s; targeted20 cho runner/
  metrics/usage/re-score; Ruff163files,12Node,lock70/pipcheck đạt.
- Frozen100/60dev40test/72spans/49chunks/legacy30/19 giữ hashes;
  `t4_2_dataset_integrity.json`. Corpus15ready/307chunks/307FTS/15unchanged/0unfinished;
 103approved/40native/45excluded, `t4_2_publication_snapshot.json`.
- Reproduce/annotate/publish: `evals/README.md`, `docs/development.md`. Cùng code/config
  vẫn có thể khác tốc độ và modelselection trong cold/warm/local load; review mới cần
  bind response mới. Không re-use reviewSHA của run khác.
