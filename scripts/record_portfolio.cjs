/* Optional media tooling from NODE_PATH: Playwright + axe; never intercept model responses. */
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { createHash } = require('node:crypto');

const baseUrl = process.env.DEMO_BASE_URL || 'http://127.0.0.1:8001';
const outputDir = path.resolve(process.env.RECORD_OUTPUT_DIR || 'data/processed/t5-4-demo-v1');
const root = path.resolve(__dirname, '..');
const hash = value => createHash('sha256').update(value).digest('hex');
const load = file => JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
const checkNames = [], cases = [], scenes = [], errors = [];
const check = (name, condition) => { assert.ok(condition, name); checkNames.push(name); };
const evidence = load('data/evaluation/v1/evidence.json');
const questions = load('data/evaluation/v1/questions.json');
const question = id => {
  const item = questions.find(row => row.question_id === id);
  assert.ok(item && item.split === 'development', 'record only known development cases');
  return item;
};
const publicExcerpts = ['class_size', 'summer'].map(id => evidence.find(row => row.evidence_id === id));
const allowedText = publicExcerpts.map(row => row.excerpt).join('\n');
const bindings = [
  'data/evaluation/v1/questions.json', 'data/evaluation/v1/evidence.json',
  'data/evaluation/v1/freeze.json', 'configs/rag/final.json',
  'data/manifests/t4_4_release_freeze.json',
  'data/manifests/t4_4_release_freeze-held-out-run.json',
  'data/manifests/t4_4_development_metrics.json', 'data/manifests/t4_4_held_out_metrics.json',
];
const inputHashes = Object.fromEntries(bindings.map(file => [file, hash(fs.readFileSync(path.join(root, file)))]));
const sleep = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
let started;
const seconds = () => Math.round((performance.now() - started) / 10) / 100;
function scene(id, title) { scenes.push({ id, title, start_seconds: seconds() }); }

async function caption(page, title, text) {
  await page.evaluate(({ title, text }) => {
    let panel = document.getElementById('portfolio-caption');
    if (!panel) {
      panel = document.createElement('aside');
      panel.id = 'portfolio-caption';
      panel.setAttribute('aria-label', 'Chú thích video production');
      Object.assign(panel.style, {
        position: 'fixed', bottom: '0', left: '0', right: '0', zIndex: '1000',
        background: '#fff', borderTop: '3px solid #2563eb', padding: '16px 36px',
        boxShadow: '0 -8px 24px #1e293b18', color: '#1e293b', pointerEvents: 'none',
        font: '23px/1.45 "Segoe UI", Arial, sans-serif',
      });
      document.body.append(panel);
      document.body.style.paddingBottom = '150px';
    }
    panel.replaceChildren();
    const heading = document.createElement('strong');
    heading.textContent = title; heading.style.color = '#1d4ed8';
    const body = document.createElement('div'); body.textContent = text;
    panel.append(heading, body);
  }, { title, text });
}

async function snapshot(page, file) {
  await page.evaluate(() => { const panel = document.getElementById('portfolio-caption'); if (panel) panel.hidden = true; });
  await page.screenshot({ path: path.join(outputDir, file) });
  await page.evaluate(() => { const panel = document.getElementById('portfolio-caption'); if (panel) panel.hidden = false; });
}

async function auditAxe(page, name) {
  const scan = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
  fs.writeFileSync(path.join(outputDir, `${name}-axe.json`), JSON.stringify(scan.violations, null, 2), { flag: 'wx' });
  check(`${name} automated WCAG A/AA scan`, scan.violations.length === 0);
}

async function submit(page, id, expected) {
  const began = performance.now();
  const pending = page.waitForResponse(response => response.url() === `${baseUrl}/api/v1/ask`
    && response.request().method() === 'POST', { timeout: 180000 });
  await page.locator('#submit-button').click();
  const response = await pending;
  const body = await response.json();
  fs.writeFileSync(path.join(outputDir, `${id}-response.json`), JSON.stringify(body, null, 2), { flag: 'wx' });
  await page.waitForFunction(() => document.querySelector('#result-panel').getAttribute('aria-busy') === 'false');
  const request = response.request().postDataJSON();
  const requestId = response.headers()['x-request-id'];
  const row = {
    case_id: id, http_status: response.status(), status: body.status,
    request_id: requestId, failure_reason: body.failure_reason,
    elapsed_ms: Math.round(performance.now() - began), response_sha256: hash(JSON.stringify(body)),
    source_spans: body.evidence_passages.filter(p => p.cited).map(p => ({
      passage_id: p.passage_id, source_id: p.source_id, chunk_id: p.chunk_id,
      char_start: p.char_start, char_end: p.char_end, text_sha256: p.text_sha256,
    })),
  };
  cases.push(row);
  check(`${id} live HTTP200/expected status`, response.status() === 200 && body.status === expected);
  check(`${id} header/body request ID`, requestId === body.request_id && /^[a-f0-9-]{36}$/.test(requestId));
  check(`${id} final hybrid/top4 requested`, request.top_k === 4 && request.retrieval_mode === 'hybrid');
  if (expected === 'answered') {
    const passages = body.evidence_passages.filter(p => p.cited);
    check(`${id} cited passages present`, passages.length > 0);
    for (const p of passages) {
      const source = body.sources.find(s => s.source_id === p.source_id);
      check(`${id} ${p.passage_id} original Unicode range/SHA`, source?.cited
        && source.chunk_id === p.chunk_id
        && Array.from(source.excerpt).slice(p.char_start, p.char_end).join('') === p.text
        && hash(p.text) === p.text_sha256);
      check(`${id} ${p.passage_id} bounded already-public excerpt`, p.text.length <= 450
        && p.chunk_id === publicExcerpts[0].chunk_id && allowedText.includes(p.text));
    }
    check(`${id} backend exact quoted rendering`, body.answer === passages.map(p => `“${p.text}” [${p.source_id}]`).join('\n\n'));
  } else check(`${id} no invented citation`, body.evidence_passages.every(p => !p.cited)
    && await page.locator('.citation-button').count() === 0);
  check(`${id} full chunk/provenance details remain closed`, await page.locator('#source-list .source-details[open]').count() === 0);
  return body;
}

async function main() {
  assert.ok(['127.0.0.1', 'localhost'].includes(new URL(baseUrl).hostname), 'record local operator deployment only');
  assert.ok(outputDir.startsWith(path.join(root, 'data', 'processed') + path.sep), 'raw footage under ignored data/processed');
  assert.ok(fs.existsSync(path.dirname(outputDir)), 'recording parent must exist');
  fs.mkdirSync(outputDir); // Refuse to overwrite a previous attempt, including failed runs.
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  let context, page;
  try {
    context = await browser.newContext({ viewport: { width: 1440, height: 900 },
      recordVideo: { dir: outputDir, size: { width: 1440, height: 900 } }, reducedMotion: 'reduce' });
    page = await context.newPage();
    const video = page.video();
    page.on('pageerror', error => errors.push(error.name));
    const deck = pathToFileURL(path.join(root, 'docs', 'portfolio.html')).href;
    started = performance.now();
    scene('intro', 'Bài toán và phạm vi');
    await page.goto(deck + '#intro');
    await auditAxe(page, 'intro');
    await sleep(18000);

    scene('workspace', 'UI thực tế / local development');
    await page.goto(baseUrl, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-preset=summer]');
    const catalog = await (await page.request.get(baseUrl + '/api/v1/demo/catalog')).json();
    check('live final pipeline/catalog15', catalog.pipeline_version === 'rag-obligation-support-v3' && catalog.documents.length === 15);
    check('UI backend-default top4', await page.locator('#top-k').inputValue() === '4');
    await snapshot(page, 'demo-workspace.png');
    await caption(page, '01 / UI thực tế · local development controls', 'Câu hỏi tiếng Việt + scope/filter tường minh. Kết quả và bằng chứng hiển thị trong cùng native FastAPI UI.');
    await sleep(14000);

    scene('simple', 'Câu đơn giản: học kỳ hè');
    await page.locator('#question').fill('Theo1393 học kỳ hè tối đa bao nhiêu tín chỉ?');
    await caption(page, '02 / Câu đơn giản · học kỳ hè theo 1393', 'Bấm Tra cứu bằng chứng và chờ CPU inference thật. Footage không cắt thời gian loading; không là một benchmark mới.');
    const simple = await submit(page, 'DEV-SUMMER', 'answered');
    check('simple summer12/no small classes', simple.answer.includes('12 tín chỉ') && simple.answer.includes('không mở lớp sĩ số ít'));
    await page.locator('#result-panel').scrollIntoViewIfNeeded();
    await caption(page, '02 / Đọc kết quả cùng điều kiện', 'Hè tối đa 12 tín chỉ; đọc cả điều kiện đủ sĩ số. Backend dựng nguyên văn từ passage đã kiểm offset/SHA.');
    await sleep(12000);

    scene('source', 'Mở citation tới nguồn và trang');
    const firstId = simple.evidence_passages.find(p => p.cited).source_id;
    await page.locator('.citation-button').first().click();
    check('citation opens matching source', await page.locator(`#source-${firstId}`).evaluate(el => el.open));
    check('official source URL present', (await page.locator(`#source-${firstId} .source-link`).getAttribute('href')).startsWith('https://portal.uit.edu.vn/'));
    await caption(page, '03 / Click citation → mở đúng nguồn', 'Đoạn đã dùng, 1393/QĐ-ĐHCNTT, trang PDF và URL chính thức. Không mở toàn PDF/chunk trong video; pháp lý hiện hành chưa xác minh.');
    await sleep(18000);

    scene('multi', 'D31: hai nghĩa vụ / hai điều khoản');
    const multiCase = question('D31');
    await page.locator('#filter-panel').evaluate(el => { el.open = true; });
    await page.locator('[name=document-id][value=uit_1393_2023]').check();
    await page.locator('#filter-panel').evaluate(el => { el.open = false; });
    await page.locator('#question').fill(multiCase.question);
    await caption(page, '04 / D31 · câu cần nhiều điều khoản', 'Hỏi đồng thời cap tín chỉ hè và sĩ số lớp đại cương/cơ sở ngành chung toàn Trường. Chỉ dùng văn bản 1393 đã chọn.');
    const multi = await submit(page, 'D31', multiCase.expected_status);
    check('D31 both facts and conditions', multi.answer.includes('12 tín chỉ') && multi.answer.includes('70 sinh viên') && multi.answer.includes('không mở lớp sĩ số ít'));
    check('D31 explicit caller source retained', multi.applied_filters.document_ids.join() === 'uit_1393_2023');
    await page.locator('#result-panel').scrollIntoViewIfNeeded();
    await caption(page, '04 / Hai phần cần có đủ', 'Hè ≤12 tín chỉ và không mở lớp ít sĩ số; nhóm đại cương/cơ sở ngành chung toàn Trường ≥70 sinh viên. Đây là case development đã biết.');
    await sleep(14000);
    await snapshot(page, 'demo-answer.png');
    await page.locator('.citation-button').last().click();
    await auditAxe(page, 'multi');
    await snapshot(page, 'demo-source.png');
    await sleep(9000);

    scene('no-answer', 'D46: văn bản không có bằng chứng');
    const noAnswerCase = question('D46');
    await page.locator('#filter-panel').evaluate(el => { el.open = true; });
    await page.locator('[name=document-id][value=uit_1393_2023]').uncheck();
    await page.locator('#filter-panel').evaluate(el => { el.open = false; });
    await page.locator('#question').fill(noAnswerCase.question);
    await caption(page, '05 / D46 · corpus không có văn bản 99999', 'Không đoán thời hạn từ một nguồn gần chủ đề. Known guard trả Chưa đủ bằng chứng; không chứng minh từ chối tổng quát.');
    await submit(page, 'D46', noAnswerCase.expected_status);
    await page.locator('#result-panel').scrollIntoViewIfNeeded();
    await auditAxe(page, 'no-answer');
    await snapshot(page, 'demo-no-answer.png');
    await sleep(20000);

    scene('architecture', 'Kiến trúc thực tế');
    await page.goto(deck + '#architecture');
    await auditAxe(page, 'architecture');
    await caption(page, '06 / Source-bound pipeline', 'Approved source/hash → E5 + FTS/RRF/freshness/CE → registry P# → Qwen selector → backend citation. Request UUID/bounded trace quan sát pipeline.');
    await sleep(28000);

    scene('benchmark', 'M4: kết quả thật và mẫu số');
    await page.goto(deck + '#benchmark');
    await auditAxe(page, 'benchmark');
    await caption(page, '07 / Một lượt test40 sau release freeze', '19/28 đúng đủ ý; 29/108 task-support; 108/108 faithful quotes. Reject0/7, clarification0/20, p95 32.707s. Review bởi assistant, quality targets chưa đạt.');
    await sleep(31000);

    scene('limits', 'Trade-offs và remaining failures');
    await page.goto(deck + '#limits');
    await auditAxe(page, 'limits');
    await caption(page, '08 / Bước tiếp theo cần evidence và test mới', 'Test40 đã exposed. Giữ gold/failures và source freeze; development mới + test độc lập trước prospective quality claim. API0VND, compute/điện chưa định giá.');
    await sleep(Math.max(14000, 240000 - (performance.now() - started)));
    const duration = seconds();
    check('recorded duration 3–5min', duration >= 180 && duration <= 298);
    check('no uncaught page errors', errors.length === 0);
    for (const [file, fingerprint] of Object.entries(inputHashes)) {
      check(`unchanged ${file}`, hash(fs.readFileSync(path.join(root, file))) === fingerprint);
    }
    await context.close();
    const recording = path.basename(await video.path());
    const result = {
      schema_version: 'portfolio-recording-v1', passed: true, base_url: baseUrl,
      recorded_at: new Date().toISOString(), browser_channel: 'msedge',
      browser_version: browser.version(), viewport: { width: 1440, height: 900 },
      raw_video: recording, elapsed_seconds: duration, cases, scenes,
      assertions: checkNames, input_file_sha256: inputHashes,
      new_held_out_inference_requests: 0, live_development_requests: cases.length,
      response_interception: false, voice_over: false, presentation_overlay_only: true,
      published_source_content: 'Only cited short spans contained in existing class_size/summer curated excerpts; full chunk/provenance/PDF panels remain closed.',
      notes: 'Live development browser capture; unchanged inference/config/gold. M4 metrics are historical Windows source-bound measurements, not Linux video timings.',
    };
    fs.writeFileSync(path.join(outputDir, 'recording.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify({ passed: true, live_development_requests: cases.length,
      new_held_out_inference_requests: 0, duration_seconds: duration, assertions: checkNames.length, recording }, null, 2));
  } catch (error) {
    fs.writeFileSync(path.join(outputDir, 'failed-recording.json'), JSON.stringify({
      passed: false, error_type: error.name, failed_check: error.message, cases, scenes, assertions: checkNames,
    }, null, 2), { flag: 'wx' });
    throw error;
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.name + ': ' + error.message); process.exitCode = 1; });
