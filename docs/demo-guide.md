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
& "C:\Users\Khanh\miniconda3\Scripts\conda.exe" run --no-capture-output -n ragschool python -m uvicorn regularag.main:app --host 127.0.0.1 --port 8000
```

Giữ terminal này mở, truy cập URL demo. Máy hiện tại đã có model cache, migrations,
corpus15/307 và source review. Offline flags ở trên sử dụng cache đã có; trên máy mới
phải làm setup/tải model/index theo `docs/development.md` trước.
`Ctrl+C` trong terminal để dừng server. Không dùng thêm `--workers` trên máy RAM nhỏ;
model requests được serialize trong service.

Badge góc trên kiểm API/database, **không chứng minh model đã được tải**. Bấm badge
để kiểm lại. Model local CPU được tải khi có request; lần đầu có thể30–90giây tuỳ máy.

## 2. Test nhanh các trạng thái

Chọn mẫu ở “Thử một tình huống”, rồi bấm **Tra cứu bằng chứng**. Mẫu điền dữ liệu,
không tự gửi. Có thể gửi bằng `Ctrl+Enter` trong ô câu hỏi.

| Mẫu | Cách thử | Kết quả mong đợi |
|---|---|---|
| **Tín chỉ học kỳ hè** | Chọn mẫu, gửi | `answered`, cap12tín chỉ từ1393, cùng điều kiện học hè |
| **Chuẩn ngoại ngữ của em** | Chọn mẫu, để scope trống, gửi | `needs_clarification`: hỏi khóa/hệ/chương trình |
| **Ngày hiệu lực quy định** | Chọn mẫu, gửi | 851 có mốc nguồn01/9/2024, phân biệt ngày ban hành14/8 |
| **Bộ lọc chỉ cho văn bản cũ** | Chọn mẫu, giữ lựa chọn790, gửi | `insufficient_evidence`/`latest_excluded_by_filters`, không dùng ngưỡng50cũ |

Để thử trả lời clarification:

1. Sau mẫu ngoại ngữ, bấm **Bổ sung thông tin áp dụng**.
2. Điền khóa **2026**, hệ **Đại học chính quy**, programme **CTA**.
3. Giữ nguyên câu hỏi gốc, gửi lại.
4. Đối chiếu source956: CTA sau3học kỳ cầnIEL05, chưa đạt cap16tín chỉ ngoài ngoại ngữ,
   kể cả học lại/cải thiện cho đến khi đạt. Block nguồn còn giữ các mốc2/4kỳ cùng programme.

Mỗi request độc lập; UI không tự thêm nội dung câu hỏi trước hoặc rewrite query.

## 3. Kiểm tra citation và nguồn

- Bấm **[S1]** trong đáp án: mở đúng source card và chuyển focus đến nguồn.
- Đọc phần **Đoạn đã dùng trong câu trả lời**. Đây là actual cited passages từ backend.
- **Xem toàn bộ chunk đã truy xuất** hiển thị approved chunk để đọc context/ngoại lệ.
- **Mở tài liệu nguồn** mở URL source từ API trong tab mới. Số trangPDF có thể là
  phạm vi chunk, không nhất thiết là trang chính xác của từng dòng.
- **Phiên bản & provenance** có ngày ban hành, latest family, ngày kiểm source,
  chunkID, offsets/hash và rawscore. Những scores này không phải confidence phần trăm.
- Nguồn không cited được ghi “Nguồn trong context”, không trình bày như bằng chứng
  đã dùng để kết luận. Warnings/partial coverage và legal-status-unknown đọc ở ghi chú.

“Mới nhất” là verified chain/corpus/request scope; không tự xác nhận pháp lý hiện hành.
Không suy khóa hoặc ngày áp dụng chỉ từ năm ban hành.

## 4. Thử phạm vi và bộ lọc

**Thông tin áp dụng**: khóa, hệ, programme, ngàyđối chiếu, thời gianthiết kế và loạiđồán.
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

## 6. Khi request lâu hoặc có lỗi

- Loading có elapsed time, không có phần trăm hoặc stage giả.
- **Dừng chờ** dừng fetch của trình duyệt. Python backend có thể vẫn xử lý; request
  sau sẽ chờ inference lock. UI giữ câu hỏi và không dùng response cũ làm đáp án mới.
- Lỗi503: kiểm Docker/db/model/cache trong terminal. Lỗi422: đọc thông báo field
  và sửa dữ liệu. Lỗi mạng: kiểm Uvicorn/cổng rồi gửi lại; dữ liệu nhập vẫn được giữ.
- Nếu8000 đang được app khác dùng, chọn cổng khác, ví dụ8001, và mở URL tương ứng.
- Dùng browser desktop DevTools resize để thử375px/landscape; UI có responsive layout.

Các mẫu này là **development**, không dùng40câu held-out để thử/tune trước khi chốt
cấu hình đánh giá. T4.2 runner vẫn là bước tiếp theo.
