# T5.4 — video demo và kịch bản quay lại

## Bản đã tạo

- **[MP4 4:00.6](assets/regularag-demo.mp4)**: H.264/yuv420p, 1440×900, 15fps,
  faststart, chú thích tiếng Việt, **không voice-over/audio**.
- [UI workspace](assets/demo-workspace.png), [hai điều khoản/answer](assets/demo-answer.png),
  [sau mở citation/source](assets/demo-source.png), [no-answer](assets/demo-no-answer.png).
- [Offline slides](portfolio.html), [architecture SVG](assets/architecture.svg),
  [interview rehearsal/CV](interview.md), [verification report](portfolio-review.md).

Quay MS Edge headless/Playwright trên Docker deployment localhost8001: continuous
footage, không cắt loading thật. Overlay chỉ là chú thích production, không sửa
query/payload/model output. WebM/raw responses/QA ở ignored
`data/processed/t5-4-demo-v1/`. FFmpeg chỉ transcode H.264/15fps/faststart, không
tăng tốc clip. MP4 1.801.612bytes (~1.8MB).

## Chapters — bám timestamp footage

| Time | Cảnh | Thông điệp |
|---|---|---|
| 0:00 | Bài toán UIT / partial corpus | 15ready/307chunks, điều kiện/amendments, pháp lý hiện hành chưa xác minh |
| 0:19 | Native UI thực tế | Query/scope/filter, local CPU, sources cạnh answer |
| 0:34 | Câu hè đơn giản | “Theo1393 học kỳ hè tối đa bao nhiêu tín chỉ?” → cap12, không lớp ít sĩ số |
| 1:14 | Mở citation | Click `[S1]` tới1393, đoạn dùng/trangPDF1–2/URL nguồn; không mở wholechunk/PDF |
| 1:32 | D31 nhiều điều khoản | Hè12 + no smallclasses **và** min70SV đúng nhóm học chung toànTrường |
| 2:11 | D46 no-answer | Quyết định99999 không có evidence → insufficient, không invented citation |
| 2:34 | Kiến trúc | Approved/hash → E5+FTS/RRF/CE → registry/QwenPIDs → backend citation/trace |
| 3:03 | Benchmark M4 | Dev47/47 vs heldout19/28; faithful108/108 vs support29/108; reject0/7, p9532.707s |
| 3:34–4:00.6 | Trade-offs / remaining failure | Local API0≠free compute; exposed test cần test mới; quality targets chưa đạt |

Exact scene timestamps/media SHA/browser/request IDs/offsets:
[media manifest](../data/manifests/t5_4_portfolio_media.json).
Ảnh answer lấy **actual video frame tại114s** để đọc đủ hai quote; ảnh source là
viewport sau click citation. Đây không phải generated/mock answer screenshot.

### Cách diễn giải demo

Ba request là **known development controls**, không thêm held-out requests. D31
ghép hai điều khoản trong1393; không gọi đó là cross-document benchmark. D46 là
known no-matching-evidence case, không phủ nhận heldout reject0/7.
Live UI elapsed28.016s/15.050s/1.818s là diagnostic trong recording, không thay
CPU Windows M4 timings. Source/legal status/partial coverage vẫn hiển thị.

Cited short spans chỉ thuộc curated `class_size` / `summer` đã public ở
[evidence.json](../data/evaluation/v1/evidence.json). Full chunk/provenance/
responseJSON/PDF panels không mở; full PDFs/OCR/weights/secrets/model traces
giữ ngoài Git.

## Quay lại — optional media tooling

Prerequisites: deployment final config/cache/approved corpus đã ready theo
[README](../README.md), Node + optional Playwright/axe, MS Edge và FFmpeg/FFprobe.
Các media tools không là Python/runtime app dependencies; dùng tooling đã có,
không thêm package vào requirements.lock. Parent `data/processed/` phải tồn tại.

```powershell
conda activate ragschool
$env:NODE_PATH = "$env:LOCALAPPDATA\Temp\opencode\regularag-ui-qa\node_modules"
$env:DEMO_BASE_URL = "http://127.0.0.1:8001"
$env:RECORD_OUTPUT_DIR = "data/processed/<new-demo-attempt>"
node scripts/record_portfolio.cjs
```

Script chỉ chấp nhận localhost/new ignored output directory; dùng exact D31/D46
development questions; kiểm source/offset/SHA/render/conditions/caller filter/
requestID/public short spans, six automated A/AA scans và input hashes. Failed
attempts giữ nguyên; không overwrite hoặc rerun test40. Recording gồm loading,
actual results và static architecture/benchmark slides.

Export lần đầu (targets **phải mới**, không overwrite media/manifest đã phát hành):

```powershell
python scripts/check_portfolio.py --recording data/processed/<new-demo-attempt> --encode --publish-media
python scripts/check_portfolio.py --seal-text-bindings
```

Portfolio revision mới cần versioned asset/manifest paths trong tooling revision
tương ứng; không delete evidence cũ chỉ để command chạy lại.

Kiểm lại bản đã public: không RAG/model calls, không cần raw footage. Với
FFmpeg/FFprobe có trong PATH, command static chạy được ngay trên clone có media:

```powershell
python scripts/check_portfolio.py
$env:PORTFOLIO_QA_OUTPUT = "data/processed/<new-portfolio-browser-check>"
node scripts/check_portfolio_browser.cjs
```

Browser checker mặc định ghi `browser-checks.json` trong new ignored QA directory;
có thể đặt `PORTFOLIO_QA_SUMMARY` tới new ID-only report path để lưu metadata.
Không overwrite report cũ. Static checker không thay manifest/Git.
Checkout reader cho phép **chỉ CRLF/LF khác nhau** ở presentation text inputs,
theo [text bindings](../data/manifests/t5_4_portfolio_text_bindings.json) được seal
từ exact recorded bytes. Original raw hashes và M4 runner/source-freeze guards
giữ nguyên; đây không phải historical inference reproduction.
Human narration/rehearsal hoặc external video hosting không nằm trong automated
checks đã công bố.
