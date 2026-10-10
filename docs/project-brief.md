# RegulaRAG - Project brief

## Tóm tắt 60 giây

RegulaRAG là trợ lý tra cứu quy chế dành trước hết cho sinh viên Trường Đại học
Công nghệ Thông tin, Đại học Quốc gia Thành phố Hồ Chí Minh (UIT). Hệ thống tìm
bằng chứng trong các tài liệu chính thức công khai của trường, trả lời bằng tiếng
Việt và đính kèm nguồn, trang PDF cùng đoạn trích để người dùng tự kiểm tra. Bản
MVP tập trung vào các câu hỏi độc lập về học vụ, học lại/cải thiện điểm, cảnh báo
học tập, tốt nghiệp và bảo lưu. Một câu trả lời chỉ được coi là tốt khi giữ đúng
điều kiện, ngưỡng, đối tượng và thời gian áp dụng; nếu bằng chứng thiếu hoặc câu
hỏi chưa rõ phạm vi, hệ thống phải từ chối hoặc hỏi lại thay vì suy đoán.

## Bài toán

Thông tin học vụ thường nằm rải rác trong nhiều PDF, có thể khác nhau theo hệ đào
tạo, khóa tuyển, thời điểm hoặc văn bản sửa đổi. Việc tìm thủ công mất thời gian,
trong khi một câu trả lời nghe hợp lý nhưng dùng sai phiên bản có thể gây hậu quả
cho kế hoạch học tập của sinh viên. RegulaRAG giải quyết phần tra cứu và đối chiếu
bằng một pipeline RAG có provenance từ tài liệu đến đoạn trích và citation.

RegulaRAG là công cụ hỗ trợ tra cứu, không thay thế Phòng Đào tạo hoặc kết luận
hành chính chính thức. Khi các nguồn mâu thuẫn hoặc chưa xác định được hiệu lực,
hệ thống phải trình bày giới hạn và hướng người dùng xác nhận với đơn vị phụ trách.

## Người dùng mục tiêu

- Chính: sinh viên UIT cần tra cứu nhanh quy định áp dụng cho trường hợp của mình.
- Phụ: cố vấn học tập và cán bộ hỗ trợ sinh viên cần tìm lại điều khoản, nguồn và
  trang để đối chiếu.
- Portfolio: nhà tuyển dụng AI Engineer cần kiểm chứng được thiết kế, code,
  evaluation và các quyết định kỹ thuật của dự án.

## Nhóm câu hỏi MVP

1. Đăng ký học phần, học lại và học cải thiện.
2. Đánh giá kết quả học tập, cảnh báo học tập và xử lý học vụ.
3. Điều kiện xét và công nhận tốt nghiệp.
4. Nghỉ học tạm thời, bảo lưu và tiếp tục học.
5. Học phí, miễn giảm hoặc học bổng khi corpus có tài liệu chính thức phù hợp.

## Mười câu hỏi thực tế cần hỗ trợ

Các câu dưới đây là yêu cầu tra cứu dự kiến, chưa phải khẳng định rằng corpus đã
có câu trả lời. T1.2 sẽ gắn từng câu với tài liệu và bằng chứng thực tế.

1. Sinh viên được đăng ký học lại một học phần trong những trường hợp nào?
2. Nếu đã đạt một học phần, sinh viên có được học cải thiện điểm không và kết quả
   nào được dùng để tính điểm?
3. Sinh viên bị cảnh báo học tập khi vi phạm những điều kiện nào?
4. Sau bao nhiêu lần hoặc học kỳ bị cảnh báo thì sinh viên có thể bị buộc thôi học?
5. Điều kiện về số tín chỉ, điểm trung bình và chứng chỉ để được xét tốt nghiệp là
   gì?
6. Sinh viên còn nợ học phí có được xét tốt nghiệp không?
7. Trường hợp nào sinh viên được xin nghỉ học tạm thời và thời gian nghỉ có tính
   vào thời gian đào tạo tối đa không?
8. Sinh viên muốn quay lại học sau thời gian bảo lưu cần thực hiện thủ tục nào?
9. Quy định học vụ nào áp dụng cho sinh viên hệ chính quy thuộc khóa tuyển cụ thể
   của tôi?
10. Nếu hai văn bản quy định khác nhau về cùng một vấn đề, văn bản nào áp dụng cho
    sinh viên thuộc khóa và chương trình của tôi?

## Phạm vi MVP

- Một trường: UIT.
- Khoảng 10-20 tài liệu chính thức, ưu tiên PDF có text; dùng một nhóm nhỏ PDF scan
  để thử OCR.
- Câu hỏi độc lập bằng tiếng Việt.
- Ingestion bằng CLI/script; tìm kiếm dense vector và PostgreSQL full-text search.
- Câu trả lời có source ID, tài liệu, trang PDF và excerpt kiểm tra được.
- Có hành vi `answered`, `insufficient_evidence` và `needs_clarification`.
- API FastAPI và giao diện demo Streamlit, không có tài khoản người dùng.
- Evaluation gồm retrieval, chất lượng câu trả lời, citation, abstention và latency.

## Ngoài MVP

- Nhiều trường đại học hoặc corpus riêng theo từng người dùng.
- Đăng nhập, phân quyền và dữ liệu cá nhân.
- Dashboard quản trị tài liệu đầy đủ.
- Hội thoại nhiều lượt và ghi nhớ dài hạn.
- Tự động kết luận văn bản nào có hiệu lực khi metadata hoặc bằng chứng không rõ.
- OCR diện rộng và hỗ trợ mọi bố cục bảng/phụ lục phức tạp.
- Cam kết tư vấn pháp lý, học vụ hoặc thay thế quyết định chính thức của UIT.

## Tiêu chuẩn của câu trả lời tốt

- Chỉ nêu các phát biểu được context hỗ trợ; không thêm điều kiện từ kiến thức nền.
- Giữ đúng số liệu, ngoại lệ, đối tượng, hệ đào tạo, khóa và thời gian áp dụng.
- Mỗi phát biểu quan trọng có citation hợp lệ và đoạn trích thực sự hỗ trợ nội dung.
- Trang PDF được ghi riêng với số trang in trên tài liệu nếu hai giá trị khác nhau.
- Hỏi lại khi thiếu khóa, hệ đào tạo hoặc thời điểm cần thiết để chọn đúng phạm vi.
- Từ chối có kiểm soát khi corpus không đủ bằng chứng.

## Nguồn lực và ràng buộc

| Hạng mục | Hiện trạng/Quyết định |
|---|---|
| Hệ điều hành | Windows 11 Home Single Language |
| CPU | Intel Core i5-12450HX, 12 logical processors |
| RAM | 11,8 GB khả dụng theo thông tin hệ thống |
| GPU | NVIDIA GeForce RTX 3050 Laptop GPU, 6 GB |
| Python hiện có | 3.14.5; cần kiểm tra tương thích thư viện trước khi khóa môi trường |
| Docker hiện có | Docker 29.7.2 |
| Ngân sách API | 0 VND; ưu tiên local/open-source và free tier |
| Thời gian | Khoảng 10 giờ/tuần |
| Deadline | Chưa có; ước lượng hiện tại 9-12 tuần theo kế hoạch 90-120 giờ |

Hệ quả thiết kế: MVP bắt đầu bằng cấu hình nhẹ và đo được. Model embedding/reranker
phải có thể bật tắt hoặc đổi qua config; không mặc định tải đồng thời nhiều model
lớn vào GPU 6 GB. Python 3.14 có thể chưa được toàn bộ thư viện ML hỗ trợ, nên T1.3
sẽ xác minh và có thể khóa project ở Python 3.11 hoặc 3.12.

## Tiêu chí thành công của T1.1

Trong 60 giây có thể giải thích: sinh viên UIT dùng RegulaRAG để tra cứu quy chế
từ tài liệu chính thức; hệ thống trả lời kèm bằng chứng kiểm tra được và không đoán
khi thiếu dữ liệu. Phạm vi, nhóm câu hỏi, phần ngoài MVP, 10 câu hỏi mẫu, nguồn lực
và kiến trúc ban đầu đều đã được ghi lại. Danh mục tài liệu và hiệu lực văn bản là
đầu ra phải xác minh ở T1.2.
