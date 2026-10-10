# Nguồn dữ liệu UIT

## Phạm vi đợt tải đầu

Ngày kiểm tra và tải: 2026-10-05.

Corpus P0 lấy từ trang chính thức [Văn bản & Biểu mẫu cấp Trường của
UIT](https://portal.uit.edu.vn/van-ban-bieu-mau?issuer=cap_truong). Đợt này chọn 13
nhóm tài liệu ưu tiên trong `UIT_RAG_documents_links.md`. Có 15 PDF vì hai văn bản
mới là quyết định sửa đổi, không chứa toàn văn quy định gốc:

- `1393/QĐ-ĐHCNTT` cập nhật `790/QĐ-ĐHCNTT`.
- `513/QĐ-ĐHCNTT` sửa đổi, bổ sung `412/QĐ-ĐHCNTT`.

Hai văn bản gốc được giữ như thành phần bắt buộc của bộ quy định hiện tại, không
phải phiên bản cũ độc lập để retrieval lựa chọn thay cho bản mới.

## Kết quả tải và kiểm tra

| Chỉ số | Kết quả |
|---|---:|
| Nhóm tài liệu P0 | 13 |
| PDF đã tải | 15 |
| Tổng số trang PDF | 188 |
| Tổng dung lượng | 40.367.168 byte |
| PDF có text layer | 4 |
| PDF scan toàn phần | 11 |
| URL trả đúng PDF | 15/15 |
| PDF mở được bằng PyMuPDF | 15/15 |
| File có SHA-256 trong manifest | 15/15 |

File được lưu cục bộ tại `data/raw/uit/p0/`. Metadata, URL, hash, số trang và kết
quả phân loại nằm trong `data/manifests/documents.csv`.

## Chính sách chọn phiên bản

1. Chỉ chọn bản mới nhất đang được Portal UIT liệt kê trong từng nhóm tài liệu.
2. Không suy ra trạng thái `active` chỉ từ năm ban hành hoặc vị trí trên Portal;
   `legal_status` giữ là `unknown` cho đến khi có bằng chứng trực tiếp.
3. Nếu bản mới chỉ sửa đổi/bổ sung một phần, giữ cả văn bản gốc và amendment rồi
   buộc retrieval/context builder đưa quan hệ này vào xử lý.
4. Văn bản mới theo khóa không tự thay thế văn bản của khóa cũ. Ví dụ,
   `956/QĐ-ĐHCNTT` nêu rõ chỉ áp dụng bắt buộc từ khóa tuyển sinh 2026, năm học
   2026-2027. Corpus hiện chỉ hỗ trợ chuẩn ngoại ngữ cho phạm vi đó; không dùng nó
   để trả lời cho khóa trước.
5. `43/TB-ĐHCNTT` được giữ vì Portal liệt kê trong nhóm học phí gia hạn nhưng bảng
   hỗ trợ lịch2012–2019, chưa xác minh hiện hành. M2 đã mở technicalallowlist15;
   filters hiện ởdocument level và optional, chưa tự chặn mọi câu hỏi chung/phạm vi
   khác. M2 wrong-cohortM204 làfailure; T3.1 focus explicitreviewedrow/cohort/duration
   đã loạiwrongrows nhưng modelsource-ID errors còn, chưa auto-clarification mọiscope.

## Nguồn và quyền phân phối

- Nguồn ưu tiên: `portal.uit.edu.vn`.
- Trang Portal hiển thị thông báo: "Bản quyền thuộc về Trường Đại học Công nghệ
  Thông tin".
- Chưa tìm thấy giấy phép cho phép tái phân phối các PDF.
- Vì vậy PDF chỉ được tải cục bộ để phát triển. Repository portfolio công khai nên
  chia sẻ manifest và script tải, không commit bản sao PDF khi chưa có cho phép.
- `data/raw/` được thêm vào `.gitignore` để giảm rủi ro đưa tài liệu lên Git ngoài ý
  muốn.

## Chất lượng tài liệu

Kiểm kê T1.2: mười một trong mười lăm PDF không có text layer; lúc đó chưa có OCR.
T2.2 đã cài Tesseract5.5.2 và preparation toàn corpus: 135 OCR/53 native pages.
1393 được post-edit và review theo hash, hiện ready/full. Mười scan khác có candidate
OCR nhưng chưa đủ page review nên vẫn bị chặn; không coi confidence là accuracy.

Rà soát T1.4 phát hiện `43/TB-ĐHCNTT` có text layer nhưng encoding font nhúng làm
text tiếng Việt bị garbled. Vì vậy chỉ ba tài liệu `159/QĐ-ĐHCNTT`,
`790/QĐ-ĐHCNTT` và `956/QĐ-ĐHCNTT` sẵn sàng cho retrieval baseline. Văn bản 43
phải OCR hoặc reparse và kiểm tra lại, dù manifest vẫn ghi `pdf_type=text` để phản ánh
đặc tính kỹ thuật của file.

Các trang bảng/lưu đồ đã xác minh trên bốn PDF có text:

| Văn bản | Trang PDF có bảng/lưu đồ đã thấy |
|---|---|
| 159/QĐ-ĐHCNTT | 9-11, lưu đồ quy trình KLTN |
| 43/TB-ĐHCNTT | 1-2, bảng hệ số và khóa tuyển |
| 790/QĐ-ĐHCNTT | 3 và 18, bảng từ viết tắt và thang điểm |
| 956/QĐ-ĐHCNTT | 3, 6-7, 9-10, các bảng chương trình/chứng chỉ |

Trang bảng của 11 PDF scan được đánh dấu `unknown_scan_requires_review`; ingestion
không được coi chúng là nội dung đã kiểm tra cho đến khi OCR và rà soát hình ảnh.
Kết quả chi tiết của 20 chunk mẫu nằm tại `docs/ingestion-baseline-review.md`.
Snapshot T2.2: 4 nguồn ready (1393/159/790/956), 97 chunk. 159/790/956 là partial vì
layout/TOC excluded; 43 đã OCR nhưng chưa publication do table mapping. Kết quả và
review32 chunk: `docs/structure-ocr-review.md` / `data/manifests/page_reviews.csv`.

## Metadata có bằng chứng trực tiếp

- `790/QĐ-ĐHCNTT`: hiệu lực từ học kỳ 1 năm học 2022-2023.
- `1393/QĐ-ĐHCNTT`: có hiệu lực từ ngày ký 2023-12-29 và cập nhật Quy chế 790.
- `159/QĐ-ĐHCNTT`: có hiệu lực từ ngày ký 2024-03-05.
- `513/QĐ-ĐHCNTT`: có hiệu lực từ ngày ký 2026-05-08 và sửa đổi Quy định 412.
- `956/QĐ-ĐHCNTT`: có hiệu lực từ ngày ký 2026-08-10; áp dụng bắt buộc từ khóa
  tuyển sinh 2026, tổ chức đào tạo từ năm học 2026-2027.

Các văn bản còn lại để trống `effective_from`. Ngày trong tên file được ghi là
`issued_date`, không tự chuyển thành bằng chứng về hiệu lực.

Snapshot M2 2026-10-09:15 ready/307 chunk;0 pending pages.133 pages của11 nguồn
chưa publication đã được assistant so raster/text, post-edit hoặc loại scope rõ.
`source_metadata_reviews.csv` bind sourceSHA, bổ sung112/277/308/697/803/832/894
startfromsignature và851 explicit01September2024. Loader overlay review đúnghash;
manifest gốc vẫn giữ lịch sử kiểm kê.308 bỏ cohort2025-only không có evidence,
277 thêm from2024.43 supportedtable range2012–2019. Tất cả legal_status unknown.

112 TOC/appendix ghi2023 khác main2024;697 appendices ghi kỳ2023-2024/2024-2025;
308 priorityformula có internalcrossreference bất thường. Giữ sourceinconsistency
trong notes, không sửa thành một kết luận pháp lý. 697 ghi replaces244 và894
replaces172; hai văn bản thay thế đó không nằm trong corpus hiện tại.

### T3.1 — Ngày ban hành và freshness checkpoint

`document_versions.csv` bind15 issued_dates/signature witnesses vớisourceSHA;
`document_relations.csv` bind1393/513 affectedclause maps và697/894 replacement
witnesses vớiapprovedchunk contentSHA, targetSHA khi target cótrongcorpus.
Review stale khôngđược gánquan hệ; dates/relations refresh quaunchanged lifecycle.
Rulelatest chỉ dựa verifiedsuccessors/caller scope/historicalcutoff, khôngcoi
mọi văn bản mới hơn làthay thế. Baseunmodifiedparts giữamendmentevidence trongcontext.

Ngày09October2026 re-fetch15 PDFs vàhaiPortalpublicpages:15registeredattachments
vẫnlisted, byteskhớphashesđợt05October2026. `source_freshness_checks.csv` lưuUTC
checked_at/indexhashes/attachmentgroups. Nhómngoạingữ gồm956 và13filekhác códateslisted
cũ hơn; khôngsuy quan hệthay thế/phạmvi từfilename. Twoamendmentgroups vẫn790+1393/412+513.
Đối chiếu listing cácP0groups khôngthấy attachmentmới hơn thayselected tại checkpoint.

`check_source_freshness.py` có thểchạy lại; attachmentdates/relations phải review
khi nguồnthay đổi, khôngauto-infer từfilename. Source changed/notlisted được đưa
vàometadata refresh để chặncurrentanswers. APItrảissued/latestissued/sourcechecked
provenance vàwarning scope; khônglivecheck mỗirequest hoặc tựlegal_status active.
Signature dates khác effective dates;851 vẫnissued14August/effective01September2024.

## Ánh xạ câu hỏi mẫu

Ánh xạ chi tiết được lưu trong `data/manifests/question_sources.csv`. Đây là ánh xạ
nguồn dự kiến, chưa thay cho nhãn evidence theo trang/chunk ở giai đoạn evaluation.

| Câu | Nguồn chính | Hành vi cần có |
|---|---|---|
| Q01-Q02: học lại/cải thiện | 790 + amendment 1393 | Trả lời có citation |
| Q03-Q04: cảnh báo/buộc thôi học | 790, 832, 803 | Đối chiếu quy chế và quy trình |
| Q05: điều kiện tốt nghiệp | 790, 956, 894 | Hỏi khóa/chương trình trước |
| Q06: nợ học phí và tốt nghiệp | 790 | Trả lời có citation |
| Q07: tạm dừng học tập | 790 | Trả lời có citation |
| Q08: quay lại sau bảo lưu | 790, 803 | Có thể thiếu chi tiết thủ tục |
| Q09: quy định theo khóa | 790, 1393, 956, 112 | `needs_clarification` |
| Q10: khác biệt giữa văn bản | base + amendment liên quan | Không tự kết luận khi thiếu metadata |

## Giới hạn còn lại

T3.2 thêm request-scoped passage IDs vàUnicodeoffset/textSHA từapprovedchunk,
backend dựngnguyênvăn/citation. Date/source/latest metadata guards giữ nguyên.
Literal table row/phạmvi/chươngtrình vàcompleteconditions đượcreview trong
`docs/passage-citation-review.md`; firststage/generatedIDs khôngtự xácnhậnlegalactive.

- Review source do assistant, chưa independent human.15ready là supported scope;
 45 excluded pages và832 omitteddiagramregions không có trong evidence hỗ trợ.
- Chưa xác minh liệu có văn bản mới hơn ở nguồn ngoài danh mục Portal cấp Trường,
  đặc biệt với tuyển sinh và thông báo học phí.
- Chưa có giấy phép tái phân phối PDF.
- Corpus đạtM2 technical ingest/retrieval/filter/development; answer quality còn hạn chế.
  Xem `docs/m2-corpus-review.md` và publication snapshot để biết coverage từng nguồn.
