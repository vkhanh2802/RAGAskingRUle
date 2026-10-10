# Kiểm chứng ingestion lifecycle — T2.1

Ngày: 2026-10-08. Migration: `003_ingestion_lifecycle`.

## Luồng và trạng thái

Mỗi tài liệu có một `ingestion_runs` riêng cho mỗi lần ingest/delete. Một lần ingest
đi qua `pending` → `processing` → `ready` hoặc `failed`. Run lưu source hash yêu cầu,
hash thực tế khi đọc PDF, config/version pipeline, model/revision/fingerprint, artifact
path, số chunk, timestamp và lỗi riêng.

- `documents.ingestion_status` là trạng thái lần xử lý hiện tại;
  `retrieval_status` là cổng publication riêng.
- Retrieval yêu cầu cả hai trạng thái `ready`, allowlist và embedding fingerprint phù hợp.
- Parser/chunker/embedding chạy ngoài transaction dài. Publication thay chunk và cập nhật
  document/run `ready` trong một transaction theo từng tài liệu.
- Cập nhật thất bại giữ bản chunk cũ để kiểm tra nhưng document bị chặn khỏi retrieval.
- SHA-256 và ingestion fingerprint trùng, index đầy đủ, document ready: ghi run `unchanged`
  và bỏ qua parsing/embedding. Metadata vẫn được cập nhật từ manifest.
- Hash nguồn, config chunking hoặc model/fingerprint đổi: tạo artifact theo run UUID và
  thay index sau khi kiểm chứng thành công.
- Session advisory lock theo schema/document ngăn hai worker ingest/delete cùng tài liệu.
  Khi retry sở hữu được lock, run cũ chưa hoàn tất được đóng thành `failed/interrupted`.
- Delete cascade toàn bộ chunk, giữ audit với `document_id_snapshot`; xóa lại trả `not_found`.

CLI mới: `scripts/ingest.py` hoặc `python -m regularag.ingestion.cli`.
Indexer processed baseline cũng dùng lifecycle, không còn đường ghi batch bỏ qua trạng thái.
Lane processed kiểm metadata, identity, content hash và page provenance; chỉ lane PDF
đọc file nguồn để ghi `actual_source_sha256`.

## Corpus thật

Đã kiểm SHA-256 và xử lý thư mục P0 có 15 PDF. Snapshot cuối:

| Chỉ số | Kết quả |
|---|---:|
| Document đã đăng ký | 15 |
| `ready` / publication `ready` | 3: 159, 790, 956 |
| `failed` / publication `blocked` | 12 |
| Chunk / chunk ID duy nhất | 46 / 46 |
| Chunk có FK đến ingestion run | 46 |
| Run còn pending/processing | 0 |

Mười một PDF scan ghi `ocr_required`; PDF 43 lỗi encoding ghi `quality_not_approved`.
Đây là trạng thái xử lý/chất lượng, không phải kết luận về hiệu lực pháp lý của văn bản.

| Lượt kiểm chứng | Ingest mới | Unchanged | Failed | Bằng chứng |
|---|---:|---:|---:|---|
| Retry riêng 159 sau timeout | 1 | 0 | 0 | `data/manifests/ingestion_lifecycle_resume.csv` |
| Batch thư mục hoàn tất lần 1 | 2 | 1 | 12 | `data/manifests/ingestion_lifecycle_first.csv` |
| Batch thư mục hoàn tất lần 2 | 0 | 3 | 12 | `data/manifests/ingestion_lifecycle_second.csv` |

Hai batch thư mục trả exit code 1 đúng contract partial failure; vẫn xử lý đủ 15 file.
Lượt thứ hai không chạy embedding lại cho cả ba document ready và không tăng số chunk.

Lần chạy đầu bị tool timeout tại embedding của 159; worker đã dừng nhưng document
còn `processing` và bị chặn khỏi search. Retry phục hồi tự động, lưu lỗi `interrupted`
của run cũ rồi xuất bản lại 159. Runtime sau đó dùng batch 1 / 2 CPU threads với cache
model offline; embedding fingerprint loại các tham số hardware này. Chưa xác định nguyên
nhân chính xác của lần chậm ban đầu và không coi đây là benchmark tăng tốc.

CLI ghi progress vào stderr, JSON tổng kết vào stdout; CSV report được flush sau mỗi
tài liệu hoàn tất để một lần ngắt tiếp theo không làm mất các hàng đã xử lý.

## Kiểm chứng PostgreSQL

Quality gate: **53 tests pass**, gồm **32 unit + 21 integration**; Ruff check/format,
`pip check` và lock 70/70 pass. Integration chạy trong schema riêng rồi xóa schema;
delete/update/failure test không thao tác corpus thật.

Các case quan trọng:

- Ingest PDF hai lần không nhân đôi chunk và không gọi embedding lần hai.
- Một PDF corrupt có hash đúng manifest không phá hai PDF tốt khác trong batch.
- Hash mismatch được ghi requested/actual hash và có thể retry.
- Update thành công không trả text cũ; update lỗi làm text cũ bị ẩn; retry xuất bản text mới.
- SQL constraint failure sau bước thay chunk rollback toàn transaction của document.
- `pending`, `processing`, `failed` không vào search ngay cả khi publication flag là ready.
- Delete không để lại chunk trong search, audit còn sau khi FK document bị set null.
- Model revision đổi không được skip; writer thứ hai bị `document_busy`.
- Run mất worker được đóng khi retry hoặc delete; report đã flush vẫn còn khi bị ngắt.

## Bước tiếp theo

T2.2: chunking cấu trúc và OCR có điều kiện, ưu tiên amendment 1393 để hoàn thiện bộ
790 + 1393. PDF scan và PDF 43 chỉ được publication sau OCR/reparse và rà soát chất lượng.
