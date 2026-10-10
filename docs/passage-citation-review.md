# T3.2 — Structured passage selection và citation validation

Hoàn tất **2026-10-09** trên corpus15/307. Mặc định mới:
`rag-bound-passages-v3` / `verified_passages` / `bound-passage-selection-v3`.
T3.3 clarification và T3.4 behavioral acceptance còn tiếp theo; chưa nghiệm thu M3.

## Thay đổi chính

- LLM trả duy nhất `{"passage_ids":[...]}`, tối đa4 mã không trùng, hoặc[] khi
  thiếu evidence. Không sinh quote, source ID, URL, tiêu đề hay trang.
- Mã P1… chỉ có nghĩa trong registry của request hiện tại. Llama.cpp dùng JSON
  grammar có enum các mã đã cấp; strict parser từ chối unknown ID, duplicate,
  wrong types, extra fields và output ngoài JSON. Transformers dùng strict parser.
- Backend resolve passage→chunk→source, kiểm char_start/char_end theo Unicode,
  đoạn nguyên văn và SHA-256; dựng answer/citation từ approved text. P1 không
  tự đồng nghĩa S1. Fake quote/source/page của model không tham gia answer.
- Numeric clauses/bullets được giữ thành atomic blocks; không cắt giữa điều kiện
  hay ngoại lệ. Với câu hỏi conditions tổng quát, giữ whole condition article.
  Table row/cohort/design-duration chọn literal reviewed row. Date-from-signature
  phải kèm literal signing date từ cùng document, không suy từ ISO metadata.
- Support facets kiểm các phần được hỏi: unit/limit, deadline/grade, date type,
  programme/course, weighting/rounding, midterm/suspension… Chỉ là các lexical
  checks khai báo, chưa là general entailment hoặc confidence calibrated.
- Ưu tiên semantic chunk order đã đo ởT3.1, chọn complete blocks hoặc minimal
  facet cover, reserve mandatory amendment passages. Giữ publication/hash/model/
  metadata/freshness guards và kiểm lại companion sau prompt budgeting.
- Output64 tokens, input2304 thay cho384/4096 ởquote mode; tối đa8 candidate
  passages từ6 chunks. Không ép đủ6 sources nếu chỉ1–2 đoạn trả lời đúng.
- Low-memory mode giải phóng E5/reranker sau retrieval, đóng GGUF sau request
  trong finally kể cả lỗi. Không giữ ba model đồng thời qua các request.
- Retry tối đa1 lần cho structural output failure ởLlama; không retry épempty
  selection thành answer hoặc nới support checks. Lưu attempts/raw attempts trong
  ignored diagnostics. API thêm evidence_passages và timing/attempt fields.

Legacy quote validator800chars vẫn giữ cho `verified_quotes`. Bound passages có
thể dài hơn800 vì backend lấy toàn atomic block theo offsets/hash, model không
chép nội dung. So sánh/reproduction legacy bằng `configs/rag/quotes-v9.json`.

`sources.excerpt` ởpolicy mới là approved source chunk để mở đối chiếu;
`evidence_passages` là **các đoạn thực sự đưa vào prompt**, có offsets/hash/cited
và required_passage_ids. URL/PDF page range/article vẫn từ database, không gán lại
page theo phỏng đoán về nội dung; page range của chunk có thể coarse.

## Kết quả bộ12 failure/regression cases

ASGI TestClient, PostgreSQL/E5/reranker/Qwen thật, cùng câu hỏi/filters củaT3.1.

| Chỉ số | T3.1 quotes-v9 | T3.2 acceptance batch |
|---|---:|---:|
| HTTP200 |12/12|12/12|
| Generation calls |11|11|
| Answered |1|11|
| Primary answer source-supported, assistant review |1/12|11/12|
| Expected stale-filter abstention |1|1|
| End-to-end p50 |103,908s|**13,572s**|
| End-to-end p95 |152,603s|25,958s|

Đây là development/debug set, có tuning sau khi xem failures; không phải held-out
answer accuracy. Timing là mixed cold/warm toàn request, gồm model load/release,
không so trực tiếp với warm retrieval stage4,65s. Cold firstcase35,5s; separate
cold regression processes34–39s vẫn chậm. Lợi ích đến từ ID-only output, shorter
complete context và resource lifetime, không quy hết cho một thành phần.

- F01/F02: dùng1393 cap12/minimum70, không các old790 clauses10/50.
- F03: monthdeadline/gradeM nguyên văn; acceptance còn extra gradeI không liên
  quan, đã sửa primary-document pruning và rerun `deadline-regression` chỉ1393.
- F04/M201:513 online/freeelectives/max3/15hours/top100/rankingage3years,
  nonduplication/learningoutcomes và các conditions chung đều giữ.
- F05:790-only filter loại1393, abstain trướcgeneration; không bỏfreshnessguard.
- F06:412 tại01December2025, khôngfuture513; wholearticle3 giữC-or5 threshold,
  completionwithin5years, equivalence vàinstitutional review conditions.
- M204: correct2018/4-year row/HK1NH2022-2023/PDF2; sourceID dobackend resolve.
- M211: literal01/9/2024 vànonretroactivity, không14Augustsignature/ISOmetadataquote.
- M212:30paperdegree/5digital; source894 **Điều9/PDF8/chunk0017**, khôngĐiều15.
- D15/D30: bloodrelation/CBHD condition và JAN02/JLPTN5/NATN5/cap16 intact;
  không model paraphrase hoặc thêm từ vào source.

Acceptance audits:0 span-binding, citation, source provenance, excerpt, filter,
latest-anchor, old-affected-clause hoặc missing-companion violations. Existing
quote audit không đủ cho ID-only policy; dùng thêm `audit_passage_samples.py`.

Artifacts: `t3_2_acceptance_api.csv`, `t3_2_acceptance_audit.json`,
`t3_2_freshness_audit.json`, `t3_2_api_manual_review.csv`; fulltext/prompts/raw
model outputs ởignored `data/processed/t3-2-acceptance-api/` vàregression folders.

## Mở rộng development30 và các lỗi tìm được

`t3_2_development_final.csv` ghi29answered/1abstain, p50~13,79s/p95~20,65s.
Identity/citation audit pass; **statusanswered không được tự tính semantic pass**.
Manual comparison với frozen references tìm thấy:

- D09 falseabstention vì nguồn ghiSV: thêm unit alias và rerun có1–2SV/outline.
- D13 wrongtopic grade0 từarchive thay midterm: thêm requested-topic facets;
  rerun đúngĐiều7 clause1/c/grade0. Giữ output sai trước sửa.
- D18 weighting bị nhầm sang reviewer identity: chỉ áp relation facet khi câu
  hỏi thực sự yêu cầu identity; finalrun đúng2/1weights vàrounding0,1.
- D26 códate/certificateage thay schedule: thêm session/month facets, rerun
  đúng4đợt vàtháng2/5/8/11; còn adjacent certificate condition extra.
- D28/D29 overinclusive otherprogram rules: namedprogramme facet, rerun chỉ
  đúngCTC/CTTN hoặcCTA; atomic block còn các mốc của cùngprogramme để giữconditions.
- F06 initial clause-only selection thiếugrading/age: whole condition article,
  acceptance rerun đủrequirements. F03 unrelated gradeI excerpt bỏ ởtargeted rerun.

`t3_2_development_manual_review.csv` phân biệt run được review/corrected vàextra
material. Primary reference evidence đã đối chiếu30 cases theo final+targeted
reruns; **không ghép thành một đo30-case accuracy/latency mới**. Một số generic
queries vẫn quote thêmclauses không cần thiết; precision/minimality là việcT3.3.
Gold dataset/source/content/page bindings19chunks không đổi, không rebind.

## Quality gate và reproduction

-210 tests pass:109unit/101PostgreSQL integration; unknown/tampered IDs/offsets/hash,
  duplicate output, complete conditions, signature dependency, facets, namedprogramme,
  latest binding quaDB/API và resource release khi exception.
- Ruff124files check/format pass; pipcheck/lock70 unchanged; Docker healthy.
- `t3_2_publication_snapshot.json`:15ready/307unique/307FTS/15unchanged/0unfinished,
  19gold unchanged. Migrations001–006, source corpus và embedding fingerprint giữ nguyên.

```powershell
python scripts/run_baseline_samples.py --questions data/manifests/t3_1_api_smoke_questions.csv --output-dir data/processed/t3-2-acceptance-api --summary data/manifests/t3_2_acceptance_api.csv --limit 12
python scripts/audit_passage_samples.py --input-dir data/processed/t3-2-acceptance-api --summary data/manifests/t3_2_acceptance_audit.json
python scripts/audit_reranker_samples.py --results data/processed/t3-2-acceptance-api/results.jsonl --manual data/manifests/t3_2_api_manual_review.csv --output data/manifests/t3_2_freshness_audit.json
python scripts/check_corpus_publication.py --output data/manifests/t3_2_publication_snapshot.json
```

Dùngoutputpath riêng để giữmeasuredruns. Sampler cũng nhận development_questions.csv
vàderive expected document numbers từboundevidence IDs; không thayreference set.
RestartAPI để loadconfig mới. GiữUTF-8/ragschool/modelcache/offline theo development.md.
Latest vẫn verified corpus/snapshot09October2026, không livewebsite/currentlegalproof.
T3.3: clarification khi thiếucohort/program/date, precision trên vaguequeries và
falseassumptions; T3.4 ít nhất20behaviorcases.45excludedpages/832omittedregions còn ngoài scope.
