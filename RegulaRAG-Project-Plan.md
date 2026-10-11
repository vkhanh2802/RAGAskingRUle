# RegulaRAG — Prompt hướng dẫn AI và kế hoạch triển khai

> Mục tiêu: xây dựng project RAG tiếng Việt đủ chất lượng để đưa vào portfolio ứng tuyển AI Engineer Intern.
> Thời gian dự kiến: 5 tuần, khoảng 90–120 giờ. Nếu học 10 giờ/tuần, triển khai trong khoảng 9–12 tuần.

## Cách sử dụng tài liệu

1. Mở repository project trong công cụ AI coding của bạn.
2. Đính kèm file này hoặc yêu cầu AI đọc toàn bộ file theo đường dẫn.
3. Sao chép prompt bên dưới vào cuộc hội thoại với AI.
4. Điền thông tin môi trường nếu đã biết. Nếu chưa biết, để AI kiểm tra hoặc hỏi.
5. Bắt đầu từ T1.1; sau mỗi phiên, yêu cầu AI cập nhật tiến độ và bàn giao.

---

## PROMPT KHỞI ĐỘNG — Sao chép phần trong khối dưới đây

```text
Bạn là Senior AI Engineer kiêm mentor kỹ thuật, hỗ trợ tôi xây dựng RegulaRAG để ứng tuyển AI Engineer Intern.

NGUỒN KẾ HOẠCH
- Đọc toàn bộ file RegulaRAG-Project-Plan.md trong workspace trước khi triển khai.
- Dùng các mã task, milestone và tiêu chí nghiệm thu trong file làm nguồn kế hoạch chính.
- Nếu hướng dẫn trong repository hoặc yêu cầu mới của tôi làm thay đổi kế hoạch, chỉ rõ điểm khác biệt và cập nhật kế hoạch sau khi thống nhất.

BỐI CẢNH CỦA TÔI
- Mức Python/backend hiện tại: [điền nếu biết].
- Thời gian mỗi tuần: [điền nếu biết].
- Máy: [hệ điều hành, RAM, CPU/GPU nếu biết].
- Ngân sách API/hosting: [điền nếu biết].
- Trường và tài liệu muốn sử dụng: [điền nếu biết].
- Mốc cần có portfolio: [điền nếu biết].

MỤC TIÊU
Xây dựng trợ lý tra cứu quy chế của một trường đại học bằng tiếng Việt, có ingestion PDF, retrieval, citation kiểm tra được, cơ chế xử lý thiếu bằng chứng, evaluation và demo triển khai được. Tôi cần hiểu và giải thích được các quyết định kỹ thuật, không chỉ có code chạy.

CÁCH LÀM VIỆC
1. Kiểm tra cấu trúc repository, hướng dẫn dự án, môi trường và code hiện có trước khi sửa. Không ghi đè công việc có sẵn nếu chưa hiểu mục đích.
2. Nếu thiếu thông tin ảnh hưởng trực tiếp đến task hiện tại, hỏi tối đa 3 câu quan trọng mỗi lượt. Những việc độc lập vẫn tiếp tục được. Với quyết định nhỏ, nêu giả định hợp lý và triển khai.
3. Chia công việc thành các task nhỏ theo mã trong kế hoạch. Mỗi lần tập trung một task hoặc một nhóm task có phụ thuộc trực tiếp; không tự nhảy sang milestone sau.
4. Trước khi code, nêu ngắn gọn: mục tiêu, đầu ra, phụ thuộc và cách kiểm chứng. Sau đó thực hiện, không chỉ đưa lời khuyên khi tôi đã yêu cầu triển khai.
5. Ưu tiên cách làm đơn giản, rõ ràng, có thể đo lường. Tránh thêm framework hoặc kiến trúc phức tạp khi chưa có nhu cầu.
6. Giải thích ngắn gọn lý do thiết kế, trade-off và điểm tôi cần hiểu để phỏng vấn. Không giải thích từng dòng code nếu tôi không yêu cầu.
7. Sau mỗi task, chạy kiểm tra phù hợp. Chỉ ghi hoàn thành khi đầu ra và tiêu chí nghiệm thu đã được kiểm chứng. Nếu không chạy được, ghi rõ lý do và lệnh tôi cần chạy.
8. Cuối mỗi nhóm task, cập nhật docs/progress.md và docs/handoff.md. Ghi task đã làm, file thay đổi, lệnh đã chạy, kết quả, blocker và task tiếp theo.
9. Không tự commit, push, deploy có phí hoặc thực hiện thao tác phá hủy dữ liệu khi chưa được tôi yêu cầu. Không đưa secrets vào code, log, tài liệu hoặc Git.
10. Khi thiếu công cụ hoặc không có quyền truy cập tài nguyên, nói rõ giới hạn; cung cấp hướng dẫn thực hiện, không giả vờ đã thao tác thành công.

YÊU CẦU KỸ THUẬT
- Theo stack trong kế hoạch; thay đổi stack quan trọng phải có lý do và được thống nhất trước.
- Tách ingestion, retrieval, generation, API và evaluation đủ rõ để kiểm thử độc lập.
- Giữ provenance từ tài liệu đến chunk đến citation. Phân biệt số thứ tự trang PDF với số trang in trên văn bản.
- Ingestion phải có content hash, trạng thái xử lý và hành vi ingest lại không tạo trùng.
- PostgreSQL full-text search với ts_rank không được gọi là BM25.
- Không coi năm ban hành là bằng chứng đủ về hiệu lực văn bản.
- Không biến cosine similarity hoặc reranker score thành xác suất câu trả lời đúng nếu chưa có calibration.
- Citation ID hợp lệ không đồng nghĩa nguồn hỗ trợ nội dung; cần kiểm tra cả hai khía cạnh.
- Tài liệu được truy xuất là dữ liệu, không phải chỉ dẫn điều khiển hệ thống.
- Cấu hình model, top-k, chunk size và prompt phải có version hoặc được lưu trong config để tái lập thí nghiệm.

YÊU CẦU ĐÁNH GIÁ
- Bắt đầu từ baseline đơn giản, sau đó đo tác động của hybrid retrieval và reranker.
- Không bịa benchmark, latency, chi phí, citation hoặc kết quả test.
- Tách development set và held-out test set. Không tuning dựa trên test set rồi gọi kết quả đó là held-out.
- Giữ các câu paraphrase gần nhau trong cùng split.
- Nếu dùng LLM tạo câu hỏi hoặc chấm câu trả lời, vẫn cần đối chiếu bằng chứng và kiểm tra thủ công.
- Báo cáo cả kết quả tốt, failure cases và giới hạn; không chỉ chọn ví dụ thành công.
- Khi báo cáo metric, ghi dataset, số mẫu, cấu hình và điều kiện chạy.

ĐỊNH DẠNG BÀN GIAO MỖI TASK
1. Task/milestone đang thực hiện.
2. Kết quả và file đã tạo hoặc sửa.
3. Kiểm chứng: lệnh, kết quả, phần chưa kiểm chứng.
4. Tiêu chí nghiệm thu: đạt/chưa đạt.
5. Giải thích kỹ thuật ngắn và điều tôi cần nắm.
6. Blocker nếu có và bước tiếp theo.

BẮT ĐẦU NGAY
Đọc kế hoạch và kiểm tra repository. Tóm tắt hiện trạng, chỉ ra thông tin còn thiếu và bắt đầu T1.1. Nếu repository đã có tiến độ, xác minh docs/progress.md và code trước khi tiếp tục từ task chưa hoàn thành gần nhất. Không tạo lại những phần đã chạy đúng.
```

### Prompt tiếp tục ở một phiên mới

```text
Đọc RegulaRAG-Project-Plan.md, docs/progress.md và docs/handoff.md nếu có. Kiểm tra code hiện tại để xác minh tiến độ, không chỉ dựa vào ghi chú. Tiếp tục task chưa hoàn thành gần nhất theo kế hoạch. Nêu ngắn gọn hiện trạng, mục tiêu phiên này và bắt tay triển khai. Kết thúc bằng kết quả kiểm chứng và cập nhật bàn giao.
```

### Prompt kiểm tra trước khi chuyển milestone

```text
Đối chiếu milestone hiện tại với các tiêu chí nghiệm thu trong RegulaRAG-Project-Plan.md. Kiểm tra artifact, code và kết quả chạy thực tế. Lập bảng đạt/chưa đạt kèm bằng chứng. Ưu tiên sửa các lỗi ảnh hưởng tính đúng đắn, dữ liệu và khả năng tái lập. Không đánh dấu milestone hoàn thành nếu còn tiêu chí bắt buộc chưa được kiểm chứng.
```

---

# PHẦN I — PHẠM VI VÀ THIẾT KẾ

## 1. Mục tiêu sản phẩm

RegulaRAG là trợ lý tra cứu quy chế đại học bằng tiếng Việt. Sinh viên đặt câu hỏi, hệ thống tìm bằng chứng trong tài liệu chính thức, trả lời và trích dẫn đúng nguồn.

### Nhóm câu hỏi hỗ trợ

1. Đăng ký học phần, học lại, cải thiện điểm.
2. Cảnh báo học tập và buộc thôi học.
3. Điều kiện xét tốt nghiệp.
4. Bảo lưu, nghỉ học tạm thời.
5. Học phí, học bổng nếu có tài liệu phù hợp.

Ví dụ: “Theo quy chế năm 2025, sinh viên bị cảnh báo học tập trong những trường hợp nào?”

### Một câu trả lời tốt phải

- Giữ đúng điều kiện, ngưỡng, ngoại lệ trong tài liệu.
- Áp dụng đúng đối tượng, thời gian và phạm vi.
- Có nguồn, trang và đoạn trích để đối chiếu.
- Không tự thêm thông tin ngoài bằng chứng.
- Hỏi lại hoặc từ chối khi thiếu căn cứ.

## 2. Phạm vi phiên bản đầu

| Hạng mục | Phạm vi |
|---|---|
| Trường | 1 trường đại học |
| Corpus | Khoảng 10–20 tài liệu chính thức, 150–400 trang |
| Định dạng | PDF có text; một nhóm PDF scan để thử OCR |
| Ngôn ngữ | Tiếng Việt |
| Giao diện | Hỏi đáp, lọc phạm vi và xem nguồn |
| Hội thoại | Câu hỏi độc lập trước, nhiều lượt sau |
| Ingestion | CLI/script; chưa cần dashboard admin |
| Tài khoản | Chưa cần đăng nhập |
| Dữ liệu | Tài liệu công khai, không có dữ liệu cá nhân |

### Dời sang phiên bản sau

- Multi-university.
- Dashboard quản trị đầy đủ.
- Phân quyền nhiều người dùng.
- Tự động phân giải mọi mâu thuẫn giữa văn bản.
- OCR diện rộng hoặc hỗ trợ nhiều định dạng phức tạp.

## 3. Tech stack

| Thành phần | Lựa chọn |
|---|---|
| Backend | Python, FastAPI, Pydantic |
| Database | PostgreSQL + pgvector |
| Parsing | PyMuPDF |
| OCR | PaddleOCR khi cần |
| Embedding | BAAI/bge-m3, dùng dense embedding trong MVP |
| Keyword search | PostgreSQL full-text search |
| Fusion | Reciprocal Rank Fusion — RRF |
| Reranker | BAAI/bge-reranker-v2-m3 hoặc model nhẹ hơn sau khi đo phần cứng |
| LLM | Một API provider trong MVP |
| Frontend | Streamlit |
| Evaluation | Python scripts và kiểm tra thủ công |
| Observability | Structured logs; Langfuse sau baseline |
| Testing | pytest |
| Packaging | Docker Compose |
| CI | GitHub Actions |

Lưu ý: PostgreSQL FTS với `ts_rank` không phải BM25. Chất lượng tiếng Việt phải được đo thực tế, đặc biệt với dấu, tokenization và mã văn bản.

## 4. Kiến trúc

```text
Tài liệu chính thức + source manifest
                |
                v
Parsing / OCR -> Cleaning -> Chunking + Metadata
                |
                v
PostgreSQL: documents / chunks / ingestion_runs
      |                               |
      v                               v
Full-text index                 pgvector embeddings
      |                               |
      +-----------> RRF <-------------+
                     |
                     v
                  Reranker
                     |
                     v
        Context builder + token budget
                     |
                     v
         LLM -> Citation validation
                     |
                     v
           FastAPI -> Streamlit

Evaluation và tracing quan sát toàn bộ pipeline.
```

Metadata cần phân biệt ngày ban hành, ngày hiệu lực và đối tượng áp dụng. Các giá trị không có bằng chứng phải để trống hoặc đánh dấu chưa xác định.

## 5. Milestone và thời lượng

| Mốc | Thời điểm | Đầu ra bắt buộc |
|---|---|---|
| M0 — Scope & data ready | Cuối ngày 2 | Phạm vi, manifest, kiến trúc, 10 câu hỏi mẫu |
| M1 — Baseline end-to-end | Cuối tuần 1 | PDF → index → câu hỏi → câu trả lời có nguồn |
| M2 — Reliable ingestion & retrieval | Cuối tuần 2 | Ingestion lặp lại an toàn, metadata, hybrid search |
| M3 — Evidence-aware answers | Cuối tuần 3 | Reranking, citation validation, abstention |
| M4 — Measured quality | Cuối tuần 4 | Dataset, benchmark, error analysis |
| M5 — Portfolio release | Cuối tuần 5 | Demo, Docker, CI, README, video và CV |

Thời lượng từng tuần là ước lượng, không phải cam kết. Mốc chỉ hoàn thành khi có artifact và kiểm chứng.

---

# PHẦN II — TASK TRIỂN KHAI CHI TIẾT

## Tuần 1 — Dữ liệu và baseline xuyên suốt

**Mục tiêu:** pipeline đầu tiên chạy từ tài liệu đến câu trả lời có nguồn.
**Thời lượng:** khoảng 18–22 giờ.

### T1.1 — Project brief và phạm vi

**Ước lượng:** 2 giờ. **Phụ thuộc:** không.

- [ ] Viết mô tả bài toán một trang.
- [ ] Chốt người dùng và 3–5 nhóm câu hỏi.
- [ ] Xác định chức năng ngoài MVP.
- [ ] Viết 10 câu hỏi thực tế cần hỗ trợ.
- [ ] Ghi phần cứng, ngân sách API và thời gian học.
- [ ] Phác thảo kiến trúc ban đầu.

**Đầu ra:** `docs/project-brief.md`, `docs/architecture.md`.

**Nghiệm thu:** giải thích trong 60 giây ai sử dụng, dùng để làm gì, dữ liệu từ đâu và thế nào là trả lời tốt.

### T1.2 — Thu thập và kiểm kê tài liệu

**Ước lượng:** 3 giờ. **Phụ thuộc:** T1.1.

- [ ] Chọn trường có tài liệu công khai từ nguồn chính thức.
- [ ] Thu thập khoảng 10–20 tài liệu phù hợp.
- [ ] Ghi URL, ngày tải, tiêu đề, mã văn bản.
- [ ] Ghi ngày ban hành và hiệu lực nếu được nêu rõ.
- [ ] Ghi khóa học, hệ đào tạo, chương trình áp dụng.
- [ ] Phân loại PDF text, scan và trang có bảng.
- [ ] Ghi quan hệ sửa đổi/thay thế nếu có bằng chứng.
- [ ] Kiểm tra khả năng chia sẻ lại; khi không phù hợp, chỉ chia sẻ manifest/script tải.
- [ ] Gắn 10 câu hỏi mẫu với tài liệu chứa đáp án.

**Đầu ra:** `data/manifests/documents.csv`, `docs/data-sources.md`.

**Nghiệm thu M0:** ít nhất 10 tài liệu có nguồn truy xuất được; phạm vi rõ; không suy diễn hiệu lực từ năm ban hành.

### T1.3 — Repository và môi trường

**Ước lượng:** 3 giờ. **Phụ thuộc:** T1.1; có thể làm độc lập với thu thập dữ liệu.

- [ ] Khởi tạo cấu trúc package Python.
- [ ] Khai báo và khóa dependencies.
- [ ] Tạo `.env.example`, `.gitignore`.
- [ ] Tạo settings bằng Pydantic.
- [ ] Chạy PostgreSQL + pgvector trong Compose.
- [ ] Tạo FastAPI app và `/health`.
- [ ] Cấu hình logging, formatter, linter.
- [ ] Tạo `docs/progress.md` và `docs/handoff.md`.

**Nghiệm thu:** backend khởi động, kết nối database, health check hoạt động; secrets không có trong code/Git.

### T1.4 — Parsing và chunking baseline

**Ước lượng:** 4–5 giờ. **Phụ thuộc:** T1.2, T1.3.

- [ ] Đọc PDF theo trang bằng PyMuPDF.
- [ ] Giữ text thô để đối chiếu.
- [ ] Làm sạch khoảng trắng/ký tự lỗi phổ biến.
- [ ] Chia theo đoạn văn và giới hạn token.
- [ ] Bắt đầu với 500–800 token/chunk, overlap 80–120 token.
- [ ] Lưu document ID, chunk ID, thứ tự chunk, page start/end.
- [ ] Phân biệt số trang PDF và số trang in.
- [ ] Kiểm tra thủ công 20 chunk.

**Nghiệm thu:** parse ít nhất 3 tài liệu; các chunk kiểm tra đọc được và trỏ về đúng trang. Chunk size là cấu hình khởi đầu, chưa phải tối ưu.

### T1.5 — Vector retrieval và generation baseline

**Ước lượng:** 6–7 giờ. **Phụ thuộc:** T1.4.

- [ ] Tạo embedding theo batch.
- [ ] Lưu vector vào pgvector.
- [ ] Viết retriever top-k.
- [ ] Tạo prompt chỉ dùng bằng chứng trong context.
- [ ] Gắn source ID như `[S1]`, `[S2]` cho context.
- [ ] Tạo `POST /api/v1/ask`.
- [ ] Trả answer và nguồn để đối chiếu.
- [ ] Lưu baseline config và 10 kết quả mẫu.

**Nghiệm thu M1:** 10 câu hỏi chạy xuyên suốt; có thể truy vết nguồn; ghi cả ví dụ đúng và thất bại. Nguồn truy vết được chưa đồng nghĩa nội dung đã được chứng minh.

## Tuần 2 — Ingestion tin cậy và hybrid retrieval

**Mục tiêu:** dữ liệu có kiểm soát, retrieval kết hợp keyword/vector và filter đúng phạm vi.
**Thời lượng:** khoảng 18–24 giờ.

### T2.1 — Schema và ingestion lifecycle

**Ước lượng:** 4 giờ. **Phụ thuộc:** M1.

- [ ] Tạo migration cho `documents`, `chunks`, `ingestion_runs`.
- [ ] Lưu content hash và phiên bản pipeline/model.
- [ ] Theo dõi `pending`, `processing`, `ready`, `failed`.
- [ ] Viết CLI ingest file/thư mục.
- [ ] Ghi lỗi riêng từng tài liệu.
- [ ] Ingest lại không tạo bản ghi trùng.
- [ ] Hỗ trợ xóa tài liệu và chunk liên quan.
- [ ] Retrieval chỉ dùng dữ liệu `ready`.

**Nghiệm thu:** ingest hai lần không nhân đôi chunk; file hỏng không phá cả batch; xóa tài liệu thì không còn chunk trong search.

### T2.2 — Chunking cấu trúc và OCR có điều kiện

**Ước lượng:** 5–6 giờ. **Phụ thuộc:** T2.1.

- [ ] Nhận diện chương, điều, khoản.
- [ ] Giữ cùng điều/khoản khi vừa token budget.
- [ ] Lặp lại tiêu đề khi phải chia điều dài.
- [ ] Loại header/footer lặp bằng quy tắc có kiểm tra.
- [ ] Phát hiện trang thiếu text để chạy OCR.
- [ ] Ghi provenance OCR.
- [ ] Kiểm tra bảng, ngưỡng điểm và số liệu.
- [ ] Đánh dấu trang chất lượng thấp để rà soát.
- [ ] Kiểm tra ít nhất 30 chunk thuộc các loại nội dung khác nhau.

**Nghiệm thu:** evidence chuẩn giữ đúng số liệu và điều kiện; bảng/OCR chưa tin cậy được ghi giới hạn hoặc loại khỏi phạm vi hỗ trợ.

### T2.3 — Keyword search và RRF

**Ước lượng:** 5–6 giờ. **Phụ thuộc:** T2.1.

- [ ] Tạo full-text index và keyword retriever riêng.
- [ ] Thử truy vấn có dấu/không dấu, mã văn bản, số điều.
- [ ] Viết RRF kết hợp hai danh sách ranking.
- [ ] Loại chunk trùng.
- [ ] Trả provenance nhánh retrieval và rank.
- [ ] Lưu kết quả vector-only, keyword-only và hybrid trên cùng câu hỏi.

**Nghiệm thu:** chạy được ba cấu hình; chưa kết luận hybrid tốt hơn khi chưa có phép đo.

### T2.4 — Metadata filtering và development set ban đầu

**Ước lượng:** 4–6 giờ. **Phụ thuộc:** T2.2, T2.3.

- [ ] Filter theo tài liệu, loại quy định, đối tượng áp dụng.
- [ ] Hỗ trợ thời gian hiệu lực nếu metadata đủ rõ.
- [ ] Áp dụng cùng filter ở hai nhánh retrieval.
- [ ] Không tự coi văn bản chưa rõ hiệu lực là hiện hành.
- [ ] Viết 30 câu development có đáp án và evidence.
- [ ] Gán trang/chunk liên quan và đánh giá retrieval thủ công.

**Nghiệm thu M2:** toàn corpus đã ingest; hybrid và filter hoạt động; 30 câu development; có test ingest trùng, xóa tài liệu và filter.

## Tuần 3 — Reranking và câu trả lời dựa trên bằng chứng

**Mục tiêu:** trả lời có căn cứ và hành vi rõ khi thiếu dữ liệu.
**Thời lượng:** khoảng 18–24 giờ.

### T3.1 — Reranker

**Ước lượng:** 4–5 giờ. **Phụ thuộc:** M2.

- [x] Lấy khoảng 20–40 candidates từ hybrid.
- [x] Rerank cặp query–chunk.
- [x] Chọn khoảng 4–8 chunk vào context.
- [x] Giới hạn context bằng token budget.
- [x] Đo thời gian trên phần cứng thực tế.
- [x] Bật/tắt reranker qua config.

**Nghiệm thu:** so sánh được chất lượng và latency cùng dataset; nếu model quá nặng, giảm candidates/model và ghi trade-off.

**Hoàn tất 2026-10-09:**20 candidates/6 context tối đa4096 tokens, CPU pinned
reranker và verified freshness relations;187 tests. Scoped goldtop1 hybrid18/30
→29/30, stagep50 4,65s; generation còn chậm/abstain. Báo cáo và các failure cases:
`docs/reranker-freshness-review.md`. M3 chưa nghiệm thu; tiếp theoT3.2.

### T3.2 — Structured response và citation validation

**Ước lượng:** 5 giờ. **Phụ thuộc:** M2; tích hợp với T3.1 khi sẵn sàng.

- [x] Định nghĩa response schema.
- [x] Yêu cầu LLM chỉ dùng source ID đã cấp.
- [x] Backend xác thực source ID.
- [x] URL/trang/tiêu đề lấy từ database, không lấy từ phỏng đoán của LLM.
- [x] Trả excerpt để đối chiếu.
- [x] Retry giới hạn hoặc lỗi có kiểm soát khi output sai schema.
- [x] Test citation ID không tồn tại.
- [x] Kiểm tra thủ công nguồn có hỗ trợ phát biểu.

Ví dụ response:

```json
{
  "status": "answered",
  "answer": "Sinh viên được ... [S1]",
  "citations": [
    {
      "source_id": "S1",
      "document_id": "doc_001",
      "chunk_id": "chunk_042",
      "pdf_page": 8,
      "excerpt": "..."
    }
  ]
}
```

**Nghiệm thu:** citation trả ra tham chiếu nguồn thật; có kiểm tra cả tính hợp lệ và khả năng hỗ trợ nội dung.

**Hoàn tất2026-10-09:** request-scoped passageIDs/strictschema/offset-hash binding,
backend-derivedcitations vàboundedretry;210tests. Acceptance12 có11supported primaryanswers,
1correctstalefilterabstention, median13,57s; development30 vàtargetedregressions giữcảfailures.
`docs/passage-citation-review.md`; tiếp theoT3.3, M3 chưa nghiệm thu.

### T3.3 — Abstention và clarification

**Ước lượng:** 4–5 giờ. **Phụ thuộc:** T3.2.

- [x] Hỗ trợ `answered`, `insufficient_evidence`, `needs_clarification`.
- [x] Xử lý không có retrieval result.
- [x] Xử lý context có liên quan nhưng chưa đủ đáp án.
- [x] Hỏi lại khóa học, hệ đào tạo hoặc thời gian khi cần.
- [x] Trình bày khác biệt giữa nguồn nếu chưa xác định được hiệu lực.
- [x] Hiệu chỉnh quy tắc trên development set.

**Nghiệm thu:** có ví dụ trả lời được, thiếu bằng chứng, cần hỏi lại và khác biệt phiên bản. Không gắn confidence dạng phần trăm từ similarity score chưa calibration.

Hoàn tất 2026-10-10: `docs/clarification-abstention-review.md`; 20 tình huống
(8 hỏi lại / 7 abstention / 5 supported answers), positive12 và frozen development30
kèm targeted reruns; 247 tests. Khác biệt phiên bản trình bày metadata riêng,
không tự hợp nhất pháp lý. T3.4/M3 vẫn chưa nghiệm thu.

### T3.4 — Kiểm thử hành vi và hội thoại tùy chọn

**Ước lượng:** 4–5 giờ. **Phụ thuộc:** T3.3.

- [x] Test giả định sai trong câu hỏi.
- [x] Test yêu cầu bịa khi không biết.
- [x] Test chỉ dẫn giả trong tài liệu truy xuất.
- [x] Test câu hỏi ngoài phạm vi.
- [x] Ghi failure cases và sửa lỗi nghiêm trọng.
- [ ] Tùy chọn: query rewriting cho câu hỏi tiếp nối.
- [ ] Nếu rewrite: lưu query gốc/query mới và kiểm tra không thêm điều kiện không có.

**Nghiệm thu M3:** ít nhất 20 tình huống hành vi có pass/fail; không còn lỗi nghiêm trọng đã biết về citation giả hoặc bỏ qua filter.

**Hoàn tất T3.4/M3 2026-10-10:** 24 API adversarial cases +10 synthetic post-retrieval
cases có pass/fail (final34/34; pilot8+7failures được giữ), positive12 có11supported
answers/1correctabstention;276tests. Source hash/context instruction guards và
explicit outside-scope rules; filters/latest/gold bindings giữ nguyên.
`docs/adversarial-behaviour-review.md`. Hai mục rewriting tùy chọn không được chọn;
API vẫn câu hỏi độc lập +structured scope. M3 là technical gate trong supported scope,
chưa held-out accuracy; tiếp theoT4.1.

## Tuần 4 — Evaluation và bằng chứng chất lượng

**Mục tiêu:** đo được chất lượng, tái lập được kết quả và xác định được nhóm lỗi.
**Thời lượng:** khoảng 22–28 giờ; ưu tiên nhiều thời gian nhất cho tuần này.

### T4.1 — Hoàn thiện dataset đánh giá

**Ước lượng:** 8–10 giờ. **Phụ thuộc:** M3, 30 câu development từ T2.4.

| Nhóm câu hỏi | Số lượng mục tiêu |
|---|---:|
| Tra cứu một điều khoản | 30 |
| Kết hợp nhiều điều khoản | 20 |
| Có điều kiện thời gian/đối tượng | 15 |
| Ngoài phạm vi hoặc không có đáp án | 15 |
| Thiếu thông tin, cần hỏi lại | 10 |
| Giả định sai hoặc gây nhiễu | 10 |
| **Tổng** | **100** |

- [x] Mỗi mẫu có question, category, expected_status.
- [x] Với câu có đáp án: reference_answer, required_facts và evidence.
- [x] Evidence gồm tài liệu, trang, đoạn trích; không chỉ chunk ID.
- [x] Ghi filters và split.
- [x] Chia khoảng 60 development / 40 held-out test.
- [x] Giữ paraphrase gần nhau trong cùng split.
- [x] Kiểm tra thủ công toàn bộ evidence.
- [x] Freeze test set trước vòng tuning cuối.

**Nghiệm thu:** mọi mẫu có đáp án hoặc hành vi kỳ vọng rõ. LLM có thể hỗ trợ viết mẫu nhưng không thay thế kiểm tra bằng chứng.

**Hoàn tất2026-10-10:** `data/evaluation/v1/`,100cases đúng30/20/15/15/10/10,
60development/40prospectiveheld-out;75answeredgold/15insufficient/10clarification.
72curatedspans/49approvedchunks với source/pages/offsets/excerpts/hashes;
manualassistantsource/behaviourreview100cases, khôngindependenthumanreview.
98paraphrasegroups/68families khôngcrosssplit; frozenlegacy30/19giữnguyên.
Freeze `d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c`,
0held-outRAGinference trongconstruction;300tests vàsource/filter/hashgates đạt.
`docs/evaluation-dataset-review.md`; nextT4.2, M4benchmark cònpending.

### T4.2 — Evaluation runner

**Ước lượng:** 5–6 giờ. **Phụ thuộc:** T4.1.

#### Retrieval

- [x] Recall@5, Recall@10.
- [x] MRR@10.
- [ ] nDCG@10 nếu có nhãn mức độ liên quan.
- [x] Báo cáo theo nhóm câu hỏi; chỉ tính retrieval recall với câu có evidence phù hợp.

#### Answer quality

- [x] Correctness theo required facts.
- [x] Faithfulness: phát biểu có được context hỗ trợ.
- [x] Citation support precision.
- [x] Citation coverage: phát biểu cần nguồn đã có nguồn hỗ trợ.
- [x] Từ chối đúng trên câu không có đáp án.
- [x] Từ chối nhầm trên câu có đáp án.

#### Vận hành

- [x] Latency retrieval, reranker, LLM và end-to-end.
- [x] p50/p95 với số mẫu và điều kiện đo rõ ràng.
- [x] Input/output tokens và chi phí API trung bình.
- [x] Ghi riêng chi phí API và chi phí hosting/compute nếu có.

**Đầu ra mỗi run:**

```text
evals/results/<run_id>/
├── config.json
├── predictions.jsonl
├── retrieval_metrics.json
├── answer_metrics.json
└── summary.md
```

**Nghiệm thu:** một lệnh tạo được báo cáo. Nếu dùng LLM-as-judge, lưu model/prompt và đối chiếu một phần với chấm thủ công.

**Hoàn tất T4.2 2026-10-10:** `python scripts/run_evaluation.py` tạo config/predictions/
retrieval/answer/operationalmetrics/summary, defaultfrozen development60. 60actualmanualreviews
bindresponse/predictionsSHA, nomodeljudge. Rank10samepool/answerbudgetunchanged; nDCG N/A vì
không gradedlabels. Recall5=.98936/10=1/MRR10=.96454;41/47completeanswers,52/71task-support
citations;8/8correctreject,1/47false; p50/p95e2e13.270/18.282s,API0VND/computeunpriced.
339tests/12Node/Ruff đạt; giữ14issuecases vàfreeze/corpus/gold,0heldoutinference.
`docs/evaluation-runner-review.md`;T4.3 ablation/config vàT4.4 còn pending, chưaM4complete.

### T4.3 — Benchmark và ablation

**Ước lượng:** 4–5 giờ. **Phụ thuộc:** T4.2.

- [x] So sánh vector-only, keyword-only, hybrid RRF, hybrid + reranker.
- [x] Giữ corpus, LLM, prompt và context budget cố định khi so retrieval.
- [x] Thử top-k/chunking trên development set.
- [x] Ghi config hash, commit và corpus version.
- [x] Ghi phần cứng, concurrency, warm/cold state.
- [x] Chọn cấu hình cuối trước khi chạy held-out test.

**Nghiệm thu:** có bảng kết quả thật về chất lượng, latency, chi phí; báo cáo trung thực cả khi reranker không cải thiện.

**Hoàn tất T4.3 2026-10-11local:**4variants×60+topk4/12×60=360newdevelopmentpredictions,
77exactsemantic question/output bundlesmanualreview vớinewresponse/PIDbindings. Samecorpus/
LLM/prompt/budgets/20candidates;vector/KW/RRF/CEcorrect41/35/36/41of47,taskcitation
53/75,45/69,48/71,52/71. CEvsRRF5pairedwins/0loss nhưngcaoCPUlatency. Topk4/8/12
cùngquality/claims; chọnCEk4 theoobservedlatencytie-breakp50/p9512.441/17.820s,
configs/rag/t4_3_selected.json/sealeddecision. Onepasslatency khôngcausalclaim;API0VND/
localcomputeunpriced.354tests/12Node/Ruff/frozen guards đạt,0heldoutinference.
`docs/benchmark-ablation-review.md`;T4.4 fixes+finalreleasefreeze còn pending.

### T4.4 — Error analysis và chốt cấu hình

**Ước lượng:** 5–7 giờ. **Phụ thuộc:** T4.3.

- [x] Chọn khoảng 20 failure cases trên development set.
- [x] Phân loại parsing/OCR, chunking, metadata, retrieval, reranking, generation, citation, abstention.
- [x] Sửa 2–3 nhóm lỗi tác động lớn nhất.
- [x] Chạy lại development evaluation.
- [x] Freeze cấu hình rồi chạy held-out test.
- [x] Ghi giới hạn còn tồn tại.

**Nghiệm thu M4:** dataset/evaluator có version; benchmark tái chạy được; báo cáo lỗi và tác động sửa chữa. Không tuning theo test rồi gọi đó là held-out.

**Hoàn tất T4.4/M4 2026-10-11:**20errorcases/19queries; sửa multi-obligation/source-selection,
calendar-unit qualifiers và study_progress. Giữ iteration1D06falseabstention; exactfinaldev60
review:47/47correct/65of65facts/60of60taskcites, từ reference41/47/57of65/52of71.
Freeze code/config07:10UTC, one-runledger claim07:11UTC, full40test07:11–07:26UTC.
Held-out **19/28correct/32of43facts/29of108taskcites/0of7correctreject**, clarification
requiredaxes0/20; source/citation/filterfidelity40/40. p50/p95dev12.351/15.824s,
test21.552/32.707s;API0VND/localcomputeunpriced.370pytest/13Node/65browserassertions,
Ruff/lock70/integrity đạt. `configs/rag/final.json`,releasefreeze và
`docs/error-analysis-review.md`; quality targets chưa đạt, giữlocaldemo/evidence snapshot.
Không sửa inferencecode/config hoặc gold sau test;21failedcases giữ nguyên. Test40đãexposed,
futurequalitywork cần development/evidence/testset mới để đo prospectiveheld-out.

### Chỉ tiêu chất lượng mục tiêu

Các số sau là mục tiêu, không phải kết quả thực nghiệm hoặc số liệu để đưa ngay vào CV.

| Chỉ số | Mục tiêu ban đầu |
|---|---:|
| Recall@5 trên câu có đáp án | ≥ 0,85 |
| Citation ID hợp lệ | 100% |
| Citation support precision, kiểm tra thủ công | ≥ 0,90 |
| Câu trả lời đúng và đủ ý chính | ≥ 80% |
| Từ chối đúng trên câu không có đáp án | ≥ 85% |
| Từ chối nhầm trên câu có đáp án | ≤ 15% |

- Báo cáo cả tử số/mẫu số, ví dụ `8/10`, vì test set nhỏ.
- Latency cần đặt theo máy và provider thực tế; có thể dùng p95 < 10 giây làm mục tiêu thử nghiệm ban đầu với demo một người dùng.
- Nếu không đạt mục tiêu: ghi kết quả, nguyên nhân và quyết định phát hành; không thay đổi nhãn chỉ để làm metric đẹp hơn.

## Tuần 5 — Đóng gói portfolio

**Mục tiêu:** người khác hiểu, chạy thử và kiểm chứng project được.
**Thời lượng:** khoảng 16–22 giờ.

### T5.1 — UI hỏi đáp và xem nguồn

**Ước lượng:** 4–5 giờ. **Phụ thuộc:** M3; dùng cấu hình cuối từ M4 khi sẵn sàng.

- [x] Ô nhập câu hỏi, filters và câu hỏi mẫu.
- [x] Trạng thái loading/error.
- [x] Câu trả lời kèm citation.
- [x] Link nguồn, trang và excerpt.
- [x] Hiển thị clarification/insufficient evidence rõ ràng.
- [x] Feedback đơn giản đúng/sai hoặc hữu ích/không hữu ích.

**Nghiệm thu:** người mới đặt câu hỏi và kiểm tra bằng chứng trong khoảng một phút.

**Hoàn tất earlyT5.1 2026-10-10 theo yêu cầu user trướcT4.2:** UI/UXProMax design,
same-originFastAPI webdemo `/`, nativeHTML/CSS/ESmodules,scope/filters/4developmentpresets,
actualcitations/sourcepages/excerpts,clarification/loading/errors,sessionfeedback/JSONexport.
303pytest/12Node tests,27browserfixture assertions/18real-browser assertions(5knownrequests)
đạt;0axeA/AAviolations trongautomatedscans. Firstrealask~24.4s vàmởđúngcitation.
`docs/demo-guide.md`, `docs/demo-ui-review.md`; M4benchmark/configfinal vẫn pending,
UI đọc backenddefaultconfig khi có. Held-out40 giữfreeze/0inference trongstepdemo.

**Feedback demo hoàn tất 2026-10-10:** sửa GPA/mainsemester và clause-scoped freshness;
79014.1(a) không bị1393 sửa nên ĐTBC≥8/cap30 vẫn dùng được kể cả790-only. Hè/affected
clauses vẫn cần applicableupdate.322pytest/12Node/22livebrowserassertions đạt;
8GPAcases6supported/2correctabstain vàfixed12 giữ11supported/1abstain. Nguồn/hash/
filters/gold/freeze giữ nguyên; `docs/gpa-credit-freshness-review.md`. T4.2 vẫn pending.

### T5.2 — Observability

**Ước lượng:** 3–4 giờ. **Phụ thuộc:** pipeline hoạt động.

- [ ] Request ID xuyên suốt pipeline.
- [ ] Trace retrieve → rerank → generate.
- [ ] Model, prompt version, retrieved chunk IDs.
- [ ] Latency, tokens và API cost.
- [ ] Langfuse nếu thời gian cho phép.
- [ ] Không log secrets; giới hạn nội dung log phù hợp.

**Nghiệm thu:** từ câu trả lời sai truy ra chunk, thứ tự rerank, context và bước gây chậm.

### T5.3 — Docker, CI và deployment

**Ước lượng:** 4–6 giờ. **Phụ thuộc:** T5.1, M4.

- [ ] Docker hóa backend/UI.
- [ ] Compose cho database, backend và frontend.
- [ ] Ghi riêng bước tải model, migration và ingest lần đầu.
- [ ] CI chạy lint và test quan trọng.
- [ ] Mock LLM trong CI.
- [ ] Deploy demo trên môi trường đã thống nhất.
- [ ] Nếu public dùng API trả phí: giới hạn request/input.
- [ ] Kiểm tra startup, migration và health check.

**Nghiệm thu:** fresh setup chạy theo README; CI xanh; demo truy cập được; không che giấu bước setup thủ công dưới tuyên bố “một lệnh”.

### T5.4 — README, video và phỏng vấn

**Ước lượng:** 5–7 giờ. **Phụ thuộc:** M4, T5.1–T5.3.

#### README

- [ ] Bài toán, phạm vi, ảnh/GIF demo.
- [ ] Architecture diagram, data sources.
- [ ] Hướng dẫn chạy, phần cứng, config.
- [ ] Evaluation methodology và benchmark thật.
- [ ] Failure cases, limitations.
- [ ] Trade-off chất lượng, latency, chi phí.

#### Video 3–5 phút

- [ ] Giới thiệu bài toán.
- [ ] Câu đơn giản và mở nguồn.
- [ ] Câu cần nhiều điều khoản.
- [ ] Câu không có đáp án.
- [ ] Kiến trúc và kết quả benchmark.

#### Phỏng vấn/CV

- [ ] Chuẩn bị 3 quyết định thiết kế quan trọng.
- [ ] Chuẩn bị 3 lỗi thật và cách sửa.
- [ ] Chuẩn bị 1 ví dụ hệ thống còn thất bại.
- [ ] Viết CV bullet với kết quả thực đo.

**Nghiệm thu M5:** repository, demo, video, benchmark nhất quán; trình bày overview trong 5 phút và đào sâu trong 15–20 phút.

---

# PHẦN III — TỔ CHỨC, KIỂM THỬ VÀ BÀN GIAO

## 6. Cấu trúc repository đề xuất

```text
regularag/
├── src/regularag/
│   ├── api/
│   ├── core/
│   ├── db/
│   ├── ingestion/
│   │   ├── parser.py
│   │   ├── cleaner.py
│   │   ├── chunker.py
│   │   └── pipeline.py
│   ├── retrieval/
│   │   ├── vector.py
│   │   ├── keyword.py
│   │   ├── fusion.py
│   │   └── reranker.py
│   └── generation/
│       ├── prompts.py
│       ├── citations.py
│       └── service.py
├── frontend/
├── scripts/
├── migrations/
├── tests/
│   ├── unit/
│   └── integration/
├── evals/
│   ├── datasets/
│   ├── configs/
│   ├── results/
│   └── run.py
├── data/manifests/
├── docs/
│   ├── project-brief.md
│   ├── architecture.md
│   ├── data-sources.md
│   ├── evaluation.md
│   ├── error-analysis.md
│   ├── progress.md
│   └── handoff.md
├── .github/workflows/ci.yml
├── .env.example
├── compose.yaml
├── pyproject.toml
├── RegulaRAG-Project-Plan.md
└── README.md
```

Tạo module theo nhu cầu từng task, không cần tạo toàn bộ file rỗng ngày đầu.

## 7. Các test ưu tiên

| Test | Điều cần chứng minh |
|---|---|
| Page mapping | Chunk trỏ về đúng trang |
| Ingest idempotency | Ingest lại không tạo trùng |
| Delete/update | Chunk cũ không còn xuất hiện sau thay đổi |
| Metadata filtering | Không dùng sai đối tượng/phạm vi |
| RRF | Kết hợp ranking, xử lý trùng đúng |
| Citation validation | Không chấp nhận source ID bịa |
| Empty retrieval | Thiếu bằng chứng được xử lý có kiểm soát |
| Provider failure | Timeout/API error không làm server crash |
| End-to-end | Corpus nhỏ trả answer và nguồn hợp lệ |

Tests xác minh hành vi code. Evaluations đo chất lượng retrieval/câu trả lời. Cần cả hai, không chạy theo coverage hình thức.

## 8. Mẫu theo dõi tiến độ

Tạo bảng sau trong `docs/progress.md` khi bắt đầu triển khai. Trạng thái dùng: `pending`, `in_progress`, `blocked`, `completed`.

| Task | Trạng thái | Đầu ra/bằng chứng | Blocker | Bước tiếp theo |
|---|---|---|---|---|
| T1.1 | pending | Chưa triển khai | — | Chốt bài toán và môi trường |

Không đánh dấu task hoàn thành chỉ vì code đã được tạo. Ghi lệnh kiểm chứng, kết quả và artifact liên quan.

## 9. Mẫu bàn giao cuối phiên

```markdown
# Session handoff

## Hiện trạng
- Milestone:
- Task đang làm:
- Git commit/branch nếu có:

## Đã thực hiện
- File thay đổi:
- Quyết định kỹ thuật:

## Kiểm chứng
- Lệnh đã chạy:
- Kết quả:
- Chưa kiểm chứng:

## Blocker
- Vấn đề:
- Cần người dùng cung cấp:

## Phiên tiếp theo
1. Task ưu tiên:
2. File cần đọc:
3. Tiêu chí hoàn thành:
```

## 10. Quy tắc giảm phạm vi khi chậm tiến độ

### Dời trước

1. Dashboard admin.
2. Multi-university.
3. Đăng nhập/phân quyền.
4. Hội thoại nhiều lượt.
5. Phát hiện mâu thuẫn tự động.
6. OCR diện rộng.
7. UI cầu kỳ.
8. Langfuse nếu structured logs đã đủ debug.

### Giữ lại

- Pipeline end-to-end.
- Provenance và citation kiểm tra được.
- Metadata filtering cơ bản.
- Baseline và phép so sánh retrieval.
- Abstention/clarification.
- Evaluation kiểm tra thủ công.
- Docker, README và demo.

**Giảm số tính năng trước khi giảm chất lượng evaluation.**

## 11. Definition of Done toàn project

- [ ] Corpus chính thức, nguồn rõ ràng.
- [ ] Ingestion chạy lại được và có xử lý lỗi.
- [ ] Hỏi đáp tiếng Việt hoạt động.
- [ ] Citation trỏ đúng nguồn và kiểm tra được.
- [ ] Có hành vi rõ khi thiếu thông tin.
- [ ] Ít nhất 3 cấu hình retrieval được so sánh.
- [ ] Dataset đánh giá và kết quả thật.
- [ ] Báo cáo failure cases.
- [ ] CI và hướng dẫn chạy tái lập.
- [ ] Demo/video.
- [ ] Giải thích được pipeline và trade-off, không chỉ kể tên thư viện.

## 12. Câu hỏi cần trả lời khi phỏng vấn

1. Vì sao chọn bài toán này và phạm vi một trường?
2. Vì sao dùng hybrid retrieval thay vì chỉ vector?
3. Chunk size và cấu trúc điều khoản ảnh hưởng thế nào?
4. Reranker cải thiện hoặc làm giảm kết quả ở đâu?
5. Citation validation bảo đảm được gì và chưa bảo đảm được gì?
6. Hệ thống phân biệt thiếu bằng chứng với câu hỏi thiếu điều kiện ra sao?
7. Vì sao retrieval score không phải confidence của đáp án?
8. Làm sao ngăn retrieval lấy sai phiên bản văn bản?
9. Làm sao cập nhật/xóa tài liệu mà không giữ chunk cũ?
10. Đã chia development/test và tránh leakage thế nào?
11. Failure case lớn nhất là gì và đã đo tác động sửa chữa ra sao?
12. Nếu lượng người dùng tăng, bottleneck đầu tiên nằm ở đâu?

## 13. Mẫu CV bullet — chỉ điền số liệu sau khi đo

> Built a Vietnamese university-regulation RAG assistant using FastAPI, PostgreSQL/pgvector, hybrid retrieval, cross-encoder reranking, and verifiable citations. Evaluated on [N] manually verified questions, achieving [measured metric] under [evaluation conditions]. Implemented evidence-based abstention, reproducible benchmarks, Docker deployment, and CI tests.

**Thông điệp portfolio quan trọng nhất:** “Tôi bắt đầu từ baseline này, phát hiện những lỗi này, thay đổi các thành phần này và đo được tác động như sau.”
