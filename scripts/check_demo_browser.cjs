/* Optional QA tooling: require playwright and @axe-core/playwright from NODE_PATH. */
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const baseUrl = process.env.DEMO_BASE_URL;
const outputDir = process.env.DEMO_OUTPUT_DIR;
const real = process.env.DEMO_REAL === '1';
const gpa = process.env.DEMO_GPA === '1';
const checks = [], records = [], pageErrors = [], consoleErrors = [];
const check = (name, condition) => { assert.ok(condition, name); checks.push(name); };
const synthetic = () => ({
  status: 'answered', answer: '“Học kỳ hè tối đa 12 tín chỉ.” [S1]',
  sources: [{ source_id: 'S1', chunk_id: 'synthetic:ui', document_id: 'synthetic', document_number: '1393/QĐ-ĐHCNTT', title: 'Quy định thử nghiệm giao diện', source_url: 'https://portal.uit.edu.vn/example', pdf_page_start: 1, pdf_page_end: 2, cited: true, excerpt: 'Học kỳ hè tối đa 12 tín chỉ.', article: '1', legal_status: 'unknown', issued_date: '2023-12-29', freshness_status: 'latest_verified_corpus' }],
  evidence_passages: [{ passage_id: 'P1', source_id: 'S1', chunk_id: 'synthetic:ui', text: 'Học kỳ hè tối đa 12 tín chỉ.', char_start: 0, char_end: 28, text_sha256: 'a'.repeat(64), cited: true }],
  input_tokens: 350, selection_attempts: 1, warnings: ['Trạng thái hiệu lực chưa xác minh.'], requested_filters: {}, applied_filters: {}, resolved_scope: {},
});
async function submit(page) {
  const pending = page.waitForResponse(r => r.url().endsWith('/api/v1/ask') && r.request().method() === 'POST', { timeout: 300000 });
  await page.locator('#submit-button').click();
  const response = await pending;
  const body = await response.json();
  await page.waitForFunction(() => document.querySelector('#result-panel').getAttribute('aria-busy') === 'false', { timeout: 300000 });
  return { status: response.status(), body, request: response.request().postDataJSON() };
}
async function main() {
  fs.mkdirSync(outputDir, { recursive: true });
  if (gpa && !real) throw new Error('GPA QA requires the real backend');
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
    const page = await context.newPage();
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
    await page.goto(baseUrl, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-preset=summer]');
    check('Vietnamese document language', await page.locator('html').getAttribute('lang') === 'vi');
    check('four development-only presets', await page.locator('.sample-button').count() === 4);
    check('catalog15', await page.locator('[name=document-id]').count() === 15);
    const initialAxe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    check('initial WCAG A/AA automated scan', initialAxe.violations.length === 0);
    await page.screenshot({ path: path.join(outputDir, 'desktop-empty.png'), fullPage: true });
    await page.locator('#open-catalog').click();
    check('native catalog dialog opens', await page.locator('#catalog-dialog').evaluate(el => el.open));
    await page.keyboard.press('Escape');
    check('Escape closes dialog', !(await page.locator('#catalog-dialog').evaluate(el => el.open)));
    if (real && gpa) {
      const question = 'Nếu điểm trung bình đến hiện tại của tôi >=8.0, tôi sẽ được phép đăng kí bao nhiêu tín chỉ?';
      await page.locator('#question').fill(question);
      let result = await submit(page); records.push({ case: 'gpa-all-sources', ...result });
      const catalog = await (await page.request.get(`${baseUrl}/api/v1/demo/catalog`)).json();
      check('live clause-scoped policy loaded', catalog.pipeline_version === 'rag-clause-scoped-v2' && result.body.freshness_policy === 'clause-scoped-v2');
      check('real GPA cap30 in main semester from790', result.body.status === 'answered' && /30\s*tín chỉ/.test(result.body.answer) && /học kỳ chính/.test(result.body.answer) && !/học kỳ hè/.test(result.body.answer) && result.body.sources.some(s => s.document_id === 'uit_790_2022' && s.cited));
      const source = result.body.sources.find(s => s.cited);
      const [start, end] = source.evidence_char_ranges[0];
      check('actual cited spans stay inside unchanged source view', result.body.evidence_passages.filter(p => p.cited).every(p => p.chunk_id === source.chunk_id && start <= p.char_start && p.char_end <= end && source.excerpt.slice(p.char_start, p.char_end) === p.text));
      await page.locator('.citation-button').first().click();
      check('GPA citation opens source790', await page.locator('#source-S1').evaluate(el => el.open));
      check('unchanged range provenance rendered', (await page.locator('#source-S1').textContent()).includes('Phạm vi bằng chứng không bị sửa đổi'));
      const resultAxe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      check('GPA result WCAG A/AA automated scan', resultAxe.violations.length === 0);
      await page.screenshot({ path: path.join(outputDir, 'desktop-answered.png'), fullPage: true });
      await page.locator('#filter-panel > summary').click();
      await page.locator('[name=document-id][value=uit_790_2022]').check();
      result = await submit(page); records.push({ case: 'gpa-790-only', ...result });
      check('GPA old-only caller filter retained', result.request.filters.document_ids.length === 1 && result.body.applied_filters.document_ids.length === 1 && result.body.applied_filters.document_ids[0] === 'uit_790_2022');
      check('unchanged GPA rule answers even with790-only', result.body.status === 'answered' && /30\s*tín chỉ/.test(result.body.answer) && result.body.sources.every(s => s.document_id === 'uit_790_2022'));
      await page.locator('#question').fill('Theo790 ĐTBC>=8,0 thì học kỳ hè đăng ký tối đa bao nhiêu tín chỉ?');
      result = await submit(page); records.push({ case: 'summer-790-only', ...result });
      check('amended summer still blocks old-only filter', result.body.status === 'insufficient_evidence' && result.body.failure_reason === 'latest_excluded_by_filters' && await page.locator('.citation-button').count() === 0);
      await page.locator('#domain').selectOption('academic_training');
      await page.locator('#question').fill(question);
      result = await submit(page); records.push({ case: 'personal-domain-needs-audience', ...result });
      check('explicit personal training scope still asks for audience', result.body.status === 'needs_clarification' && result.body.clarification.required_fields.includes('applies_to') && await page.locator('#clarification-actions').isVisible());
      await page.locator('#fill-scope').click();
      await page.locator('#audience').selectOption('undergraduate_regular');
      result = await submit(page); records.push({ case: 'personal-domain-scope-reply', ...result });
      check('explicit audience reply preserves query and answers unchanged cap30', result.request.question === question && result.request.scope.applies_to[0] === 'undergraduate_regular' && result.body.status === 'answered' && /30\s*tín chỉ/.test(result.body.answer) && result.body.applied_filters.document_ids[0] === 'uit_790_2022');
    } else if (real) {
      await page.locator('[data-preset=summer]').click();
      let result = await submit(page); records.push({ case: 'summer', ...result });
      check('real cap12 from1393', result.body.status === 'answered' && /12\s*tín chỉ/.test(result.body.answer) && result.body.sources.some(s => s.document_number.startsWith('1393') && s.cited));
      await page.locator('.citation-button').first().click();
      check('citation opens matching source', await page.locator('.source-entry').first().evaluate(el => el.open));
      await page.screenshot({ path: path.join(outputDir, 'desktop-answered.png'), fullPage: true });
      await page.locator('[data-preset=clarify]').click();
      result = await submit(page); records.push({ case: 'clarify', ...result });
      check('real clarification visible', result.body.status === 'needs_clarification' && await page.locator('#clarification-actions').isVisible());
      const original = await page.locator('#question').inputValue();
      await page.locator('#fill-scope').click();
      await page.locator('#cohort').fill('2026');
      await page.locator('#audience').selectOption('undergraduate_regular');
      await page.locator('#programme').selectOption('cta');
      result = await submit(page); records.push({ case: 'scope-reply', ...result });
      check('explicit scope reply uses same question andCTA', result.request.question === original && result.request.scope.programmes[0] === 'cta' && result.body.status === 'answered' && /16\s*tín chỉ/.test(result.body.answer));
      await page.locator('[data-preset=old-filter]').click();
      result = await submit(page); records.push({ case: 'old-filter', ...result });
      check('caller old-only filter retained', result.request.filters.document_ids.length === 1 && result.request.filters.document_ids[0] === 'uit_790_2022' && result.body.applied_filters.document_ids[0] === 'uit_790_2022');
      check('real latest guard abstains', result.body.status === 'insufficient_evidence' && result.body.failure_reason === 'latest_excluded_by_filters');
      await page.locator('[data-preset=effective]').click();
      result = await submit(page); records.push({ case: 'effective', ...result });
      check('real01September effective date', result.body.status === 'answered' && /01\/9\/2024/.test(result.body.answer));
    } else {
      let mode = 'answered'; let seenRequest;
      await page.route('**/api/v1/ask', async route => {
        seenRequest = route.request().postDataJSON();
        const currentMode = mode;
        await new Promise(resolve => setTimeout(resolve, currentMode === 'slow' ? 1500 : 250));
        if (currentMode === 'network') return route.abort('connectionfailed');
        if (currentMode === '503') return route.fulfill({ status: 503, json: { detail: 'Backend unavailable' } });
        const body = synthetic();
        if (currentMode === 'clarify') Object.assign(body, { status: 'needs_clarification', answer: 'Bạn thuộc khóa nào?', sources: [], evidence_passages: [], clarification: { required_fields: ['cohort_year'] } });
        if (currentMode === 'insufficient') Object.assign(body, { status: 'insufficient_evidence', answer: 'Chưa đủ bằng chứng.', sources: [], evidence_passages: [] });
        if (currentMode === 'xss') {
          body.answer = '<img src=x onerror="window.uiXss=1"> [S1] [S99]';
          body.sources[0].title = '<script>window.uiXss=2</script>';
          body.sources[0].source_url = 'javascript:alert(1)';
          body.evidence_passages[0].text = '<svg onload="window.uiXss=3">';
        }
        try { await route.fulfill({ json: body }); } catch (error) { if (currentMode !== 'slow') throw error; }
      });
      await page.locator('[data-preset=summer]').click();
      const pending = submit(page);
      await page.waitForSelector('#loading-state:not([hidden])');
      check('busy/loading without fake percentages', await page.locator('#submit-button').isDisabled() && await page.locator('#result-panel').getAttribute('aria-busy') === 'true');
      await pending;
      check('answer visible', await page.locator('#answer-text').textContent() === '“Học kỳ hè tối đa 12 tín chỉ.” [S1]');
      await page.locator('.citation-button').click();
      check('citation focus target', await page.locator('#source-S1').evaluate(el => el.open));
      await page.locator('[data-feedback=useful]').click();
      check('feedback session-local selected state', await page.locator('[data-feedback=useful]').getAttribute('aria-pressed') === 'true');
      const downloadPromise = page.waitForEvent('download');
      await page.locator('#download-result').click();
      await (await downloadPromise).saveAs(path.join(outputDir, 'export.json'));
      check('JSON export keeps actual request and session feedback', JSON.parse(fs.readFileSync(path.join(outputDir, 'export.json'), 'utf8')).feedback === 'useful');
      mode = 'clarify'; await page.locator('[data-preset=clarify]').click(); await submit(page);
      check('clarification action', await page.locator('#clarification-actions').isVisible());
      const question = await page.locator('#question').inputValue();
      await page.locator('#fill-scope').click(); await page.locator('#cohort').fill('2026'); await page.locator('#programme').selectOption('cta');
      mode = 'answered'; await submit(page);
      check('scope reply preserves query', seenRequest.question === question && seenRequest.scope.cohort_year === 2026 && seenRequest.scope.programmes[0] === 'cta');
      mode = 'insufficient'; await page.locator('[data-preset=old-filter]').click(); await submit(page);
      check('preset resets stale scope and binds old filter', !seenRequest.scope && seenRequest.filters.document_ids[0] === 'uit_790_2022');
      check('insufficient has no fake citation', await page.locator('.citation-button').count() === 0);
      mode = '503'; await submit(page);
      check('503 preserves question and clears old evidence', await page.locator('#question').inputValue() !== '' && await page.locator('.source-entry').count() === 0 && await page.locator('#download-result').isDisabled());
      mode = 'network'; await page.locator('#submit-button').click();
      await page.waitForFunction(() => document.querySelector('#result-panel').getAttribute('aria-busy') === 'false');
      check('network error explains retry', (await page.locator('#answer-text').textContent()).includes('Không kết nối được API'));
      mode = 'slow'; await page.locator('#submit-button').click();
      await page.waitForSelector('#loading-state:not([hidden])');
      await page.locator('#stop-waiting').click();
      await page.waitForFunction(() => document.querySelector('#result-panel').getAttribute('aria-busy') === 'false');
      check('stop waiting is honest and retains query', (await page.locator('#answer-text').textContent()).includes('Backend có thể vẫn đang xử lý') && (await page.locator('#question').inputValue()).length > 0);
      await page.waitForTimeout(1600);
      check('late aborted response cannot overwrite current UI', (await page.locator('#answer-text').textContent()).includes('Đã dừng chờ'));
      mode = 'xss'; await page.locator('[data-preset=summer]').click(); await submit(page);
      check('user/source/model HTML stays text', await page.evaluate(() => !window.uiXss && document.querySelectorAll('#answer-text img, #source-list script, #source-list svg').length === 0));
      check('invalid citation is not clickable and unsafe URL is absent', await page.locator('.citation-button').count() === 1 && await page.locator('#source-list a').count() === 0);
      mode = 'answered'; await submit(page);
      const resultAxe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      check('result WCAG A/AA automated scan', resultAxe.violations.length === 0);
      await page.screenshot({ path: path.join(outputDir, 'desktop-answered.png'), fullPage: true });
    }
    for (const viewport of [{ width: 375, height: 812 }, { width: 812, height: 375 }, { width: 768, height: 1024 }]) {
      await page.setViewportSize(viewport);
      check(`no horizontal page overflow ${viewport.width}x${viewport.height}`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(outputDir, `view-${viewport.width}x${viewport.height}.png`), fullPage: true });
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    check('reduced motion disables smooth scrolling', await page.evaluate(() => getComputedStyle(document.documentElement).scrollBehavior === 'auto'));
    check('no uncaught browser errors', pageErrors.length === 0);
    fs.writeFileSync(path.join(outputDir, 'records.json'), JSON.stringify(records, null, 2));
    fs.writeFileSync(path.join(outputDir, 'browser-report.json'), JSON.stringify({ passed: true, mode: gpa ? 'real-backend-gpa-regression' : real ? 'real-backend-development-presets' : 'isolated-browser-fixtures', assertions: checks, pageErrors, held_out_inference_requests: 0 }, null, 2));
    console.log(JSON.stringify({ passed: true, mode: real ? 'real' : 'fixture', assertion_count: checks.length, real_requests: records.length }));
  } finally { await browser.close(); }
}
main().catch(error => {
  fs.writeFileSync(path.join(outputDir, 'records.json'), JSON.stringify(records, null, 2));
  fs.writeFileSync(path.join(outputDir, 'browser-report.json'), JSON.stringify({ passed: false, completed_assertions: checks, error: error.message, pageErrors, consoleErrors }, null, 2));
  console.error(error); process.exitCode = 1;
});
