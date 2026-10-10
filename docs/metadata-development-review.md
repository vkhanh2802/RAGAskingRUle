# Metadata filtering và development set — T2.4

Ngày: 2026-10-08. Migration `006_metadata_filters`; policy `evidence-metadata-v1`.
T2.4 hoàn thành về filter chung, 30 câu development có evidence và đánh giá retrieval.
M2 còn blocked ở publication toàn corpus: 4/15 nguồn ready, 121 trang chờ review.

## Hợp đồng filter

`POST /api/v1/ask` nhận optional `filters`. Không có filter hoặc list rỗng nghĩa là
không thêm restriction; publication/model/quality allowlist vẫn áp dụng.

| Field | Ý nghĩa |
|---|---|
| `document_ids` | Document IDs chính xác; luôn giao với eligible allowlist |
| `domains` | Tags: academic_training, graduation_thesis, foreign_language… |
| `document_types` | regulation, decision, procedure, notice |
| `applies_to` | Audience tag chính xác, ví dụ undergraduate_regular |
| `cohort_year` | Khóa tuyển sinh 1980–2100, chỉ khớp bounds có bằng chứng |
| `as_of` | Ngày ISO YYYY-MM-DD; mốc bắt đầu/kết thúc có bằng chứng |

OR trong một list, AND giữa các field. Unknown nested field, mã sai định dạng, ngày
không hợp lệ/timestamp và cohort string bị từ chối 422. Audience tags không tự
inherit; `undergraduate` và `undergraduate_regular` là hai nhãn khác nhau.

Hai repository dùng cùng `METADATA_FILTER` và parameter builder trong SQL trước
ORDER BY/LIMIT/RRF. Response giữ `applied_filters`; source thêm legal_status/domain/
document_type/applies_to, cohort_scope/bounds và ngày hiệu lực chuẩn hóa. Cổng
companion full/ready/in-context vẫn áp dụng khi filter khiến companion vắng context.

```json
{
  "question": "Đăng ký PET02 cần đạt môn tiên quyết nào?",
  "retrieval_mode": "hybrid",
  "filters": {
    "domains": ["foreign_language"],
    "applies_to": ["undergraduate_regular"],
    "cohort_year": 2026,
    "as_of": "2026-10-08"
  }
}
```

## Metadata có bằng chứng

Migration thêm typed columns và trigger insert/update metadata/backfill:

- Ngày phải đúng ISO và có effective_evidence; ngày sai hoặc chỉ ghi học kỳ/năm học
  để null. Issued year/title không được dùng để suy ngày hiệu lực.
- effective_to có giá trị nhưng thiếu evidence/ngày hợp lệ khiến as_of loại nguồn.
  End date rõ là ngày cuối inclusive. Không ghi end date chỉ là chưa ghi nhận mốc
  kết thúc, không chứng minh văn bản vẫn hiện hành.
- Cohort cần bounds và evidence rõ; range thiếu/sai/đảo chiều là unknown. Khi caller
  yêu cầu cohort_year, unknown bị loại, không gán cho mọi khóa.
- `cohort_scopes.csv` bind document ID/source SHA-256; review stale không gán bounds.
  956 Điều1 khoản3 PDF2 ghi bắt buộc từ khóa2026, đào tạo từ2026-2027.

| Nguồn ready | Domain | Ngày bắt đầu chuẩn hóa | Cohort bounds | Legal status |
|---|---|---|---|---|
| 1393 | academic_training | 2023-12-29 | unknown | unknown |
| 159 | graduation_thesis | 2024-03-05 | unknown | unknown |
| 790 | academic_training | null: học kỳ1 năm2022-2023 | unknown | unknown |
| 956 | foreign_language | 2026-08-10 | từ2026 | unknown |

`as_of` là interval nguồn đã ghi nhận, không chứng nhận hiệu lực pháp lý tại ngày
yêu cầu; API trả caveat và source unknown warning. Cohort unknown không đồng nghĩa
sinh viên không được áp dụng; đây là thiếu structured metadata để lọc chắc chắn.
Scope ở document level, chưa phân biệt program/clause trong cùng văn bản hay ngày
khác nhau ở từng điều/phụ lục.

Re-index sau config/filter version tạo4 run ingested, giữ97 unique chunks và hashes
của19 gold chunks. 11 failed/blocked không vào search;001–006 chạy lại đều skip.

## 30 câu development và evidence binding

`development_questions.csv`: 6 câu cập nhật1393, 14 KLTN159, 10 ngoại ngữ956; có
question/reference answer, filters, paraphrase group, chunk IDs và locator PDF/điều/
khoản. D01/D03/D04/D07 nối với OCR01/OCR02/OCR03/C03. Tất cả split development,
nhóm duration/prerequisite cùng split; chưa có held-out test.

Đáp án do assistant biên soạn sau đọc source chunk đã duyệt, chưa có reviewer người
độc lập. Đây là reference set ban đầu, không dùng output Qwen backend làm reference.
`development_manual_review.csv` ghi30 đối chiếu reference/source và scoped hybrid ranks.

`development_evidence.json` bind19 unique chunks với source/content hashes, source URL,
PDF pages, article/clauses/extraction/quality. Dataset canonical SHA-256:
`7a2bb4801dac8c1d78e13aeac527dbc44b76583d0d5cb16cd40573445f1bfe0d`.
Canonical records tránh false drift LF/CRLF; đổi question/answer/filter hoặc evidence/
source/page làm evaluation dừng để review lại. Binding script chỉ kiểm publication/
hash, không tự chứng minh semantic answer support.

Không dùng pending/excluded evidence. D22/D23 chỉ ghi khoản5(a)/(b) PDF4 vì article
metadata sau excluded page là null; không tự điền article4. D06 cần header ngày ký
và Điều2 hiệu lực từ ngày ký; các câu khác một chunk. Multi-clause chunks vẫn cần
chọn đúng clause khi trả lời.

## Evaluation 30 câu × 3 mode × 2 conditions

Run kết thúc `2026-10-08T14:17:22.053198+00:00`. Cùng97 chunks/model pins/E5
fingerprint và top5/candidate20/RRF60/weights1:1. Encode30 query vectors dùng lại.
Scoped condition dùng filters ghi trong từng câu: context caller cung cấp, không
phải NLP tự suy scope từ question.

| Condition / mode | Gold hit@1 | Hit@2 | Hit@5 | Đủ evidence@2 | Đủ evidence@5 |
|---|---:|---:|---:|---:|---:|
| Unfiltered vector | 20/30 | 24/30 | 27/30 | 24/30 | 26/30 |
| Unfiltered keyword | 8/30 | 10/30 | 19/30 | 9/30 | 19/30 |
| Unfiltered hybrid | 11/30 | 18/30 | 26/30 | 18/30 | 26/30 |
| Scoped vector | 27/30 | 30/30 | 30/30 | 29/30 | 30/30 |
| Scoped keyword | 14/30 | 22/30 | 27/30 | 21/30 | 27/30 |
| Scoped hybrid | 18/30 | 28/30 | 30/30 | 28/30 | 30/30 |

Hit là có ít nhất một bound gold chunk; đủ evidence cần tất cả IDs (D06 có2).
Scope violations0; unfiltered không có restriction để kiểm. Đây là gold-chunk
retrieval trước token budget, không đo quote relevance/answer accuracy/held-out
generalization hay latency benchmark. Run không gọi LLM, query cache/cold-start khác nhau.

Manual review scoped hybrid:

- 18 gold ởtop1,10 ởtop2,D30 top3,D15 top5. D06 đủ cả2 trongtop2.
- D07/C03-related duration15 tuần hồi phục vào top2 khi lọc KLTN; top1 là workflow
  nộp báo cáo. D15 CBPB/CBHD quan hệ ruột thịt và D30 Việt-Nhật JAN02/N5 vắng context2.
- D13 top1 cũng nói điểm0 nhưng do nộp báo cáo không đạt; gold đình chỉ giữa kỳ là
  chunk khác. Trùng con số không chứng minh đúng điều kiện.
- Filter cải thiện scope/document recall nhưng không sửa hết thứ hạng clause.
  Vector+filter top1 tốt hơn hybrid+filter trên run (27 so18); T2.3 document hit22/23
  không chứng minh hybrid mạnh hơn ở gold evidence. Chưa tune weights/reranker.

## Kiểm chứng và hiện trạng M2

- 149 tests pass:66 unit/83 PostgreSQL integration schema riêng.
- Ba modes kiểm42 cases ID/domain/type/audience/cohort/date/AND/OR; thêm date end/
  evidence/invalid metadata và real DB/API filter/provenance3 modes.
- Invalid inputs bị API từ chối; source unknown không tự thành current. Cohort
  review source-hash gate; old evidence hash/page drift bị chặn.
- Lifecycle/idempotency/update/delete/quality tests vẫn pass. DB4 ready/11 failed-
  blocked/97 unique chunks. Ruff check/format, pip check/lock70/70 pass.
- Warning TestClient/httpx deprecated như các task trước; native OCR dependency nhưT2.2.

M2 chưa nghiệm thu toàn corpus:10 scan khác và43 cần page/table review;121 trang
pending,23 excluded. T3.1 reranker phụ thuộc M2; ưu tiên publication/review backlog.
Lỗi generation relevance/JSON trong API smoke T2.3 còn được theo dõi.

## Tái lập

Trong `ragschool`, từ root, với source/review/correction đã chuẩn bị:

```powershell
python scripts/migrate.py
python scripts/index_baseline.py
python scripts/export_development_evidence.py
# Chỉ bind lại sau review khi reference/evidence đổi.
python scripts/build_development_evidence.py
python scripts/evaluate_development.py
$env:REGULARAG_RUN_DB_TESTS = "1"
python -m pytest
```

Thông thường giữ binding và evaluate trực tiếp để phát hiện drift; không rebind
im lặng để vượt stale gate. Public: question/reference/pointer/hash và CSV180 results.
Full excerpts/hits ở ignored `data/processed/development-evidence/` và
`development-retrieval/`. Dùng `--output-dir`/`--summary` mới để giữ các run riêng.
