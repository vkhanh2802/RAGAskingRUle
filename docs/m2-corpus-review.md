# M2 — Publication toàn corpus theo phạm vi đã duyệt

Ngày hoàn tất: 2026-10-09. Corpus15 PDF/188 trang; parser `structured-ocr-v2`,
model/prompt pins như baseline. M2 đạt phần ingestion/hybrid/filter/development theo
supported scope đã ghi nhận. Ready không đồng nghĩa văn bản hiện hành hay đáp án đúng.

## Snapshot và nghiệm thu

- 15/15 documents ingestion-ready/publication-ready;307 chunk/307 unique IDs và307 FTS.
- Lượt thứ hai15 unchanged, không tạo duplicate;0 run pending/processing.
-19 bound gold chunks của development30 còn nguyên source/content/page bindings.
-188 trang:103 approved,40 native không có flag cần review,45 excluded,0 pending.
-156 tests pass (67 unit/89 PostgreSQL integration); Ruff/format, pip check và lock70/70 pass.
-001–006 migrations chạy lại skip. Docker từng dừng gây connection timeout/test hang;
  đã khởi động lại Desktop/db và rerun sạch. Không có lỗi publication còn mở.

Bằng chứng: `data/manifests/m2_publication_snapshot.json`, `m2_chunk_inventory.csv`.
Snapshot kiểm lại source PDF hashes, chunk text hashes, model fingerprint, quality,
FTS và gold drift; full-text artifacts vẫn ở ignored `data/processed/`.

| Nguồn | Chunk | Coverage | PDF pages excluded / omitted region |
|---|---:|---|---|
|112|23|partial|2,9|
|1393|3|full|—|
|159|24|partial|9–11|
|277|16|partial|2|
|308|53|partial|2,3|
|412|17|partial|2,6,8,10|
|43|3|full|—|
|513|4|full|—|
|697|18|partial|2,8,9,11|
|790|45|partial|1,2,18|
|803|5|partial|5|
|832|5|partial|diagram regions on3,5; body retained|
|851|28|partial|11,13|
|894|38|partial|3,4,18,20–25,29–37|
|956|25|partial|3,6,9,10,13|

Full/partial mô tả phần evidence đã kiểm, không chứng nhận mọi pixel của PDF. Các
diagram/templates không có durable text/layout representation được loại rõ; không
đưa chúng vào retrieval để đạt số lượng. 697 extension fee/remuneration swimlane,
790 grade table và956 merged certificate/program tables còn ngoài supported scope.

## Review và correction

Assistant đã đối chiếu133 trang của11 nguồn chưa publication với raster/text; đây
không phải independent human review. `m2_*_page_decisions.csv` ghi decision/layout/
source+original text hashes; `page_reviews.csv` bind cleaned-text sau post-edit.

`bind_page_reviews.py` chỉ materialize explicit decisions và full post-edits, không
auto-approve theo confidence. `apply_review_plan.py` áp dụng edits do reviewer chỉ
định, từ chối edit/boundary không tồn tại; `use_existing_postedit` giữ bản bảng đã
tái dựng thủ công. Batch quyết định được validate trước khi sửa shared manifest.
Correction giữ original OCR hash, reviewed text và method/note. Raw OCR/raster/TSV
không bị thay bằng post-edit. Clone thiếu correction/review đúng hash cần review lại.

43 được đọc lại cả2 raster: xác nhận số43/ngày23June2020 và từng cell/merged cell.
Serialization lặp lại column labels/cohort/design duration, phân biệt expired-study
cells với percentage, và lịch HK/NH riêng của2012–2019. Đây là table representation
đã post-edit, không phải nguyên chuỗi OCR hay toàn văn PDF nguyên dạng.

Mixed-page omission ở832 có flag `partial_layout_omitted`, quality/SQL/API giữ
`omitted_layout_pdf_pages`; source không bị báo full khi diagram bị cắt. API cũng
giữ `metadata_note` để hiển thị scope caveats/source inconsistencies.

## Những điều kiện đã kiểm và metadata

-412+513 giữ hai nguồn riêng, quan hệ base/amendment. 513 sửa scope/clause công nhận;
  online chỉ free electives, trườngtop100, ranking không quá3năm, nội dung không trùng
  và liên quan chuẩn đầu ra;15actualhours/credit, cap3credits. 412 còn mứcC/5of10,
  completionwithin5years, gradeM; clause bị sửa phải đối chiếu amendment.
-412 áp dụng regular/distance, loại joint programs; audience tags được phân tách `;`
  và membership vẫn exact, không taxonomy inheritance. Companion full/ready/in-context
  vẫn là gate; partial base412 không làm513 trở thành bản toàn văn thay thế.
-277 capstone6credits/fromcohort2024;697 enterprisecapstone10credits/500hours,
  grading40percentcouncil+10supervisor+50companymentor. Không trộn hai quy định.
-803 working days khác832 calendar days; i ở832 là variable, không phải digit1.
-851 hiệu lực01September2024, không phải issued14August; không xem xét retroactive
  với products trước hiệu lực. Council/quorum/penalty/exceptions được giữ.
-894 giấydegree30days/papercertificate15days/digital5days; reissue/correction3WORKING
  days khác copy same-day/nextworkingday after15h; temporarycertificate3months.
-112 TOC/appendix có year2023 khác main2024;697 appendix kỳ2023-2024 khác extension
  kỳ2024-2025;308 priority formula có internal crossreference bất thường. Giữ source
  inconsistency, không tự sửa thành một kết luận pháp lý.

`source_metadata_reviews.csv` bind ISO start/scope/note với sourceSHA;851 được ghi
2024-09-01,308 bỏ nhãn cohort2025-only không có bằng chứng. Cohort reviews thêm277
from2024 và43 supported table schedules2012–2019. Các nguồn vẫn legal_status unknown;
43/790 không được suy ISO start từ issued date/academic year.

## Retrieval và API trên corpus mở rộng

Development30 giữ nguyên binding, chạy180 rows mới ở `m2_development_retrieval.csv`:

|Condition/mode|Gold hit@1|Hit@2|Hit@5|Complete evidence@2|
|---|---:|---:|---:|---:|
|Unfiltered vector|20/30|24/30|25/30|24/30|
|Unfiltered keyword|8/30|9/30|18/30|8/30|
|Unfiltered hybrid|11/30|16/30|23/30|15/30|
|Scoped vector|27/30|30/30|30/30|29/30|
|Scoped keyword|14/30|22/30|27/30|21/30|
|Scoped hybrid|18/30|28/30|30/30|28/30|

Scope violations0. Scoped metrics ổn định nhưT2.4; corpus lớn hơn làm unfiltered
retrieval khó hơn. Không dùng query cache/cold-start latency làm benchmark.
Reference do assistant source-read rồi biên soạn, chưa held-out/independent human gold.

12 identifier probes ×3 modes ở `m2_corpus_retrieval.csv`: document hit@1 vector9/12,
keyword12/12,hybrid12/12. Document hit chưa là đúng clause: M211 keyword lấy definitions
thay effective clause; M212 hybrid lấy revocation thay issuance deadlines.

API/model thật: keyword-unfiltered4 câu đều abstain; hybrid-scoped4 câu có đúng
document context nhưng không có câu nào được manual review xác nhận trả lời đúng:

|Câu|API scoped result|Manual verdict|
|---|---|---|
|M201 onlinecredits|insufficient_evidence / invalid_schema|Full condition quote vượt schema; không tính success|
|M204 tuition2018/4years|answered|Quote thật nhưng về2012/4.5years: wrong cohort|
|M211 effect851|insufficient_evidence / unverified_quote|Model quote ISO metadata thay literal source body|
|M212 issuance894|insufficient_evidence / invalid_json|Wrong section/truncatedJSON|

Bằng chứng: `m2_api_smoke.csv`, `m2_filtered_api_smoke.csv`, `m2_api_manual_review.csv`;
full trace ở ignored processed. M204 là regression quan trọng: document-level cohort
filter không chọn table rows; substring/citation validation chưa kiểm relevance.
M2 ở đây là technical ingestion/retrieval milestone, không phải answer-quality gate.

## Tái lập và tiếp theo

```powershell
python scripts/migrate.py
python scripts/prepare_structured.py --output-dir data/processed/m2-publication
python scripts/validate_structured.py --input-dir data/processed/m2-publication --inventory data/manifests/m2_chunk_inventory.csv
python scripts/index_baseline.py
python scripts/index_baseline.py
python scripts/check_corpus_publication.py
python scripts/evaluate_development.py --output-dir data/processed/m2-development-retrieval --summary data/manifests/m2_development_retrieval.csv
```

Preparation cần review/correction đúng hash. Giữ old runs/bindings để phát hiện drift;
không auto-rebind khi source/labels đổi. Server smoke đã dừng, DB healthy; Git chưa commit.
Tiếp theo T3.1 reranker sau baseline M2, đo gold evidence/latency trên cùng corpus.
Theo dõi D15/D30, wrong-cohort M204 và clause-level ranking; generation/schema/relevance
thuộc T3.2/T3.3 và evaluation tiếp theo. Các layouts excluded tiếp tục có backlog riêng.
