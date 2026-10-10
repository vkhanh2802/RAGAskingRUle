# Sửa feedback demo — GPA và điều khoản không bị sửa đổi

Hoàn tất ngày 2026-10-10. Pipeline `rag-clause-scoped-v2`, freshness
`clause-scoped-v2`; behaviour `guarded-behaviour-v1` và passage prompt v3.

## Lỗi và bằng chứng nguồn

Câu người dùng: “Nếu điểm trung bình đến hiện tại của tôi >=8.0, tôi sẽ được phép
đăng kí bao nhiêu tín chỉ?”

- Pilot G01 trả quy định **học kỳ hè 12 tín chỉ** từ1393; G02 chỉ chọn790 lại bị
  `latest_excluded_by_filters`. Đây là lỗi topic/freshness của điều khoản.
- Dense đã tìm `uit_790_2022:chunk:0020` với cosine **0.8888168003802542**, vượt
  threshold0.55. Threshold được giữ0.55; thay ngưỡng không giải quyết nguyên nhân này.
-790 Điều14 khoản1(a), PDF12–13, quy định học kỳ chính thông thường14≤n≤24;
  **ĐTBC≥8,0 đến thời điểm đăng ký được phép đăng ký tối đa30tín chỉ**. Parent clause
  còn ghi tín chỉ tại Trường/CSĐT khác, ngoại lệ còn phải học<14 và không/hủyĐKHP→0.
-1393 sửa **Điều14 khoản1(b) — học kỳ hè**, cùng4.3/12.1/23.1. Hash-bound witness
  đã ghi rõ `article14clause1itemb`, nhưng frozen affected-clause envelope14:[1]
  trước đây loại cả1(a). PDF790 và approved text đã được đối chiếu lại.
-790 Điều24, PDF20–21, định nghĩa ĐTBC dùng đăng ký tín chỉ, bao gồm học phần không
  đạt; ĐTBCTL dùng tín chỉ tích lũy đạt từ5,0. Điều này không nằm trong amendment map.

## Thay đổi

1. Freshnessv2 chỉ buộc companion cho phạm vi bị amendment tác động. Điều/khoản đã
   xác minh không bị sửa đổi được dùng từ nguồn gốc, kể cả caller chỉ chọn790.
2. Với main-semester GPA, view chỉ được tạo khi relation review source/hash-bound
   chỉ rõ1(b), metadata clause khớp và text có parent1→a)học kỳ chính→b)học kỳ hè
   rõ ràng. View giữ toàn parent/main block, dừng trước1(b).
3. `evidence_char_ranges` là Unicode offsets trên **text/hash gốc**; prepare/resolve
   kiểm range, text, SHA và sourceID. Full approved excerpt vẫn dùng đối chiếu;
   actual cited passage nằm trong view. UI hiển thị range trong provenance.
4. Candidate/support checks phân biệt GPA/học kỳ chính với học kỳ hè và language
   progress. Chỉ primary `unchanged_verified_clause` được bỏ lower blocked candidates;
   primary bị block hoặc chưa có chứng nhận unchanged giữ freshness context gate.
5. Full replacement, unknown hierarchy/witness, source drift, unverified date,
   applicable update bị filters/budget/quality/hash loại vẫn dẫn abstention.

Nguồn không bị loại chỉ vì năm ban hành đã lâu. Freshness vẫn là verified family/
snapshot/request scope; explicit dates/cohort/audience/IDs giữ strict. Không đổi
PDF/index/chunk text, relation manifest, embedding fingerprint hoặc gold bindings.

## Chạy model thật và review

Final verified run8, sau khi giới hạn lower-failure handling vào unchanged primary:

| Case | Kết quả đã review |
|---|---|
| G01 | Query gốc, all sources:790/mainsemester/cap30 |
| G02 | Query gốc,790-only: cùng unchanged1(a), filter giữ nguyên |
| G03 | Explicit mainsemester/ĐTBC≥8:cap30 với complete conditions |
| G04 | ĐTBC7,5: normal14–24; quote giữ30 chỉ khi ĐTBC≥8, không gán30 cho7,5 |
| G05 | Explicit hè:1393/cap12 và điều kiện học mới/lại/cải thiện/mở lớp |
| G06 | Hè790-only: correct abstention trước generation |
| G07 | Sĩ số lớp790-only: correct abstention, không dùng50cũ |
| G08 |790 Điều24: ĐTBC/ĐTBCTL đúng định nghĩa; còn extra related definitions |

-8/8 declared cases đạt:6 supported answers/2 correct abstentions; p50 **8.761s**,
  p95 **17.572s**. Span/citation/support/filter/provenance/latest audits0errors.
- Fixed regression12:11 supported primary answers/1 correct old-only abstention;
  p50 **10.591s**, p95 **15.609s**. Summer1393/class70/recognition513/historical412/
  43historicalrow/851literaldate/894deadline/159reviewer/956language cap giữ đúng.
- Timings là mixed cold/warm trên local CPU, serialized, không controlled comparison
  hoặc held-out accuracy. Status `answered` không tự là semantic correctness;
  manual CSV ghi verdict sau khi đọc actual quoted conditions.
- Pilot/model failures giữ ở `gpa_credit_pilot.csv` và ignored traces; reaudit cố ý
  rejectG01 sai support/G02 sai expected status, lưu `gpa_credit_pilot_reaudit.json`.
- Reference note F01 cũ nói790cap10 là không chính xác: approved790 phần hè cũng ghi12.
  Regression kiểm1393 cùng điều kiện sửa đổi; không sửa frozen reference để đổi điểm.

Aggregates: `data/manifests/gpa_credit_verified*.csv/json`,
`gpa_credit_manual_review.csv`, `gpa_credit_regression_manual_review.csv`,
`gpa_credit_retrieval_review.json`. Earlier successful iterations giữ riêng;
không ghép các reruns thành một benchmark.

## Web demo và quality gate

- Persistentdemo **http://127.0.0.1:8000/** đã restart, health/database OK,
  catalog15/pipelinev2, listenerPython16956/Conda wrapper38292 khi chốt bước.
- MicrosoftEdge headless: **22assertions/5real requests** đạt. Query gốc all sources
  và790-only trả30; hè790-only abstain; personal training-domain hỏi audience rồi
  explicit regular reply giữ query/filter và trả30. Citation/view/provenance đúng.
- Initial/GPA-result automatedaxeA/AA0violations; responsive375/812landscape/768tablet
  không overflow, reduced motion và browsererrors checks đạt.
- Browser pilot kế thừa domain từ mẫu hè nên câu cá nhân cần audience; API hỏi lại
  đúng, QA lại kỳ vọng answered. Final bắt đầu với blankform và kiểm riêng cả
  clarification/reply. Failed QA summary giữ `gpa_credit_ui_pilot_review.json`;
  final `gpa_credit_ui_review.json`. Raw records/screenshots ở ignored processed.
- **322pytest:208unit/114schema-isolated PostgreSQL**, `REGULARAG_RUN_DB_TESTS=1`;
  **12Node UI contracts**; Ruff check/format153files; lock70/pipcheck đạt.
- Frozen100 giữ datasetSHA
  `d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c`;
  legacy30/19 giữ nguyên,0held-out RAG inference. Corpus15ready/307chunks/307FTS/
  15unchanged/0unfinished; pages103approved/40native/45excluded.

## Reproduce

Trong Conda `ragschool`, với Docker/cache/source artifacts sẵn có:

```powershell
python scripts/inspect_gpa_retrieval.py --output data/processed/gpa-credit-reproduce/retrieval.json
python scripts/run_baseline_samples.py --questions data/manifests/gpa_credit_questions.csv --output-dir data/processed/gpa-credit-reproduce/api --summary data/manifests/gpa_credit_reproduce.csv --limit 8
python scripts/audit_passage_samples.py --input-dir data/processed/gpa-credit-reproduce/api --summary data/manifests/gpa_credit_reproduce_span_audit.json
python scripts/audit_reranker_samples.py --results data/processed/gpa-credit-reproduce/api/results.jsonl --manual data/manifests/gpa_credit_manual_review.csv --output data/manifests/gpa_credit_reproduce_freshness_audit.json
```

Optional browser tooling theo `docs/demo-ui-review.md`; đặt `DEMO_GPA=1` khi chạy
`scripts/check_demo.py --real` để dùng GPA cases, hoặc chạy Node helper trực tiếp với
`DEMO_REAL=1`, `DEMO_BASE_URL` và `DEMO_OUTPUT_DIR` cho persistentserver.

Item-level view hiện phục vụ hierarchy/witness rõ này; unknown/mixed boundaries còn
bảo thủ, lexical facets chưa general entailment. Combined-main/summer completeness
chưa được đo trong step này. M4/T4.2 runner và held-out benchmark vẫn là bước tiếp theo.
