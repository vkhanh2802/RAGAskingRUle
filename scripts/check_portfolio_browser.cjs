/* Optional browser media/deck checks. No API/model requests. */
const { chromium } = require('playwright');
const AxeBuilder = require('@axe-core/playwright').default;
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const outputDir = process.env.PORTFOLIO_QA_OUTPUT;
const root = path.resolve(__dirname, '..');
const summary = process.env.PORTFOLIO_QA_SUMMARY;
const checks = [];
const check = (name, condition) => { assert.ok(condition, name); checks.push(name); };

async function main() {
  assert.ok(outputDir && fs.existsSync(path.dirname(outputDir)), 'new ignored QA directory under existing parent');
  assert.ok(path.resolve(outputDir).startsWith(path.join(root, 'data', 'processed') + path.sep));
  fs.mkdirSync(outputDir);
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  let page;
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    page = await context.newPage();
    const errors = [], network = [];
    page.on('pageerror', error => errors.push(error.name));
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    const deck = pathToFileURL(path.join(root, 'docs/portfolio.html')).href;
    await page.goto(deck);
    check('initial intro/counter', await page.locator('#intro').isVisible() && await page.locator('#counter').textContent() === '1 / 5');
    check('previous disabled on first slide', await page.locator('#previous').isDisabled());
    await page.keyboard.press('ArrowRight');
    await page.waitForURL('**#contract');
    await page.locator('#contract').waitFor({ state: 'visible' });
    check('keyboard ArrowRight changes slide', await page.locator('#contract').isVisible());
    await page.keyboard.press('ArrowLeft');
    await page.waitForURL('**#intro');
    await page.locator('#intro').waitFor({ state: 'visible' });
    check('keyboard ArrowLeft changes slide', await page.locator('#intro').isVisible());
    for (const id of ['intro', 'contract', 'architecture', 'benchmark', 'limits']) {
      await page.goto(deck + '#' + id);
      check(`${id} only one visible slide`, await page.locator('.slide:not([hidden])').count() === 1 && await page.locator('#' + id).isVisible());
      const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
      check(`${id} automated WCAG A/AA scan`, axe.violations.length === 0);
      await page.screenshot({ path: path.join(outputDir, `${id}-desktop.png`) });
    }
    check('next disabled on last slide', await page.locator('#next').isDisabled());
    await page.setViewportSize({ width: 375, height: 812 });
    for (const id of ['intro', 'architecture', 'benchmark']) {
      await page.goto(deck + '#' + id);
      check(`${id} mobile no horizontal overflow`, await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(outputDir, `${id}-mobile.png`), fullPage: true });
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(pathToFileURL(path.join(root, 'docs/assets/regularag-demo.mp4')).href);
    await page.waitForSelector('video');
    await page.evaluate(async () => { const video = document.querySelector('video'); video.muted = true; await video.play(); });
    await page.waitForFunction(() => document.querySelector('video').currentTime > 2);
    const video = await page.evaluate(() => {
      const element = document.querySelector('video');
      return { duration: element.duration, width: element.videoWidth, height: element.videoHeight, error: element.error?.code || null };
    });
    check('actual HTML5 MP4 playback/duration/dimensions/no error', video.duration >= 180 && video.duration <= 300 && video.width === 1440 && video.height === 900 && video.error === null);
    await page.evaluate(() => { document.querySelector('video').currentTime = 114; });
    await page.waitForFunction(() => document.querySelector('video').currentTime >= 114);
    await page.screenshot({ path: path.join(outputDir, 'mp4-playback.png') });
    check('offline deck/media no HTTP/model calls', network.length === 0);
    check('no uncaught page errors', errors.length === 0);
    const result = { schema_version: 'portfolio-browser-v1', passed: true,
      checked_at: new Date().toISOString(), browser_channel: 'msedge', browser_version: browser.version(),
      assertions: checks, video, new_model_inference_requests: 0, new_held_out_inference_requests: 0,
      conditions: 'Offline desktop/mobile/keyboard/automated accessibility and real HTML5 media playback; not human usability/presentation assessment.' };
    fs.writeFileSync(summary || path.join(outputDir, 'browser-checks.json'), JSON.stringify(result, null, 2) + '\n', { flag: 'wx' });
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    if (page) await page.screenshot({ path: path.join(outputDir, 'failed-check.png') });
    fs.writeFileSync(path.join(outputDir, 'failed-check.json'), JSON.stringify({
      passed: false, failed_check: error.message, assertions: checks,
      new_model_inference_requests: 0, new_held_out_inference_requests: 0,
    }, null, 2), { flag: 'wx' });
    throw error;
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.name + ': ' + error.message); process.exitCode = 1; });
