# Quy ước làm việc

- Theo yêu cầu người dùng ngày 2026-10-10, sau mỗi bước trong kế hoạch được thực hiện
  và kiểm chứng hoàn tất, tạo một Git commit cho các thay đổi thuộc bước đó, rồi báo
  mã commit cùng kết quả. Chưa hoàn tất hoặc còn kiểm chứng thất bại thì chưa commit.
- Cập nhật `docs/progress.md` và `docs/handoff.md` khi chốt bước. Dùng các trạng thái
  và tiêu chí nghiệm thu trong `RegulaRAG-Project-Plan.md`.
- Chạy trong Conda environment `ragschool` (Python 3.12), kiểm tra Ruff và các tests
  phù hợp. PostgreSQL integration tests dùng schema riêng và
  `REGULARAG_RUN_DB_TESTS=1`.
- Chỉ stage file thuộc phạm vi công việc; giữ `.env`, PDF raw, toàn văn/OCR,
  artifacts xử lý và model traces ngoài Git theo `.gitignore`.
- Giữ source/hash/quality/filter/latest guards và frozen development evidence.
  Lưu cả kết quả thất bại; không đổi gold binding để làm evaluation đạt.
