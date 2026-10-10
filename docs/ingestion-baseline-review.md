# Rà soát parsing và chunking baseline

## Cấu hình

- Pipeline: `baseline-v1`.
- Parser: PyMuPDF theo từng trang.
- Tokenizer: `BAAI/bge-m3`, revision
  `5617a9f61b028005a4858fdac845db406aefb181`.
- Target: 700 token; ngưỡng mềm tối thiểu 500; hard ceiling 800; overlap 100.
- Output toàn văn: `data/processed/baseline/`, không commit.
- Thống kê không chứa toàn văn: `data/manifests/baseline_parse_summary.csv`.

## Kiểm chứng tự động

Lệnh `python scripts/validate_baseline.py` kiểm tra lại token count, content hash,
chunk index và toàn bộ source page reference. Kết quả ngày 2026-10-06:

| Chỉ số | Kết quả |
|---|---:|
| Tài liệu | 4 |
| Trang PDF | 55 |
| Chunk | 48 |
| Token nhỏ nhất/lớn nhất | 478/705 |
| Chunk dưới ngưỡng mềm 500 | 2 |
| Lỗi hard ceiling/hash/page mapping | 0 |

Hai chunk 478 và 489 token giữ nguyên ranh giới đoạn dài thay vì cắt thêm chỉ để đạt
ngưỡng mềm. Tail chunk 110 token ban đầu đã được gộp an toàn với chunk trước; kết quả
705 token, dưới hard ceiling 800.

## Kiểm tra thủ công 20 chunk

| Văn bản | Chunk đã xem | Số lượng | Đọc được | Page mapping |
|---|---|---:|---|---|
| 159/QĐ-ĐHCNTT | `0000`-`0007` | 8 | Có; lưu đồ vẫn bị tuyến tính hóa | Đúng |
| 43/TB-ĐHCNTT | `0000`-`0001` | 2 | Không; lỗi encoding font nhúng | Đúng |
| 790/QĐ-ĐHCNTT | `0000`-`0005` | 6 | Có; bảng bị tuyến tính hóa | Đúng |
| 956/QĐ-ĐHCNTT | `0000`-`0003` | 4 | Có; bảng bị tuyến tính hóa | Đúng |

Tổng cộng 20/20 chunk trỏ đến đúng trang; 18/20 đọc được. Ba tài liệu `159`, `790`
và `956` đạt nghiệm thu baseline. `43/TB-ĐHCNTT` có text layer nhưng nội dung tiếng
Việt bị garbled do encoding font; không đưa hai chunk này vào retrieval trước khi OCR
hoặc reparse và kiểm tra lại.
