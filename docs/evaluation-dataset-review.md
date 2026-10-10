# T4.1 — Dataset100 và freeze held-out

Ngày hoàn tất: **2026-10-10**. T4.1 completed; tiếp theo **T4.2 — evaluation runner**.
M4 còn runner/benchmark/error analysis.

## Đầu ra

Dataset tại `data/evaluation/v1/` gồm **100 mẫu**, **60 development / 40 test**, với
nhãn mong đợi 75 `answered`, 15 `insufficient_evidence`, 10 `needs_clarification`.
Đây là nhãn tham chiếu, không phải số câu model đã trả lời đúng.

| Category | Development | Test | Tổng |
|---|---:|---:|---:|
| `single_clause` — một điều khoản | 21 | 9 | 30 |
| `multi_clause` — kết hợp điều khoản | 12 | 8 | 20 |
| `temporal_scope` — thời gian/đối tượng | 9 | 6 | 15 |
| `no_answer` — ngoài phạm vi/thiếu đáp án | 8 | 7 | 15 |
| `clarification` — cần thông tin | 5 | 5 | 10 |
| `adversarial` — giả định sai/gây nhiễu | 5 | 5 | 10 |
| **Tổng** | **60** | **40** | **100** |

- D01–D30 giữ nguyên câu hỏi/đáp án/filters/paraphrase group và tập chunk gold frozen.
  D31–D60 là phần mở rộng development; T01–T40 là prospective question hold-out.
- Mỗi mẫu có category/status, reference answer, filters/scope, paraphrase group,
  rule families, provenance/origin và review note.
- Các mẫu answered có required facts riêng, mỗi fact tham chiếu một hoặc nhiều đoạn
  được định vị. Các mẫu clarification khai báo thông tin cần hỏi; no-answer nêu rõ
  dữ liệu/phạm vi thiếu, không gắn evidence tương phản thành gold answer.
- **72 curated spans / 49 unique approved chunks** từ 12 tài liệu; không chỉ chunk IDs.
  Trường dữ liệu có tài liệu/số văn bản/URL, PDF pages, locator, nguyên văn, Unicode
  offsets và source/content/excerpt SHA-256, article/clauses/extraction/quality.

## Quy trình source review

Đối chiếu các đáp án và required facts với approved source text, clauses/conditions,
ngoại lệ, actors, mốc thời gian và các scope notes từ M2. `manual_review.csv` ghi review
cho cả100 mẫu, gồm75 source-reviewed và25 behaviour-reviewed.

Reviewer là **assistant_source_review**. M2 đã có page/correction review hash-bound;
T4.1 sử dụng các văn bản đã publication và đối chiếu các spans/đáp án. Đây không phải
review độc lập của người dùng/chuyên gia pháp lý. Technical binding scripts chỉ kiểm
identity/filter/split/hash, không tự thực hiện semantic entailment hoặc auto-approve gold.

Các điểm kiểm tra quan trọng:

- D06 bind cả literal ngày ký và clause hiệu lực từ ngày ký cùng nguồn1393.
- D22/D23 ở PDF4 của956 có article metadata `null`; không gán Điều4 từ phỏng đoán.
- Giữ association của weights/actors, days/working days, cutoff inclusive, programme/
  cohort, điều kiện xét sửa/cấp lại và thẩm quyền quyết định.
- Confidentiality trong851 không bị đổi thành cho phép báo cáo vô danh.
- Song ngành112 xét đủ điều kiện tốt nghiệp ngành1, không tự yêu cầu đã nhận bằng.
- Đăng ký nguyện vọng không giới hạn không thành được gọi nhập học tất cả nguyện vọng.
- T02 được thu hẹp về một khoản thời lượng ĐATN trước freeze để khớp category,
  không dùng phản hồi model để điều chỉnh nhãn. Draft/pre-freeze reports giữ riêng.
- 43 là reviewed table serialization, lịch sử2012–2019; không xác nhận phí hiện nay.
- Negative diagram case T29 dựa vào832 `partial` và omitted regions PDF3/5; không
  coi body text là đầy đủ nhánh/mũi tên. Validator kiểm cả metadata omission này.
- Các negative về tương lai/cá nhân chỉ nói corpus không có evidence cần thiết,
  không khẳng định website hay hệ thống UIT không có dữ liệu đó.

`source_pdf_pages` là **approved chunk page range**, có thể coarse. Không thu hẹp
trang khi chưa có span-to-page proof riêng. OCR spelling/footer còn trong source spans
được giữ nguyên theo hash; reference answers có thể paraphrase. Curated excerpts là
phần citation cần thiết; raw PDFs, toàn văn/OCR, artifacts/model traces vẫn ở local ignored.

## Split và lịch sử exposure

30 câu cũ và các họ quy tắc đã được dùng ở T1–T3 đều ở development. `authoring.json`
ghi các exposure families và11 input registries đã kiểm, khóa bằng hashes trong freeze.
Các held-out cases đọc những cụm quy tắc mới như giới hạn/điều kiện song ngành, report
ĐATN, quản trịLCHT, chỉnh sửa/cấp lại/ngôn ngữVBCC, nguyện vọng/bảo lưu tuyển sinh.

98 paraphrase groups và68 rule families được kiểm không cắt qua split. Câu ghép có
nhiều families; từng family đều phải ở cùng split. Families đã tune không được đánh
dấu held-out chỉ bằng cách đổi question ID/cách diễn đạt.

Held-out được soạn sau M3, bằng cùng assistant/source corpus. Các document/chunk có
thể đã xuất hiện trong retrieval contexts trước đó; **không phải document-disjoint
hoặc blind independent test**. Đây là prospective question/rule-family hold-out có
exposure accounting do reviewer khai báo, không phải chứng minh semantic novelty tự động.

T4.1 không gửi các query test vào E5, reranker, Qwen hoặc API hỏi đáp. Chỉ SELECT gold
chunks/metadata/filters để xác thực source binding; **0 held-out RAG inference requests**.
Runtime prompts/guards/thresholds không được tune từ test labels trong bước này.
Loader `load_evaluation_cases()` mặc định development60; lấy test40 cần chọn split rõ.

## Freeze

Ghi một lần tại **2026-10-10T10:45:33.610837+00:00** trong `freeze.json`, trước vòng
tuning cuối. Runtime baseline commit `040dd30d28267afc2709ce415ce23402f98128b3`.

| Binding | SHA-256 |
|---|---|
| Dataset100 | `d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c` |
| Held-out40 | `d6a9f0c97925c5db41f0257ce83f5237f1a32d20569d043888a9fca5803fb457` |
| Evidence72 | `d34ca0a697b7eca1c45bacf0a1505d89860a4ad93e22a13a490e8449bebfc8ac` |
| Legacy30 | `7a2bb4801dac8c1d78e13aeac527dbc44b76583d0d5cb16cd40573445f1bfe0d` |

Lock còn giữ corpus/config hashes, baseline commit, authoring/review hashes và exposure
registry hashes. Canonical JSON/CSV hashing không phụ thuộc LF/CRLF hoặc pretty print.

- Builder từ chối nếu freeze đã tồn tại.
- Validator không overwrite freeze, không silent-rebind khi source/span/hash drift.
- Loader phát hiện labels/splits/evidence/authoring/review drift trước khi dùng dữ liệu.
- `t4_1_refreeze_rejection.json` lưu attempt freeze lần2 bị từ chối (expected exit1).
  Valid final recheck không thay đổi lock; failures phải giữ, không sửa gold để nâng score.

## Kiểm chứng

- 100 unique IDs/questions, đúng category counts/split60–40 và status contracts.
- 72span hashes/ranges/provenance/structure/quality; caller filters của75answered
  không loại support/context gold. Contrast evidence được kiểm riêng, không là gold recall.
- Source PDF bytes match15manifest hashes, current approved/model/publication gates đạt.
- Legacy30/19 bindings và nguồn/hash/relations không thay đổi.
- Corpus15ready/307chunks/307FTS/15unchanged/0unfinished;103approved/40native/45excluded.
- **300 tests passed** (188unit/112schema-isolatedPostgreSQL),1knownTestClient deprecation,
 109,19s ở full suite. Ruff check/format sạch, dependency lock70/pip check sạch.
- Tests kiểm split/family/exposure leakage, thiếu facts, contrast bị promote, Unicode
 offsets/hash/page/article drift, defaultdev loading, freeze drift và SQL filter/quality/
 publication/model guards. Các test mutation dùng fixtures/temp copies/schema riêng.

Artifacts tóm tắt tại `data/manifests/t4_1_*`; dataset gồm:

| File | Vai trò |
|---|---|
| `authoring.json` | Spec do reviewer soạn, marker/source choices, exposure mapping |
| `questions.json` | 100 canonical cases dùng bởi runner sau này |
| `evidence.json` | Curated source spans và provenance đã bind |
| `manual_review.csv` | Review notes/verdict cho100cases |
| `freeze.json` | Dataset/held-out/evidence/corpus/history lock |

## Sử dụng

Trong Conda `ragschool`; validation cần DB/corpus local đã review và raw PDF đúng hashes.
Validation không tải model hoặc tạo inference run.

```powershell
python scripts/validate_evaluation_dataset.py --summary data/manifests/t4_1_dataset_recheck.json
python scripts/check_corpus_publication.py --output data/manifests/t4_1_corpus_recheck.json
$env:REGULARAG_RUN_DB_TESTS = "1"
python -m pytest
python -m ruff check --no-cache .
python -m ruff format --no-cache --check .
```

T4.2 tiếp theo xây runner đọc frozen data, tách metrics trả lời/retrieval và nhóm lỗi.
Development60 dùng để tuning/ablation. Chọn cấu hình cuối trước held-out; khi đo test,
giữ predictions/config/commit/timing và báo failures, không quay lại tune cùng test labels
rồi gọi kết quả là held-out. M4 chưa có accuracy/latency/cost benchmark trên dataset100.
