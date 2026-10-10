# T5.1 early — Web demo và manual-test guide

Ngày2026-10-10. Theo yêu cầu người dùng, đưa T5.1 lên trước T4.2 để test thủ công.
M3 đã đạt; UI hiện dùng baseline backend, tự lấy defaults/catalog khi load. M4 còn pending.

## Thiết kế / implementation

- Dùng UI/UX Pro Max: verified design query `education knowledge search calm` chọn
  Knowledge Base/Documentation + FAQ/Documentation + Minimalism & Swiss Style,
  slate/blue/light palette, readable hierarchy/visible focus/reduced motion.
- Persisted `design-system/regularag/MASTER.md`, page override `pages/demo.md`.
  Grid/semantic token guidance từ HTML/Tailwind search áp bằngnativeCSS; loading
  guidance từ UX search. Local system/Vietnamese font fallback, không CDN/font fetch.
- FastAPI `/` serve HTML, `/assets` nativeCSS/ESmodules/SVG, same-origin `/api/v1/ask`.
  Không frontend build/runtime dependencies mới; Python dependency lock70 giữ nguyên.
- Catalogue `/api/v1/demo/catalog` chỉ publicmanifest fields/allowlist/defaults, không
  localpaths/rawPDF/modeltrace; không loadmodels/query heldout. Static mount chỉ webassets.
- Ô question, explicit scope fields, exactdomain/documentIDs/topk/mode,4devpresets.
- Loading/error/elapsedtime, statusclarify/insufficient rõ, preservedquery scope reply,
  actual backend text/citation buttons, sourcepage/excerpt/fullchunk/metadata/warnings.
- Source rendering chỉtextnodes; unsafeURL không trởthành link, SIDs không có trong
  registryresponse không tạo citation button. Khôngclientqueryrewrite/relaxfilter/confidence meter.
- Feedback session-local vàJSON exportthực; không giả đã persist lênserver.
- Dừngchờ làclientabort, không tuyênbố huỷPythoninference; late response không override UI.

## Kiểm chứng

- **303pytest pass** (191unit/112DBintegration, schemasriêng),1knownTestClient warning.
 80.64s ởfullsuite; Ruff vàlocked70/pipcheck pass.
- **12Node contract tests pass**: optionalfields khôngtự thêmfilter, integer/date typing,
  old-onlyIDs, sourceURL protocols, errors/inputlimits.
- MicrosoftEdge headless/Playwright fixture QA: **27 assertions**, loading/3status/
  scope reply/catalogdialog/Escape/citationfocus/feedback/export/network/503/abort/
  stale response/XSS/safeURLs/responsive/reducedmotion.
- Axe-core WCAG2A/2AA scans initial/result:0violations; đây là automated subset,
  không phải chứng nhận accessibility đầyđủ. Screenshots được xem desktop/375mobile;
  nohorizontaloverflow ở375×812/812×375/768×1024.
- Real browser +actualDB/E5/CE/Qwen: **18 assertions /5requests** (3answered,
  1clarification,1correctstale-filterabstention). Hè cap12 từ1393; scopeCTA reply
  cap16/IEL05;851 literal01September2024;790onlyfilter kept/latestexcluded beforegeneration.
  Firstask latency~24.4s ởlượt này; không dùng5cases làmperformance/heldoutaccuracy benchmark.
- Windows MIME registry banđầu map `.mjs`→text/plain, gâymoduleloadfail. `DemoStaticFiles`
  áp text/javascriptapp-local; testheaders/browserrerun đạt. Failedpilot giữsummary riêng.
- Dataset100SHA `d577dcde2469cdb1650b4e7b1164e520afc5037d6668fe1b5eb06c7f98946f0c`
  rechecked; legacy30/19 vàcorpus/gold unchanged.0heldout RAGinference.

QA tooling Playwright/axe cài tạm ngoài repo tại approvedTemp; không bắt user cài để
chạyUI. Reports `data/manifests/demo_ui_*_review.json`, `demo_dataset_integrity.json`;
screenshots/rawrealresponses/JSON export trongignored `data/processed/demo-ui-*/`.

Reproduce QA nếu Node +optionalPlaywright/axe tooling đã có:

```powershell
node --test tests/ui/contract.test.mjs
python scripts/check_demo.py --output-dir data/processed/demo-ui-new --summary data/manifests/demo_ui_new_review.json
python scripts/check_demo.py --real --output-dir data/processed/demo-ui-real-new --summary data/manifests/demo_ui_real_new_review.json
```

Tooling resolvequaNODE_PATH nếuinstalled temp. `check_demo.py` sởhữuserverport8767 và
tựstop sauQA; không ngắtservercủangườidùng. Run UI/teststeps tại `docs/demo-guide.md`.
T5.1 đạt UItechnical/manualtest flow; M4config/benchmark vàM5packaging cònpending.
