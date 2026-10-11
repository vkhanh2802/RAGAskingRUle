import test from 'node:test';
import assert from 'node:assert/strict';
import { buildRequest, safeHttpUrl, backendError, PRESETS } from '../../src/regularag/web/contract.mjs';

const defaults = { question: 'Câu hỏi về UIT', topK: '8', mode: 'hybrid', documentIds: [] };
test('blank fields impose no cohort/date/programme filter', () => {
  assert.deepEqual(buildRequest(defaults), { question: defaults.question, top_k: 8, retrieval_mode: 'hybrid' });
});
test('explicit completed semesters including zero are typed without inference', () => {
  assert.equal(buildRequest({ ...defaults, studyProgress: '0' }).scope.study_progress, 0);
  assert.equal(buildRequest({ ...defaults, studyProgress: '3' }).scope.study_progress, 3);
  for (const value of ['true', '-1', '41', '2.5']) assert.throws(() => buildRequest({ ...defaults, studyProgress: value }));
});
test('explicit scope is typed, programme preserved and caller IDs not widened', () => {
  const request = buildRequest({ ...defaults, cohort: '2026', programme: 'cta', audience: 'undergraduate_regular', asOf: '2025-12-01', designYears: '4.5', documentIds: ['uit_790_2022'], domain: 'academic_training' });
  assert.deepEqual(request.scope, { cohort_year: 2026, programmes: ['cta'], applies_to: ['undergraduate_regular'], as_of: '2025-12-01', design_years: 4.5 });
  assert.deepEqual(request.filters, { document_ids: ['uit_790_2022'], domains: ['academic_training'] });
});
test('a year in the question is not silently interpreted as cohort or as_of', () => {
  assert.equal(buildRequest({ ...defaults, question: 'Quyết định ban hành năm2026 có hiệu lực từ khi nào?' }).scope, undefined);
});
for (const value of ['2026.5', 'true', '1979', '2101']) {
  test(`invalid cohort ${value} is rejected`, () => assert.throws(() => buildRequest({ ...defaults, cohort: value })));
}
test('invalid calendar dates are not rolled forward', () => assert.throws(() => buildRequest({ ...defaults, asOf: '2026-02-30' })));
test('old-only preset binds exactly its requested document', () => {
  const preset = PRESETS.find(p => p.id === 'old-filter');
  assert.deepEqual(buildRequest({ ...defaults, question: preset.question, documentIds: preset.documentIds }).filters.document_ids, ['uit_790_2022']);
});
test('untrusted source URL protocols cannot become links', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,hi', 'file:///secret', '/relative']) assert.equal(safeHttpUrl(url), null);
  assert.equal(safeHttpUrl('https://portal.uit.edu.vn/file'), 'https://portal.uit.edu.vn/file');
});
test('question limit and top-k are checked before fetch', () => {
  assert.throws(() => buildRequest({ ...defaults, question: ' ' }));
  assert.throws(() => buildRequest({ ...defaults, question: 'x'.repeat(1001) }));
  assert.throws(() => buildRequest({ ...defaults, topK: 21 }));
});
test('backend validation/unavailability remains distinguishable', () => {
  assert.match(backendError(422, { detail: [{ loc: ['body', 'scope', 'cohort_year'], msg: 'Invalid' }] }), /scope.cohort_year/);
  assert.match(backendError(503, {}), /Database/);
});
