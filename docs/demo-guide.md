# Chạy và test web demo RegulaRAG

Giao diện đã có tại **http://127.0.0.1:8000/** khi Uvicorn đang chạy.
UI và API dùng cùng server; không cần chạy npm/build/frontend server.
API explorer vẫn ở **http://127.0.0.1:8000/docs**.

## 1. Khởi động local trên máy hiện tại

Mở Docker Desktop, chờ engine chạy. Mở PowerShell tại thư mục
`C:\Users\Khanh\Desktop\RAGAskingRUle`, rồi:

```powershell
docker compose up -d --wait
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:REGULARAG_RAG_CONFIG_PATH = "configs/rag/final.json"
$env:REGULARAG_LOG_LEVEL = "INFO"
$env:REGULARAG_PIPELINE_TRACING_ENABLED = "true"
& "C:\Users\Khanh\miniconda3\Scripts\conda.exe" run --no-capture-output -n ragschool python -m uvicorn regularag.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Giữ terminal này mở, truy cập URL demo. Máy hiện tại đã có model cache, migrations,
corpus15/307 và source review. Offline flags ở trên sử dụng cache đã có; trên máy mới
phải làm setup/tải model/index theo `docs/development.md` trước.
`Ctrl+C` trong terminal để dừng server. Không dùng thêm `--workers` trên máy RAM nhỏ;
model requests được serialize trong service.
Sau khi đổi code hoặc config, dừng/khởi động lại Uvicorn rồi refresh trang demo.

Badge góc trên kiểm API/database, **không chứng minh model đã được tải**. Bấm badge
để kiểm lại. Model local CPU được tải khi có request; lần đầu có thể30–90giây tuỳ máy.

## 2. Test nhanh các trạng thái

Chọn mẫu ở “Thử một tình huống”, rồi bấm **Tra cứu bằng chứng**. Mẫu điền dữ liệu,
không tự gửi. Có thể gửi bằng `Ctrl+Enter` trong ô câu hỏi.

| Mẫu | Cách thử | Kết quả mong đợi |
|---|---|---|
| **Tín chỉ học kỳ hè** | Chọn mẫu, gửi | `answered`, cap12tín chỉ từ1393, cùng điều kiện học hè |
| **Chuẩn ngoại ngữ của em** | Chọn mẫu, để scope trống, gửi | `needs_clarification`: hỏi khóa/hệ/chương trình/mốc học kỳ |
| **Ngày hiệu lực quy định** | Chọn mẫu, gửi | 851 có mốc nguồn01/9/2024, phân biệt ngày ban hành14/8 |
| **Bộ lọc chỉ cho văn bản cũ** | Chọn mẫu, giữ lựa chọn790, gửi | `insufficient_evidence`/`latest_excluded_by_filters`, không dùng ngưỡng50cũ |

Để thử trả lời clarification:

1. Sau mẫu ngoại ngữ, bấm **Bổ sung thông tin áp dụng**.
2. Điền khóa **2026**, hệ **Đại học chính quy**, programme **CTA**,
   **Học kỳ chính đã hoàn thành =3**.
3. Giữ nguyên câu hỏi gốc, gửi lại.
4. Đối chiếu source956: CTA sau3học kỳ cầnIEL05, chưa đạt cap16tín chỉ ngoài ngoại ngữ,
   kể cả học lại/cải thiện cho đến khi đạt. Block nguồn còn giữ các mốc2/4kỳ cùng programme.

Mỗi request độc lập; UI không tự thêm nội dung câu hỏi trước hoặc rewrite query.

### Thử GPA và nguồn cũ không bị sửa đổi

Điền câu:

> Nếu điểm trung bình đến hiện tại của tôi >=8.0, tôi sẽ được phép đăng kí bao nhiêu tín chỉ?

1. Để chủ đề **Tất cả** và chưa chọn giới hạn document nếu muốn thử default query;
   kiểm lại các bộ lọc còn giữ từ mẫu vừa chọn.
2. Mong đợi `answered`: **học kỳ chính**, ĐTBC≥8,0 đến thời điểm đăng ký được phép
   tối đa **30tín chỉ**, từ790 Điều14 khoản1(a), PDF12–13. Normal rule14–24 và các
   điều kiện/ngoại lệ vẫn có trong đoạn trích.
3. Chọn chỉ790 và gửi cùng câu: khoản1(a) không bị1393 sửa nên vẫn có bằng chứng30.
4. Đổi sang **học kỳ hè**, giữ790-only: phải thiếu bằng chứng cập nhật1393. Bỏ giới
   hạn790-only thì trả quy định hè12tín chỉ cùng điều kiện mới từ1393.

ĐTBC dùng đăng ký tín chỉ khác ĐTBCTL; xem790 Điều24 khi cần đối chiếu định nghĩa.
Nếu đã chọn chủ đề Đào tạo tín chỉ cho câu cá nhân, backend có thể hỏi **hệ đào tạo**;
bổ sung hệ đúng của bạn qua phần scope và giữ câu hỏi gốc. Browser QA đã kiểm cả flow
hỏi lại rồi trả lời với explicit Đại học chính quy.

## 3. Kiểm tra citation và nguồn

- Bấm **[S1]** trong đáp án: mở đúng source card và chuyển focus đến nguồn.
- Đọc phần **Đoạn đã dùng trong câu trả lời**. Đây là actual cited passages từ backend.
- **Xem toàn bộ chunk đã truy xuất** hiển thị approved chunk để đọc context/ngoại lệ.
- **Mở tài liệu nguồn** mở URL source từ API trong tab mới. Số trangPDF có thể là
  phạm vi chunk, không nhất thiết là trang chính xác của từng dòng.
- **Phiên bản & provenance** có ngày ban hành, latest family, ngày kiểm source,
  chunkID, offsets/hash và rawscore. Những scores này không phải confidence phần trăm.
- Với view khoản không bị sửa đổi, **Phạm vi bằng chứng không bị sửa đổi** ghi Unicode
  offsets trên chunk gốc; actual cited passages nằm trong phạm vi đó.
- Nguồn không cited được ghi “Nguồn trong context”, không trình bày như bằng chứng
  đã dùng để kết luận. Warnings/partial coverage và legal-status-unknown đọc ở ghi chú.

“Mới nhất” là verified chain/corpus/request scope; không tự xác nhận pháp lý hiện hành.
Không suy khóa hoặc ngày áp dụng chỉ từ năm ban hành.
Văn bản ban hành lâu vẫn được dùng cho điều/khoản đã kiểm chứng không bị sửa đổi;
latest family1393 không có nghĩa mọi nội dung790 đều phải thay bằng1393.

## 4. Thử phạm vi và bộ lọc

**Thông tin áp dụng**: khóa, hệ, programme, học kỳ chính đã hoàn thành (integer0–40),
ngàyđối chiếu, thời gianthiết kế và loạiđồán. Không suy mốc học kỳ từ năm nhập học.
Để trống nếu chưa biết; không tự điền ngày hôm nay để “được dữ liệu mới nhất”.

**Giới hạn nguồn & truy xuất**:

- Chọn một/nhiều documentIDs để giới hạn nguồn. Không chọn là toàn allowlist của backend.
- Chọn chủ đề nếu muốn áp exact domainfilter.
- Top-k1–20; modehybrid/vector/keyword. Reranker vẫn theo cấu hình backend.
- Trong **Chi tiết request & response**, so `request`, `requested_filters`,
  `applied_filters`, `resolved_scope` để xem dữ liệu tường minh/derived scopes.
- Nếu scope khác khóa nêu trong câu hỏi, backend phải hỏi lại; UI không sửa ngầm để đạt đáp án.

Chọn một mẫu khác sẽ nạp câu hỏi/scope/filter của mẫu đó và xoá scope/filter mẫu trước.
Nếu danh mục lỗi, mẫu có documentfilter sẽ không được áp thiếu lọc một cách im lặng.

## 5. Ghi nhận kết quả

Bấm **Hữu ích** hoặc **Cần xem lại** rồi **Tải JSON** để lưu request/response/elapsed
time và feedback. Góp ý chỉ giữ trong phiên tab, chưa gửi lên backend hoặc lưu vào DB.
Refresh sẽ mất trạng thái của phiên. JSON export có cả source text để bạn đối chiếu;
giữ local, không thêm raw/model outputs vào Git.

Nếu muốn báo một ca lỗi, gửi câu hỏi, scope/filter, status/failure_reason và SourceID/
chunkID kèm đoạn cần đối chiếu. Một câu trích đúng nguyên văn vẫn có thể sai chủ đề hoặc
thiếu điều kiện; việc bạn review semantic support rất hữu ích.
ResponseJSON/JSONexport có **`request_id`**; HTTPheaders có **`X-Request-ID`** kể cả422/503/500.
Gửi ID đó đểoperator tìmmetadata trace/rerankorder/context/selectedPIDs/stagechậm tronglocalJSONlogs:

```powershell
python scripts/inspect_trace.py --log <operator-json-lines-log> --request-id <UUID>
```

Không cần logfullquestion/source/modeltext đểcorrelate. Tracekhôngtựxácnhận semanticcorrectness;
`docs/observability-review.md` cóhướng dẫn vàgiớihạn. Clientdừngchờ thìbackendtrace vẫncóthểhoàn tất.

## 6. Khi request lâu hoặc có lỗi

- Loading có elapsed time, không có phần trăm hoặc stage giả.
- **Dừng chờ** dừng fetch của trình duyệt. Python backend có thể vẫn xử lý; request
  sau sẽ chờ inference lock. UI giữ câu hỏi và không dùng response cũ làm đáp án mới.
- Lỗi503: kiểm Docker/db/model/cache trong terminal. Lỗi422: đọc thông báo field
  và sửa dữ liệu. Lỗi mạng: kiểm Uvicorn/cổng rồi gửi lại; dữ liệu nhập vẫn được giữ.
- Nếu8000 đang được app khác dùng, chọn cổng khác, ví dụ8001, và mở URL tương ứng.
- Dùng browser desktop DevTools resize để thử375px/landscape; UI có responsive layout.

Các mẫu này là **development**. T4.4 đãfreeze `configs/rag/final.json` và chạy một lượt40test;
source/citationfidelity40/40 nhưng đúng/đủý19/28 vàtaskcitation29/108, đúngtừchối0/7.
Đây là localdemo/evaluation snapshot, chất lượng tổng quát chưađạt. Đọc đầyđủ kếtquả/lỗi
tại `docs/error-analysis-review.md`; không dùng tuneddevelopment47/47 làmheldoutaccuracy.
API không cóenvconfigoverride vẫn đọc baselinev2JSON; lệnh ở trên explicitlyloadfinalv3.
