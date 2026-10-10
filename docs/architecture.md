# Kiến trúc ban đầu của RegulaRAG

## Mục tiêu thiết kế

Kiến trúc phải giữ được provenance từ tài liệu gốc đến citation, cho phép kiểm thử
ingestion/retrieval/generation độc lập và tái lập một evaluation run bằng cấu hình
đã lưu. Baseline được ưu tiên hơn tối ưu sớm để phù hợp máy 12 GB RAM, RTX 3050
6 GB và ngân sách API 0 VND.

## Sơ đồ luồng chính

```text
Nguồn chính thức UIT + source manifest
                 |
                 v
        Tải/kiểm tra content hash
                 |
                 v
       PyMuPDF parsing --(thiếu text)--> OCR có điều kiện
                 |
                 v
       Cleaning + chunking + metadata
                 |
                 v
 PostgreSQL: documents / chunks / ingestion_runs
         |                              |
         v                              v
 PostgreSQL FTS                  pgvector embeddings
         |                              |
         +------------> RRF <-----------+
                          |
              verified freshness + companions
                          |
                     reranker (tùy chọn)
                         |
                         v
              context + token budget
                         |
                         v
                LLM local/free tier
                         |
                         v
      schema validation + citation validation
                         |
                         v
              FastAPI -> Streamlit (dự kiến)

Evaluation và structured logs quan sát xuyên suốt pipeline.
```

## Thành phần

### 1. Source manifest

`data/manifests/documents.csv` là danh mục kiểm kê nguồn, không phải bằng chứng tự
động về hiệu lực. Mỗi tài liệu dự kiến có URL chính thức, thời điểm tải, tiêu đề,
mã văn bản, ngày ban hành, ngày hiệu lực nếu được nêu rõ, đối tượng áp dụng, kiểu
PDF và quan hệ sửa đổi/thay thế có bằng chứng.

### 2. Ingestion

- PyMuPDF đọc từng trang và giữ text thô để đối chiếu.
- OCR chỉ chạy với trang thiếu text sau bước phát hiện; provenance phải ghi rõ text
  đến từ parser hay OCR.
- Cleaning không được làm mất số điều, khoản, ngưỡng điểm hoặc mã văn bản.
- Chunking baseline theo đoạn với giới hạn cấu hình ban đầu 500-800 token và
  overlap 80-120 token; T2.2 mới bổ sung nhận diện chương/điều/khoản.
- Content hash, trạng thái ingestion và version pipeline bảo đảm ingest lại không
  tạo trùng và retrieval chỉ dùng tài liệu `ready`.
- T2.1 triển khai transaction theo từng tài liệu và advisory lock theo schema/document.
  Update lỗi giữ chunk cũ để audit nhưng chặn search; retry/hash/config/model đổi được
  ghi vào run riêng. Delete cascade chunk và giữ snapshot ID trong history.
- T2.2 triển khai `structured-ocr-v2`: chapter/article/clause, title repeat, source spans,
  conditional Tesseract OCR và page-level hash-bound review. Confidence không tự approve;
  hierarchy không được suy qua trang bị loại và phụ lục có boundary riêng.
- M2 review133 pages của11 nguồn, explicit post-edit và table row-column serialization;
 307 approved chunks/15 ready documents. Mixed-page omission giữ flag/partial coverage,
 source dates/scope notes bind source hashes;0 pending không có nghĩa mọi layout được hỗ trợ.

### 3. Storage và provenance

PostgreSQL + pgvector lưu ba thực thể chính:

- `documents`: nguồn, metadata phạm vi, content hash và trạng thái xử lý.
- `chunks`: nội dung, thứ tự, document ID, trang PDF bắt đầu/kết thúc, số trang in
  nếu xác định được, phương thức trích xuất và vector.
- `ingestion_runs`: thời điểm, cấu hình/version, trạng thái và lỗi theo tài liệu.
- `ingestion_status` là lifecycle pending/processing/ready/failed; `retrieval_status`
  là publication gate. Cả document và companion amendment phải ingestion-ready để
  được dùng trong retrieval/provenance tương ứng.
- Coverage full/partial/unreviewed cùng excluded PDF pages mô tả phần nguồn dùng làm
  evidence. Chunk lưu extraction/review và nguồn của cả body lẫn heading context.

Citation hiển thị cho người dùng được dựng từ dữ liệu đã lưu, không cho LLM tự tạo
URL, tên tài liệu hoặc số trang.

### 4. Retrieval

- Baseline M1: dense retrieval bằng BAAI/bge-m3 nếu đo tài nguyên cho phép.
- Kết quả T1.5: dùng `intfloat/multilingual-e5-small` 384 chiều trên CPU do RAM trống
  khi chạy Docker không đủ để ưu tiên BGE-M3. Chunk dài được embed qua cửa sổ/pooling,
  không cắt im lặng ở 512 token. BGE-M3 vẫn là tokenizer chunking.
- T2.3: weighted PostgreSQL `simple`/`unaccent` FTS và GIN là nhánh keyword riêng.
  `ts_rank_cd` không phải BM25. Trigger refresh chunk text/structure/document metadata.
- Query accent-fold hỗ trợ mã văn bản/số điều; terms OR và article phrase là lexical
  lookup, có thể khớp reference trong body. Mã văn bản constrain keyword branch.
- RRF k60/weights1:1 hợp nhất candidate20 mỗi nhánh, loại chunk ID trùng và giữ
  branch/overall rank/raw scores. Dense cosine>=0.55 áp trước fusion; keyword/RRF
  dùng ngưỡng riêng. Config default hybrid, API override vector/keyword/hybrid.
- T2.4: publication/model/quality và metadata filter dùng chung trong SQL trước LIMIT/RRF.
  Filter IDs/domain/type/audience/cohort/as_of, exact tags và AND giữa fields.
- Migration006 typed dates/cohort từ metadata có evidence; cohort review bind sourceSHA,
  không suy năm/hiệu lực từ title. as_of không xác nhận current; unknown status hiển thị.
- T3.1: pinned mmarco-mMiniLMv2 CPU/window-max512/32,20candidates; rawCElogit và
  branch/rawrank giữriêng. Model không truncate đuôi; configurabletoggle/measuredon-off.
- Source-bound version/relationship CSV overlays refresh qua metadata/lifecycle;
  verified successors bỏoldaffectedclauses vàreserveupdatecontext. Catalog nhìn cả
  blocked/latest outsideallowlist; khôngcoi missingnewversion làđược dùngoldrule.
- Issued-date latest chỉ trongverified family vàrequestscope/cutoff, khôngglobalnewest
  haylegalactive. Explicitdocrefs hiệnconstrain cảdense vàkeyword trướcLIMIT;
  relation evidence có thểbổsung companion, khôngnới callerfilters.

### 5. Generation và citation

T3.3 bổ sung scope policy **trước retrieval**: thông tin cần thiết còn thiếu/mâu thuẫn
trả `needs_clarification` từ backend, không chạy model. Explicit cohort/audience/date
thêm filter còn trống; programme/design duration đi vào passage selection. Caller
filters giữ nguyên; không có query rewriting hoặc conversation memory. Câu hỏi hiệu
lực pháp lý chưa verified và comparison chưa consolidated trả insufficient cùng
source-bound metadata notes, không tự chọn/hợp nhất phiên bản.

T3.4 thêm declared task/institution boundaries và full-context hash/instruction gate
trước budgeting/model. Context có assistant-control instructions bị abstain nguyên
context, không strip/rebind text hoặc bỏ required update. Guard có trong prepare/resolve,
chat-control escaping dùng chung adapters. Những heuristic này không phải general
entailment/injection classification. 24 API +10 synthetic cases vàpositive12 xác nhận
M3 technical acceptance; source binding vẫn phải đi cùng semantic support review.

Context builder gán các ID cục bộ như `[S1]` cho các chunk đã chọn và giới hạn
context theo token budget. Prompt coi tài liệu truy xuất là dữ liệu, không phải chỉ
dẫn hệ thống. LLM phải trả response có cấu trúc với một trong ba trạng thái:
`answered`, `insufficient_evidence`, `needs_clarification`.

Backend xác thực source ID có tồn tại trong context, sau đó lấy metadata citation
từ database. Bước này ngăn citation ID bịa nhưng không tự chứng minh rằng đoạn
trích hỗ trợ phát biểu; citation support còn phải được evaluation và kiểm tra thủ
công.

Baseline T1.5 dùng Qwen2.5-1.5B GGUF Q4_K_M qua llama.cpp CPU để chọn quote theo
JSON grammar. Context lấy cửa sổ đoạn liên tiếp theo câu hỏi, giữ đoạn lân cận và
kiểm token budget toàn bộ ChatML. Backend kiểm quote có trong context trước khi dựng
answer nguyên văn, nhằm chặn diễn giải bịa đã quan sát ở các model nhỏ. Điều này chưa
tự kiểm relevance/đủ ngoại lệ. Corpus dùng allowlist + `ready`; companion amendment
chưa ready khiến câu trả lời dựa trên base bị abstain. Xem `docs/rag-baseline-review.md`.
T2.2 bổ sung cổng amendment phải full/ready và có trong context đối chiếu; dữ liệu đã
index nhưng không được retrieve chưa đủ để bỏ cổng này. Chi tiết tại
`docs/structure-ocr-review.md`.
T3.1 context6/top8/input4096; freshnessgate trướcgeneration vàsau budgeting. Historical
cutoff khôngbuộc futureamendment. Explicitreviewedtablerow/cohort/duration focus giữ
literalcontiguousrow vàbỏwrongrows; citation IDs gán lại theocontext thực gửiLLM.

### 6. API và UI

T3.2 pipeline dùngatomic source-bound passages saufreshness/re-ranking. LLM chỉchọn
request-scopedPIDsenum/strictJSON; backend validatesrange/textSHA, deriveSourceIDs,
quotes vàcitationmetadata. Minimalfacetcover/date-signature dependencies/completeconditions
đượcbudget tốiđa2304inputtokens, no arbitraryprefixtruncation. Facets cònlexical,
không phải semanticentailment tổngquát. Low-memory modelrelease giữa cácphase.

API `evidence_passages` chứaactualpromptspans/offsets/hash/cited/dependencies;
sources.excerpt vẫnapprovedfullchunk. Schema failure retrybounded1 ởllama; actual
answer body làverbatimbackendtext, khôngmodelcopy/sourceid/pageguess.

- FastAPI cung cấp `/health` và `POST /api/v1/ask`.
- Ask request nhận optional `retrieval_mode`; source trả `score_kind`, nhánh/rank,
  dense/keyword raw score và RRF score. Sources là context sau số chunk/token budget.
- Ask request nhận optional `filters`, response trả `applied_filters` và scope metadata
  của source. Cohort/date chưa có bằng chứng không khớp filter tương ứng.
- Source thêm `metadata_note` và `omitted_layout_pdf_pages`; source có nhiều exactaudience
  tags phân tách`;`. Document-level cohortfilter chưa lọc table rows hay program clauses.
- T3.1 API/source trả model/revision, firststage/rerank ranks/scores/windows,
  issued/latestissued dates/sourcechecked timestamp/status vàrequiredcompanionIDs.
- T3.3 request thêm optional `scope`; response thêm clarification/resolved_scope/
  requested_filters/behaviour_policy/version_notes. Minimal selected subsets phải giữ
  đủ support facets/signature dependencies; atomic conditions không bị cắt để làm ngắn.
  Facets có kiểm prerequisite edge đúng course, không coi progress clause là prerequisite.
- Streamlit dự kiến cho phép nhập câu hỏi, chọn filter và mở nguồn/đoạn trích.
- MVP không có tài khoản và không lưu dữ liệu cá nhân.

### 7. Evaluation và observability

- Dataset tách development/held-out test và giữ paraphrase gần nhau cùng split.
- So sánh vector-only, keyword-only, hybrid RRF và hybrid + reranker trong điều
  kiện cố định.
- Lưu version/config cho embedding, reranker, LLM, prompt, chunking và top-k.
- Structured logs theo request ID ghi latency, model version và chunk ID, không ghi
  secrets. Langfuse chỉ thêm sau baseline nếu cần.
- T2.3 lưu23 câu ×3 mode cùng query vectors/corpus/config. Document hit chỉ cần một
  candidate source, chưa là clause/answer accuracy. Hybrid có regression C03 và
  quote relevance lỗi ở OCR01; report `docs/hybrid-retrieval-review.md` giữ các lỗi.
- T2.4 development30 có reference/evidence/hash binding và manual assistant review, chưa
  independent/held-out. Chạy180 results (3 modes × 2 filter conditions), gold-chunk metrics
  tách khỏi answer accuracy. Vector+filter goldtop1 tốt hơn hybrid ở run này;
  `docs/metadata-development-review.md` ghi cả D15/D30 ngoài context2 và M2 corpus backlog.
- M2 corpus15/307, development30 bindings giữ nguyên;12 new identifierprobes và APItraces.
 15unchanged/0unfinished và156tests pass; scopedgoldmetrics ổn định, unfiltered khó hơn.
 M204 answered wrongcohort dùquote thật; schema/metadataquote/JSON còn lỗi. Reranker T3.1
 tiếp theo; milestone ởtechnical supported scope, không phải answeraccuracy.
- T3.1 hai216-rowruns30/20candidates; finalscoped hybrid-off18→on29/30goldtop1,
  stagep504.65s/12identifierprobes12/12. FullAPI12calls chỉ1supportedanswer,
  p50~104s; exactquote/source/latest audits pass nhưnggeneration chưa interactive.
 187tests,15ready/307FTS/19goldbindings unchanged. `docs/reranker-freshness-review.md`.

## Ranh giới module dự kiến

```text
src/regularag/
|- api/          # transport, schema và dependency wiring
|- core/         # settings, logging và versioned config
|- db/           # session, models và repositories
|- ingestion/    # parser, cleaner, chunker và pipeline
|- retrieval/    # vector, keyword, fusion và reranker
`- generation/   # prompt, citation validation và answer service
```

Chỉ tạo module khi task cần, không dựng toàn bộ file rỗng từ đầu.

## Quyết định và trade-off ban đầu

| Quyết định | Lý do | Đánh đổi/cách kiểm chứng |
|---|---|---|
| PostgreSQL + pgvector | Metadata, FTS và vector trong một nơi, dễ giữ tính nhất quán | Chất lượng FTS tiếng Việt phải đo với câu có dấu/không dấu |
| BAAI/bge-m3 làm ứng viên embedding | Đa ngôn ngữ và phù hợp tiếng Việt về mặt thiết kế | Chưa kết luận chất lượng; đo RAM/VRAM, latency và retrieval trước khi giữ |
| OCR có điều kiện | Giảm chi phí và lỗi trên PDF vốn đã có text | Trang scan/bảng có thể vẫn cần rà soát thủ công |
| Citation do backend dựng | Loại URL/trang do LLM phỏng đoán | Vẫn cần kiểm tra citation support, không chỉ ID hợp lệ |
| Cấu hình model thay được | Phù hợp ngân sách 0 VND và phần cứng giới hạn | Thêm kỷ luật lưu version/config cho mỗi run |
| Câu hỏi độc lập trước | Giảm lỗi query rewriting và phạm vi MVP | Hội thoại nhiều lượt được dời sang phiên bản sau |

## Rủi ro cần xác minh sớm

1. Nguồn chính thức UIT có đủ 10-20 tài liệu truy cập và được phép chia sẻ ở mức
   nào; T1.2 sẽ lưu manifest và chỉ dẫn nguồn.
2. Metadata về hiệu lực/đối tượng có thể không đầy đủ; giá trị chưa có bằng chứng
   phải để trống, không suy từ năm ban hành.
3. Python 3.14 có thể chưa tương thích PyTorch/PaddleOCR hoặc model stack; T1.3 sẽ
   khóa phiên bản Python tương thích sau kiểm tra.
4. RTX 3050 6 GB và RAM 12 GB có thể không chạy đồng thời embedding, reranker và
   LLM lớn; baseline phải đo từng thành phần, hỗ trợ CPU hoặc dịch vụ free tier.
5. PostgreSQL FTS mặc định có thể xử lý tiếng Việt chưa tốt; phải đánh giá bằng
   truy vấn thực thay vì giả định hybrid luôn tốt hơn.
