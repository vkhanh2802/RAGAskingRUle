# T5.4 / M5 — portfolio, video và interview review

## Deliverables và phạm vi

README gồm problem/scope, ảnh/video demo thật, actual architecture/source coverage,
hardware/config/runbook, methodology/benchmark, failures và quality-latency-cost
trade-offs. [Architecture](architecture.md) thay initial Streamlit proposal bằng
native FastAPI UI, actual source-bound retrieval/selector/citations/tracing/container.

[Video](assets/regularag-demo.mp4) là continuous live browser footage có chú thích,
không audio/voice-over, ba known development queries và static slides; **không
new held-out evaluation**. [Interview](interview.md) có ba decisions/ba real fixes/
một remaining failure, measured CV bullets và rehearsal budgets5min/18min.
Đây chưa là independent human presentation assessment.

## Media và actual demo

- Live Docker API/UI8001, finalv3/top4/hybrid/catalog15;
  MS Edge155.0.4283.45, viewport1440×900.
- Ba requests: DEV-SUMMER cap12/no smallclasses; D31 min70 + summer12/full conditions
  với caller1393filter; D46 insufficient/no_matching_evidence/no citation.
- **46 recording checks:** six automated WCAG A/AA scans, range/SHA/backend render,
  header=bodyUUID, full chunk/provenance panels đóng, no response interception,
  tám bound input files giữ hash.
- MP4 H.264/yuv420p/15fps/**240.6s**, 1.801.612bytes, faststart.
  UI elapsed28.016/15.050/1.818s chỉ diagnostic, không gán cho historical M4 benchmark.
- **21 offline browser checks:** keyboard arrows/counters, năm slide A/AA scans,
  desktop/mobile375px không horizontal overflow; **actual HTML5 MP4 playback**
  xác nhận duration/dimensions/no decode error, không HTTP/model calls.
- Public images/video chỉ có curated short spans đã tracked (`class_size`177chars/
  `summer`250chars), source metadata/native UI. Không có PDF/full OCR/model traces/
  exportJSON/secrets. Answer image là actual frame114s cho thấy đủ hai quote;
  source-focused screenshot gốc giữ riêng, raw footage/QA vẫn ignored.

Metadata/SHAs/cases/timeline: [media manifest](../data/manifests/t5_4_portfolio_media.json).
[Static/media/frozen-fact validation](../data/manifests/t5_4_portfolio_validation.json),
[browser/playback checks](../data/manifests/t5_4_portfolio_browser_checks.json).

Git checkout portability: [sealed text bindings](../data/manifests/t5_4_portfolio_text_bindings.json)
chỉ chấp nhận CRLF/LF-equivalent presentation inputs, seal từ exact recorded bytes.
[LF index export check](../data/manifests/t5_4_portfolio_checkout_validation.json)
đạt89links/fullMP4decode mà không cần.env/raw PDFs/cache/models; intentional metadata
change trong isolated Temp copy bị hashguard reject. Original raw hashes/source/
M4 freeze/runner guards không đổi. [Final check](../data/manifests/t5_4_portfolio_final_validation.json).

## Checks repository và runtime

- Conda `ragschool` Python3.12.15: **387pytest pass** (270unit/117schema-isolatedDB),
  73.74s; CI-style mocked/offline model download guard enabled.
- **13Node UI contracts pass**, Ruff check/format **200files** pass.
  Existing Starlette/httpx deprecationwarning giữ nguyên, không thêm dependency.
- Read-only [frozen100 integrity](../data/manifests/t5_4_dataset_integrity.json):
  100cases/72spans/49chunks/60dev40test/legacy30questions19goldchunks preserved;
  canonical datasetSHA `d577dcde…`, no inference.
- [Publication snapshot](../data/manifests/t5_4_publication_snapshot.json):
  15ready/307unique/307FTS/15unchanged/0unfinished,103approved/40native/45excluded,
  original content/model/quality/hash/instruction gates pass.
- API tạm stop để chẩn đoán local checks, rồi Compose `up --wait`:
  API/DB healthy8001; [17model-free HTTP checks](../data/manifests/t5_4_restored_container_checks.json)
  pass về health/UI/MIME/catalog/clarification/abstention/422/request IDs.

### Failures được giữ và recovery

[Pilot log](../data/manifests/t5_4_pilot_failures.json), raw evidence dưới ignored
`data/processed/t5-4-*`; không waiver gate:

1. Browser checker sampling trước hashchange DOM transition: chờ exact target
   visible sau URL transition, vẫn kiểm keyboard/counter/visibility.
2. Axe không dùng được owned context từ `browser.newPage`: chuyển sang explicit
   `browser.newContext`/`context.newPage`, giữ A/AA scan.
3. Python tests/validators timeout cả parallel và serial. Initial memory-pressure
   hypothesis không được coi là proof; faulthandler chỉ ra `psycopg.wait_conn` trong
   DBfixture line19. Bounded native diagnostic kết nối được; dùng process-local
   **PGHOSTADDR127.0.0.1/PGCONNECT_TIMEOUT5** giúp test từng treo đạt11.73s rồi
   full387 và read-only validators đạt. Không sửa `.env`, credentials, app code,
   source/gold bindings hoặc Docker DB/cache để làm checks pass.

## Nhất quán benchmark

README/slides/interview dùng **original M4 final review**: 47/47tuned development,
**19/28heldout correct,29/108task-support,108/108faithful,0/7reject,0/20axes,
p9532.707s**. Atomic quoted block unit;79blocks non-task-support. Original one-time
test40 đã exposed; T5.4 new held-out inference0, global historical vẫn40.
Assistant review không independent/blind/document-disjoint; Linux Docker demo
không thay Windows M4 source fingerprint.

Inference code/config, source/gold freeze, claimed ledger, predictions/reviews/
failed test cases giữ nguyên. Instrumentation source T5.2 mới không bypass old
M4 exact source checker. Future quality work cần development/evidence/test version
độc lập mới.

## Nghiệm thu

**T5.4/M5 completed 2026-10-13** về consistent portfolio delivery:
static/media/frozen facts cross-check đạt, 92 final local document/media/slide links resolve,
full video decode và browser playback đạt. Final status ghi trong
[progress](progress.md), [handoff](handoff.md) và project plan. Quality targets
held-out chưa đạt vẫn được trình bày trong README/M4 report; portfolio delivery
không nâng quality snapshot thành production-ready.

Reproduction/check commands: [video guide](portfolio-demo.md), [README](../README.md).
