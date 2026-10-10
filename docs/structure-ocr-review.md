# Chunking cấu trúc và OCR có điều kiện — T2.2

Ngày: 2026-10-08. Pipeline `structured-ocr-v2`; migration `004_structure_quality`.

## Preparation và OCR

Corpus 15 PDF/188 trang đã kiểm source SHA-256. Preparation dùng PyMuPDF trên 53
trang và Tesseract trên 135 trang (thiếu text hoặc forced OCR cho PDF 43 lỗi encoding).
Tesseract 5.5.2 trong `ragschool`, vie+eng, OEM 1/PSM 3, 300 DPI, 2 CPU threads;
engine/build/traineddata hash ở `data/manifests/ocr_runtime.json`.

Giữ native text, raw OCR, raster/TSV/hash, confidence và post-edit. Confidence cao
không auto approve. Review bind source/cleaned-text SHA; correction còn kiểm raw OCR
hash và page identity. Review do assistant đối chiếu ảnh/text, không phải đánh giá độc lập.

| Preparation status | Trang |
|---|---:|
| Native không có flag cần review | 40 |
| Approved sau visual comparison | 4 |
| Excluded layout/TOC | 23 |
| Pending review | 121 |

## Chunking và provenance

Nhận diện chương/điều/khoản; giữ đơn vị vừa budget, lặp đầy đủ tiêu đề khi chia điều
dài. Target 700/hard ceiling 800 BGE-M3 token; điều ngắn có thể dưới ngưỡng mềm 500.
Source spans phân biệt body/heading context, giữ trang, extraction/review và hash/text.
Trang excluded reset hierarchy; phụ lục là boundary riêng; năm 2024 không làm số khoản.

Header/footer bỏ theo bounding box lề và page-label/repeat. Số giống footer ở thân
trang được giữ. Review đã sửa numeric block có blank spans và candidate nối qua gap.
Validator kiểm 97 chunk: token/hash/page-span membership, không quá 800, không lấy
span từ pending/excluded page. Review 32 chunk đa dạng được bind hash ở
`data/manifests/structured_chunk_review.csv`.

## 1393 và bảng

OCR 1393 confidence 93.6/94.6 vẫn sai mã văn bản, diacritics, dấu nhân và `1 tháng`
thành `| tháng`. Hai trang đã so raster 300 DPI và post-edit riêng, raw OCR không bị
ghi đè. Đã kiểm công thức/định nghĩa HPTCHM HKHE; 70 sinh viên; cap 12 tín chỉ và
điều kiện đủ sĩ số; thời hạn 1 tháng/điểm M; hiệu lực kể từ ngày ký.

790 page 3 glossary và 956 page 7 bảng JLPT/NAT đơn giản đã đối chiếu layout.
790 page 18 và 956 pages 3/6/9/10 còn mất quan hệ merged/hierarchical row-column,
loại khỏi evidence. Lưu đồ 159 pages 9–11 và TOC cũng bị loại. 43 đã OCR hai trang
nhưng chưa chứng minh đủ bảng cohort/học phí, chưa publication.

| Document ready | Coverage | PDF pages excluded | Chunk |
|---|---|---|---:|
| 1393 | full | — | 3 |
| 159 | partial | 9,10,11 | 24 |
| 790 | partial | 1,2,18 | 45 |
| 956 | partial | 3,6,9,10,13 | 25 |
| Tổng | | | 97 |

11 document khác (10 scan cần review và 43) còn blocked. OCR không tự thêm allowlist;
cặp 412 + 513 chưa publication. Re-ingest lần hai: 4 unchanged, 97 ID duy nhất,
không chunk review-required trong active index, không run pending/processing.

## Kiểm chứng và giới hạn

Quality gate: 66 tests pass (43 unit/23 PostgreSQL integration), Ruff check/format,
pip check và lock70/70 pass. Tesseract là dependency Conda native riêng.

Tests bao gồm conditional OCR, không auto approve confidence, native/raw preservation,
hash-bound correction/review, body/footer numeric, hierarchy gap, phụ lục, inline
article, full-heading repeat, SQL metadata/coverage và lifecycle.

API smoke 3 câu 1393 đều HTTP 200 nhưng chưa đạt đáp án: 2 dense retrieval chọn 790
thiếu amendment trong context, 1 output model JSON lỗi. Bằng chứng:
`data/manifests/ocr_api_smoke.csv`. Backend chặn `amendment_not_in_context` dù 1393
đã ready; không coi index xong là đủ để áp dụng văn bản gốc mà thiếu đối chiếu.

## Tái lập

```powershell
conda env update -n ragschool -f environment.yml
conda activate ragschool
python scripts/migrate.py
python scripts/prepare_structured.py --output-dir data/processed/structured-final
python scripts/export_page_review.py --input-dir data/processed/structured-final
python scripts/validate_structured.py --input-dir data/processed/structured-final
python scripts/ingest.py ingest data/raw/uit/p0 --report data/manifests/structural_ingestion.csv
```

Publication chỉ tái lập khi review/correction đúng hash có sẵn. Full text/raster/TSV/
correction ở `data/processed/` bị Git ignore; repo public chứa script/config/hash/
thống kê. Clone thiếu post-edit/review tương ứng cần review lại trước publication.

T2.3 tiếp theo: keyword search riêng và RRF cho số văn bản/số điều; review corpus
tiếp trước M2. Chưa kết luận OCR/chunking cải thiện answer accuracy khi chưa evaluation.
