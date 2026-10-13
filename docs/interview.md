# RegulaRAG — phỏng vấn và CV

## Thông điệp mở đầu

> Tôi xây dựng RegulaRAG để tra cứu quy định UIT với bằng chứng có thể đối chiếu.
> Điểm tôi tập trung là provenance từ PDF/OCR tới quote và đánh giá tách fidelity
> khỏi correctness. Hệ thống chạy local CPU, có native FastAPI UI, tracing, Docker
> và CI. Development đã tuning đạt47/47 answerable, nhưng test một lượt chỉ19/28;
> tôi giữ cả lỗi để chỉ rõ bài toán còn lại là relevance/answerability/clarification.

Các câu trên mô tả project deliverables; điều chỉnh đại từ/ownership theo đóng góp
thực tế của người dùng khi đưa vào CV. Semantic reviews/implementation được làm
với AI assistant; không gọi đó là independent human evaluation.

## Overview 5 phút — rehearsal script

| Thời gian | Nội dung / thao tác | Bằng chứng để mở |
|---|---|---|
| 0:00–0:35 | PDF scan, điều kiện và amendments khiến tìm đúng con số chưa đủ; scope UIT/local research demo | [Intro slide](portfolio.html#intro) |
| 0:35–1:30 | Hỏi hè12; click `[S#]`, đọc văn bản/trang/đoạn. Model chọn PIDs, backend dựng answer | [Video](assets/regularag-demo.mp4), [demo guide](demo-guide.md) |
| 1:30–2:10 | D31: hè12 + không lớp ít sĩ số + minimum70; cần hai đoạn khác nhau | [Kịch bản](portfolio-demo.md) |
| 2:10–2:40 | D46 văn bản99999 không có evidence; minh họa known guard, không extrapolate mọi no-answer | Video chapter no-answer |
| 2:40–3:25 | Data/hash/review → E5+FTS/RRF/CE → registry → selector → citations; request ID/trace | [Architecture slide](portfolio.html#architecture) |
| 3:25–4:25 | Frozen60/40,47/47 vs19/28;108/108faithful vs29/108task support;reject0/7,p9532.707s | [Benchmark slide](portfolio.html#benchmark) |
| 4:25–5:00 | Three trade-offs và failure thật; next iteration cần independent test mới | [Limits slide](portfolio.html#limits) |

Kịch bản có tổng budget **300giây**; dùng video có chú thích để hỗ trợ rehearsal,
không xem script là bằng chứng đã có một human presentation được chấm độc lập.

## Deep dive 15–20 phút — agenda 18 phút

| Thời gian | Nội dung | Chi tiết nên nói |
|---|---|---|
| 0:00–2:00 | Corpus và publication | 15PDF/188pages,103approved/40native/45excluded; review hash-bound, technicalready≠legalactive |
| 2:00–5:00 | Ingestion/storage | Structured chunks, conditionalOCR, transaction/advisorylock, failed-update search gate, idempotency |
| 5:00–8:00 | Retrieval/freshness | E5small384, FTS≠BM25, RRFk60, filterbeforeLIMIT,20candidates/CE/windowmax,top4, unchangedclauses |
| 8:00–11:00 | Generation/citation | PIDs/strictJSON/input2304, dependency/facetchecks, literalspan/range/SHA, backendmetadata; limitation lexicalentailment |
| 11:00–14:00 | Three real fixes | GPAfalseexclusion; date-countD42; rule+signatureD06; retainedfailedruns andverifiedfull60 |
| 14:00–16:00 | Evaluation và remainingfailure | 60dev/40one-timefrozen test, reviewresponseSHA,19/28vs47/47,unsupportedT24–30; exposedtest |
| 16:00–18:00 | Deployment/trace/trade-offs | UUID→trace/CLI, actualstageusage/privacybounds, installedwheel/APIUI/nonroot,387pytest13UI/mockedCI, CPUlatency/compute0API≠free |

## Ba quyết định thiết kế quan trọng

### 1. PostgreSQL + pgvector và FTS trong một storage boundary

- **Lý do:** source metadata, publication state, vectors, keyword index và filters
  trong cùng lifecycle/transactions; dễ query provenance và kiểm update/delete.
- **Trade-off:** PostgreSQL Vietnamese FTS phải đo trên câu có dấu/không dấu/mã
  văn bản; `ts_rank_cd` không phải BM25; hybrid không tự tốt hơn dense-only.
- **Evidence:** T4.3 coredevelopment: vector41/47, keyword35/47, RRF36/47,
  CE41/47 completecorrect; CE vsRRF5pairedwins/0loss, cùnggold/corpus/LLMbudget.
  CEcorep9514.032→20.997s. Selectedtop4 samequalitytop8/12 trong single-pass runs.
- **Nếu hỏi “tại sao không vector DB riêng?”:** scope nhỏ, consistency/audit ưu
  tiên; benchmark hiện chưa chứng minh nhu cầu tách storage hoặc multi-service.
- [Ablation](benchmark-ablation-review.md), [architecture](architecture.md).

### 2. Qwen chọn passage IDs, backend dựng quote/citation

- **Lý do:** small-model free prose từng hallucinate/đổi quote/source. Request-local
  enum/strictschema giới hạn lựa chọn; resolver kiểm hash/offset/view/dependencies.
- **Trade-off:** quote dài, không diễn đạt tự nhiên; nguồn thật vẫn có thể sai task
  hoặc thiếu actors/conditions. Không gọi ID validity là semantic accuracy.
- **Evidence:** held-out108/108faithful quote blocks và40/40citationfidelity, nhưng
  **29/108task-support và19/28fullcorrect**, lexical obligations chưa tổng quát.
- **Nếu hỏi “citation có giải quyết hallucination?”:** ngăn invented quote/URL/page
  ở output boundary hiện tại, không ngăn unsupported/incomplete answer selection.
- [Passage/citation report](passage-citation-review.md), [M4](error-analysis-review.md).

### 3. Small pinned CPU models + staged low-memory release

- **Lý do:** RAM~12GB/RTX3050 6GB và APIbudget0; E5small/CPUCE/Qwen1.5BGGUF
  chạy local, exactrevisions/config/lock cho reproducibility boundary.
- **Trade-off:** cold/reload/serializedqueue và CE tăng latency. Benchmarkp9532.707s,
  target10s chưa đạt; video có loading thật, không giảm time rồi gọi là real latency.
- **Evidence:** configfinaltop4/candidates20/input2304/output64/retry1; API0VND,
 44519/576actualinput/outputtokens heldout; compute/electricity chưa định giá.
- **Nếu hỏi “GPU/API tăng tốc được không?”:** chưa có controlled benchmark tương
  ứng; không lấy ước đoán làm thành tích. Đo trên evidence/dev version mới trước.
- [Final config](../configs/rag/final.json), [runtime trace](observability-review.md).

## Ba lỗi thật — nguyên nhân, cách sửa và kiểm chứng

| Lỗi | Root cause | Sửa đúng boundary | Kiểm chứng / giữ failure |
|---|---|---|---|
| GPA≥8 đáng lẽ max30/mainsemester nhưng bị abstain | Wholeclause14.1 bị đánh affected dù1393 chỉ sửa14.1(b); cosine0.8888 vẫn vượt0.55 | Hash-bound unchanged14.1(a) view và scoped amendment hierarchy; không hạ threshold/nới callerfilter | GPA8:6supported/2correctabstain; fixed12:11supported/1abstain; affectedsummer/classsize vẫn cần1393; [report](gpa-credit-freshness-review.md) |
| D42 historicalcalendar gây falseabstention | `ngay01-12-2025` bị parse như count-of-days support facet | Tách explicitcalendar khỏi quantitativeunitintent; giữ historicalcutoff/sourcerules | D42 trở thành đủ facts trong fullfinal60; gold/configsource unchanged; [error inventory](../data/manifests/t4_4_error_cases.csv) |
| D06 rule ngày hiệu lực có đủ context nhưng onlysignaturePID | Iteration1 Qwen chọnP2literaldate mà không chọnrule “hiệu lực từ ngày ký”; resolver đúng khi từ chối | Expose requiredpassageIDs/signature_date obligation trongprompt; require cảrule+literaldate, không fallback metadata | Iteration1full60:46/47, failureretained; targetedmodelcheck rồi **newfull60**:47/47, không stitchreruns; [M4report](error-analysis-review.md) |

Khi kể lỗi, nêu điều mình **đã đo** và boundary thực sự thay đổi; không nói giảm
threshold là GPAfix, không đổi normalizedmetadata thành một quote nguồn.

## Một ví dụ hệ thống vẫn thất bại

**T24–T30 unsupported questions** trong lượt frozen test: cả7 expectedno-answer
vẫn trả các đoạn quote thật về chủ đề gần đó. Fidelity108/108 không giải quyết
answerability; lexical obligations không nhận diện mọi yêu cầu nằm ngoài corpus.
Đây là bằng chứng cần semantic relevance/answerability validation tốt hơn, không
thể chỉ thêm regex từ7testcases rồi báo held-out tăng.

- [21failures](../data/manifests/t4_4_held_out_failures.csv) và originalprediction/
  responsehashes được giữ. T01–T40 đã exposed.
- Next: author development/evidence version mới, independent reviewed test mới,
  measure fullanswer facts/taskprecision/reject/clarification/latency trên exactcode.
- No-answerD46 trong video là knowncontrol; không phủ nhận reject0/7 ở heldout.

## CV bullets — dùng số đã đo

Chọn2–3bullets phù hợp vai trò; có thể dùng bản tiếng Anh dưới đây. Không thay
held-out bằng tuneddevelopment, không gọi review là human/blind evaluation.

- Built an evidence-first Vietnamese RAG demo over **15 UIT documents / 307 approved
  chunks**, combining conditional OCR, hash-bound review, PostgreSQL FTS/pgvector,
  RRF and a CPU cross-encoder with explicit metadata/freshness guards.
- Implemented strict passage-ID selection with backend-validated Unicode offsets,
  hashes and citations; a frozen **60-development / 40-test** evaluation recorded
  **19/28 fully correct answerable test responses** and **108/108 source-faithful
  quote blocks**, while exposing **29/108 task-support citations** and rejection gaps.
- Packaged a shared FastAPI/native UI in a pinned non-root Docker image and added
  request-correlated bounded pipeline traces; verified **387 Python tests**, **13 UI
  contracts** and a **two-job hosted CI** with mocked model downloads/inference.
- Diagnosed **20 development error cases**, implemented three obligation/scope fix
  groups, and verified **41/47 → 47/47** complete development answers in full runs;
  retained one-time held-out failures and measured **p95 32.707s** on serialized CPU.

Đối chiếu số liệu: [held-out metrics](../data/manifests/t4_4_held_out_metrics.json),
[development metrics](../data/manifests/t4_4_development_metrics.json),
[CI evidence](../data/manifests/t5_3_hosted_ci_validation.json).

## Câu hỏi khó nên sẵn sàng trả lời

- **“Recall1 sao correct chỉ67.86%?”** Support chunks có trong ranked5 không bảo
  đảm budget/selector giữ đủ facts hoặc đúngtask; cuối cùng phải chấm actualanswer.
- **“0VND chi phí?”** Local APIspend; phần cứng/compute/điện/hosting chưa định giá.
- **“CI có tải model thật?”** Không; mocked/offline/downloadguard, realdevelopment
  HTTP/browser evidence chạy riêng; không dùng CI là held-out evaluation.
- **“Freshclone chạy được không?”** Image/UI/model-freeguards có runbook; fullRAG
  cần downloadedmodelcache, đúng15PDFSHA và operator-approvedpublicationinputs.
- **“Quy định mới nhất có hiện hành không?”** Verifiedlatest theofamily/corpus/
  scope/checkpoint; legalstatusunknown, không global/latestlegalverification.
- **“Video đã là userstudy?”** Không, captioneddevelopmentdemo + automatedchecks;
  rehearsal agenda chưa là independentlyassessed humanpresentation.
