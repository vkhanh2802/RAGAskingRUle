# T3.3 — Clarification, abstention và phạm vi áp dụng

Ngày hoàn tất: **2026-10-10**. Bước kế tiếp: **T3.4**; chưa nghiệm thu M3.

## Kết quả chính

- Policy `clarify-scope-v1` chạy trước retrieval/model khi thông tin còn thiếu hoặc
  mâu thuẫn. API trả đủ ba trạng thái `answered`, `insufficient_evidence`,
  `needs_clarification`, với lý do và câu hỏi bổ sung có cấu trúc.
- Bộ 20 tình huống development đạt hành vi dự kiến: **8 hỏi lại, 7 abstention,
  5 trả lời được**. Cả năm câu trả lời có bằng chứng chính hỗ trợ sau đối chiếu thủ công.
- Bộ positive regression 12 câu: **11 câu trả lời có bằng chứng hỗ trợ và 1 abstention
  đúng** khi caller chỉ cho phép văn bản cũ. Historical cutoff vẫn giữ quy định 412
  trước khi có sửa đổi 513.
- **247 tests pass**, Ruff check/format và dependency lock 70/70/pip check đạt.
- Corpus giữ **15 ready / 307 chunks / 307 FTS / 19 gold bindings không đổi**;
  source PDF hashes khớp và không có ingestion run chưa hoàn tất.

Đây là development/assistant review, chưa phải đánh giá độc lập hoặc held-out accuracy.
HTTP 200, status `answered`, citation khớp và similarity score không thay thế kiểm tra
đáp án có hỗ trợ ngữ nghĩa. API không trả confidence dạng phần trăm.

## Quy tắc phạm vi

`src/regularag/generation/clarification.py` phân tích các thông tin được nêu rõ trong
câu hỏi, caller filters và optional `scope`:

| Trường | Ý nghĩa |
|---|---|
| `cohort_year` | Khóa tuyển sinh, integer 1980–2100 |
| `applies_to` | Exact audience tags như `undergraduate_regular`, `undergraduate_distance` |
| `programmes` | `ctc`, `cttn`, `cta`, `cttt`, `viet_japan`; nhận mã hoa/thường |
| `as_of` | Ngày đối chiếu ISO; không suy từ năm ban hành hoặc khóa tuyển |
| `design_years` | Thời gian thiết kế chương trình để chọn hàng bảng học phí gia hạn |
| `project_type` | `regular` hoặc `enterprise` cho đồ án |

- Câu hỏi áp dụng ngoại ngữ cho sinh viên thiếu khóa/hệ/chương trình sẽ được hỏi lại
  khi các trục đó cần thiết. Không áp quy định 956 từ khóa 2026 cho khóa 2025 hoặc hệ từ xa.
- Tra cứu văn bản cụ thể hoặc domain cụ thể được phân biệt với câu hỏi áp dụng cá nhân.
  Ví dụ hỏi ngày bắt đầu hiệu lực 851 không cần hỏi khóa; đọc Điều 1 của 277 không cần
  hỏi khóa người dùng. Câu hỏi chương trình ngoại ngữ có nhiều đáp án vẫn cần mã chương trình.
- Học phí gia hạn cần khóa và thời gian thiết kế; câu hỏi áp dụng còn cần thời điểm.
  Bảng 43 chỉ là lịch sử 2012–2019, không đủ để xác nhận mức thu hiện nay.
- Đồ án chung chưa rõ loại sẽ hỏi thông thường hay tại doanh nghiệp, tránh tự chọn
  giữa 6 và 10 tín chỉ. Câu hỏi cá nhân về đồ án/KLTN/học vụ có thể cần hệ đào tạo.
- Ngày lịch sai hoặc chỉ nêu năm để đối chiếu sẽ hỏi ngày chính xác. Chỉ các cue lịch
  được khai báo mới chuẩn hóa; không có query rewriting hoặc bộ nhớ hội thoại.
- Caller filters luôn được giữ. Scope/câu hỏi mâu thuẫn với filters hoặc với nhau
  dẫn `needs_clarification` trước retrieval. Không tự nới document IDs, cohort hoặc ngày
  để đưa tài liệu khác vào. SQL vẫn OR trong list, AND giữa fields, unknown bounds bị loại.
- Thông tin rõ từ scope/câu hỏi có thể **bổ sung field filter còn trống** cho trục có
  metadata được chứng minh. Topic văn bản/domain rõ ưu tiên trước từ khóa cross-reference.
  Programme và design duration lọc passage, không giả tạo document metadata mới.

Response phân biệt `requested_filters` với `applied_filters`, trả `resolved_scope`,
`behaviour_policy`, `clarification.required_fields/questions/conflicting_fields`.
Khi cần hỏi lại, không truy vấn DB/embedding/reranker/LLM; sources/citations rỗng.

## Abstention và khác biệt phiên bản

- Không có kết quả phù hợp: `no_matching_evidence`. Không chuyển sang khóa/hệ khác.
- Có context nhưng thiếu phần được hỏi: `missing_support_candidates`,
  `incomplete_passage_support` hoặc `no_supported_selection`. Lỗi binding/schema,
  context budget, source drift và latest guards vẫn chặn câu trả lời như trước.
- Hỏi còn hiệu lực pháp lý khi source status `unknown`: `legal_status_not_verified`.
- So sánh/hợp nhất phiên bản chưa đủ chứng cứ: `version_comparison_not_consolidated`.
  Backend trình bày riêng ngày ban hành, vai trò base/amendment, nguồn liên quan,
  cohort/mốc hiệu lực được ghi nhận trong `version_notes`, gắn source ID để đối chiếu.
  Đây là khác biệt metadata đã kiểm chứng, không phải bản hợp nhất toàn bộ điều khoản.
- C13 nêu riêng 790 (2022-09-28/base) và 1393 (2023-12-29/amendment); 790 chưa có
  ISO effective start. Không suy pháp lý hiện hành từ ngày mới hơn. Không đưa lại
  affected old clauses đã bị freshness policy loại để tạo comparison.
- Explicit old-only filter vẫn `latest_excluded_by_filters`; lịch sử `as_of` không
  buộc future amendment. Latest vẫn chỉ trong verified family/corpus/snapshot/request scope.

## Citation support và minimality

Backend chỉ bỏ bớt **passage do model đã chọn** khi một tập nhỏ hơn vẫn đủ declared
support facets và tất cả signature dependencies. Không chọn hộ model các facts khác,
không cắt giữa condition/exception block để làm ngắn đáp án. Scope programme phải
có hỗ trợ cho từng mã được hỏi. Table row selection dùng cả structured reply scope.

Hai lỗi thực tế được phát hiện và giữ lại:

1. **C17 pilot/cohort-regression:** câu hỏi số tín chỉ đồ án và khóa áp dụng ban đầu
   trả điều kiện đăng ký (nợ 8 tín chỉ) hoặc header. Thêm kiểm “số lượng tín chỉ của
   học phần”, chiều ghi `tín chỉ: 6`, và literal intake statement. Targeted rerun và
   complete behaviour-final trả đúng Điều 1/PDF 3/chunk0004: 6 tín chỉ, từ khóa 2024.
2. **D23 development-final:** model trả chuẩn quá trình có nhắc IEL02 nhưng không trả
   IEL01 là tiên quyết. Audit identity cũ đạt; manual support thất bại. Guard mới yêu
   cầu quan hệ tiên quyết đến đúng mã môn, không chỉ có “đăng ký” và mã môn trong text.
   Rerun D22/D23 đúng chunk0007/PDF 4, không gán article metadata chưa chứng minh.
   D26 được sửa để “mấy đợt mỗi năm” không sinh thêm facet hỏi số năm; rerun chỉ trả
   4 đợt vào tháng 2, 5, 8, 11, không kèm tuổi chứng chỉ.

Facets vẫn là lexical checks có khai báo, không phải general semantic entailment.
Câu hỏi chung còn extra material, ví dụ D03/D08/D10/D16/D20/D27; whole programme blocks
của C08/D28/D29 giữ cả các mốc học kỳ lân cận. Các notes này nằm trong manual CSV.

## Các lượt chạy và timing

| Lượt | Requests | Kết quả ghi nhận | p50 / p95 toàn request |
|---|---:|---|---:|
| `behaviour-final` | 20 | 8 clarify / 7 abstain / 5 supported primary answers | 1,592 / 15,843 ms |
| `positive-api` | 12 | 11 supported primary answers / 1 correct abstention | 20,279 / 43,983 ms |
| `development-final` | 30 | 30 `answered`; manual 29 primary supported, D23 sai topic | 17,740 / 38,864 ms |
| `prerequisite-regression` | 3 | D22/D23 đúng prerequisites, D26 đúng schedule | 22,565 / 76,947 ms |

Behaviour median bị chi phối bởi các ca không generation; 8 clarify mất 22–131 ms,
median 22 ms. Không dùng con số này làm generation latency. Cold first generation
37,609 ms ở behaviour-final; positive first request 70,375 ms; prerequisite cold request
82,989 ms. CPU/RAM tải khác nhau, mixed cold/warm; không có controlled speed benchmark.
T3.2 median 13,572 ms không chứng minh policy mới nhanh hơn/chậm hơn độc lập với máy.

Final guard thay đổi **sau** complete development30 và positive12; đã rerun ba ca bị
ảnh hưởng. Không ghép targeted reruns thành một complete 30/30 accuracy hoặc trộn timing.
`t3_3_development_reaudit.json` áp guard mới lên trace cũ và lưu **support error D23**,
identity/citation/filter errors 0; exit 1 là expected rejection của output trước sửa.
`t3_3_prerequisite_audit.json` kiểm output mới đạt. Golden dataset/evidence không rebind.

## Bằng chứng và kiểm chứng

- `data/manifests/t3_3_behaviour_questions.csv`: 20 cases, expected status/reason.
- `t3_3_behaviour_final.csv`, `t3_3_behaviour_manual_review.csv`,
  `t3_3_behaviour_audit.json`, `t3_3_behaviour_freshness_audit.json`.
- `t3_3_positive_api.csv`, `t3_3_positive_manual_review.csv`,
  `t3_3_positive_audit.json`, `t3_3_positive_freshness_audit.json`.
- `t3_3_development_final.csv`, `t3_3_development_manual_review.csv`,
  `t3_3_development_audit.json`, `t3_3_development_reaudit.json`,
  `t3_3_prerequisite_regression.csv`, `t3_3_prerequisite_audit.json`.
- `t3_3_publication_snapshot.json`: 15 unchanged / 0 unfinished / 103 approved,
  40 native, 45 excluded pages; 19 gold chunk bindings giữ nguyên.
- Pilot, thất bại và config/model/raw outputs giữ trong ignored `data/processed/t3-3-*/`.
  Audit ghi summary cả khi thất bại, tách support khỏi citation fidelity.
- Tests cover scope conflicts/validation, no-model clarification, programme support,
  source-vs-personal applicability, signature dependency, empty scoped evidence, SQL/API
  cohort isolation, prerequisite mismatch và annual-unit ambiguity.
- Docker bị dừng làm một lượt pytest timeout; khởi động lại rồi full suite đạt
  **247 passed** (143 unit / 104 PostgreSQL integration), 1 known TestClient deprecation.
  Lượt final pass 166,63 s; integration schemas riêng, corpus public không bị sửa.
- Ruff check/format sạch; dependency lock/pip check sạch; không thêm migration/model.

## Tái lập

Trong Conda `ragschool`, Python 3.12; cần corpus local đã được review/index và model cache.
Dùng output paths mới cho mỗi lần đo để giữ failures/configs cũ.

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:REGULARAG_RUN_DB_TESTS = "1"
$env:TEMP = "C:\Users\Khanh\AppData\Local\Temp\opencode"
$env:TMP = $env:TEMP
docker compose up -d --wait
python -m ruff check --no-cache .
python -m ruff format --no-cache --check .
python -m pytest
python scripts/run_baseline_samples.py --questions data/manifests/t3_3_behaviour_questions.csv --output-dir data/processed/t3-3-behaviour-reproduce --summary data/manifests/t3_3_behaviour_reproduce.csv --limit 20
python scripts/audit_passage_samples.py --input-dir data/processed/t3-3-behaviour-reproduce --summary data/manifests/t3_3_behaviour_reproduce_audit.json
python scripts/check_corpus_publication.py --output data/manifests/t3_3_publication_recheck.json
```

## Bước tiếp theo và Git

T3.3 đạt các ví dụ answered/insufficient/clarification/khác biệt phiên bản và development
calibration. **T3.4 còn pending**: tối thiểu 20 tình huống về giả định sai, yêu cầu bịa,
chỉ dẫn giả trong tài liệu và ngoài phạm vi; ghi pass/fail trước nghiệm thu M3.
20 ca ở báo cáo này tập trung T3.3, chưa thay thế behavioral gate T3.4.

Theo yêu cầu người dùng, từ bước này commit sau mỗi bước hoàn tất kiểm chứng; quy tắc
lưu tại `AGENTS.md`. Repo trước đó chưa có commit: commit T3.3 là initial commit gồm
code/config/tests/tài liệu và manifest tóm tắt của trạng thái đã kiểm chứng đến T3.3.
`.env`, PDF raw, toàn văn/OCR/artifacts và model traces giữ ngoài Git.
