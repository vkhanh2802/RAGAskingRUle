import { PRESETS, STATUS, DOMAINS, buildRequest, safeHttpUrl, backendError } from './contract.mjs';

const $ = id => document.getElementById(id);
let busy = false, activeController = null, lastResult = null, feedback = null, catalog = null;
const node = (tag, text, className) => {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
};
const announce = text => { $('live-status').textContent = text; };
const pretty = value => JSON.stringify(value, null, 2);
const fields = ['cohort', 'audience', 'programme', 'as-of', 'design-years', 'project-type'];
function values() {
  return {
    question: $('question').value, topK: $('top-k').value, mode: $('retrieval-mode').value,
    cohort: $('cohort').value, audience: $('audience').value, programme: $('programme').value,
    asOf: $('as-of').value, designYears: $('design-years').value, projectType: $('project-type').value,
    domain: $('domain').value,
    documentIds: [...document.querySelectorAll('[name=document-id]:checked')].map(input => input.value),
  };
}
function countChars() { $('char-count').textContent = `${$('question').value.length.toLocaleString('vi-VN')} / 1.000`; }
function setBusy(value) {
  busy = value;
  $('result-panel').setAttribute('aria-busy', String(value));
  $('submit-button').disabled = value;
  $('submit-button').querySelector('span').textContent = value ? 'Đang tra cứu…' : 'Tra cứu bằng chứng';
  document.querySelectorAll('#ask-form input, #ask-form select, #ask-form textarea, .sample-button').forEach(el => { el.disabled = value; });
}
function badge(status, text) { $('result-status').className = `status-badge ${status}`; $('result-status').textContent = text; }
function renderAnswer(text, sources) {
  const ids = new Set(sources.map(source => source.source_id));
  const container = $('answer-text');
  container.replaceChildren();
  let cursor = 0;
  for (const match of text.matchAll(/\[(S[1-9]\d*)\]/g)) {
    container.append(document.createTextNode(text.slice(cursor, match.index)));
    if (ids.has(match[1])) {
      const button = node('button', match[0], 'citation-button');
      button.type = 'button'; button.setAttribute('aria-label', `Mở bằng chứng ${match[1]}`);
      button.addEventListener('click', () => {
        const source = document.getElementById(`source-${match[1]}`);
        if (source) {
          source.open = true;
          source.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
          source.querySelector('summary').focus({ preventScroll: true });
        }
      });
      container.append(button);
    } else container.append(document.createTextNode(match[0]));
    cursor = match.index + match[0].length;
  }
  container.append(document.createTextNode(text.slice(cursor)));
}
function definitionList(items) {
  const dl = node('dl');
  items.forEach(([term, value]) => { dl.append(node('dt', term), node('dd', value == null || value === '' ? 'Chưa ghi nhận' : String(value))); });
  return dl;
}
function sourceEntry(source, payload, index) {
  const entry = node('details', undefined, `source-entry ${source.cited ? '' : 'uncited'}`);
  entry.id = `source-${source.source_id}`; entry.open = source.cited && index === 0;
  const summary = node('summary');
  const meta = node('span', undefined, 'source-summary');
  meta.append(node('strong', source.document_number), node('span', `PDF ${source.pdf_page_start}–${source.pdf_page_end} · ${source.cited ? 'Được trích dẫn' : 'Nguồn trong context'}`));
  summary.append(node('span', source.source_id, 'source-id'), meta);
  entry.append(summary, node('p', source.title, 'source-title'));
  const tags = node('div', undefined, 'source-tags');
  tags.append(node('span', source.article ? `Điều ${source.article}` : 'Điều chưa xác định', 'source-tag'));
  tags.append(node('span', source.legal_status === 'unknown' ? 'Hiệu lực chưa xác minh' : source.legal_status, 'source-tag'));
  if (source.omitted_layout_pdf_pages?.length) tags.append(node('span', `Lược layout PDF ${source.omitted_layout_pdf_pages.join(', ')}`, 'source-tag'));
  entry.append(tags);
  const passages = (payload.evidence_passages || []).filter(p => p.source_id === source.source_id && p.cited);
  if (passages.length) {
    entry.append(node('div', 'ĐOẠN ĐÃ DÙNG TRONG CÂU TRẢ LỜI', 'source-excerpt-label'));
    passages.forEach(p => entry.append(node('blockquote', p.text, 'source-excerpt')));
  } else entry.append(node('p', 'Nguồn này nằm trong context; chưa dùng để kết luận câu trả lời.', 'field-hint'));
  const excerpt = node('details', undefined, 'source-details');
  excerpt.append(node('summary', 'Xem toàn bộ chunk đã truy xuất'), node('blockquote', source.excerpt, 'source-excerpt'));
  entry.append(excerpt);
  const technical = node('details', undefined, 'source-details');
  technical.append(node('summary', 'Phiên bản & provenance'), definitionList([
    ['Ngày ban hành', source.issued_date], ['Bản mới nhất trong chuỗi', source.latest_document_number],
    ['Ngày kiểm nguồn', source.source_checked_at], ['Freshness', source.freshness_status],
    ['Chunk ID', source.chunk_id], ['Cohort', source.cohort_scope], ['Ghi chú', source.metadata_note],
    ['Score kind', source.score_kind], ['Raw score', source.score], ['Rerank logit', source.rerank_score],
    ['Phạm vi bằng chứng không bị sửa đổi', source.evidence_char_ranges?.length ? source.evidence_char_ranges.map(([start, end]) => `${start}–${end}`).join(', ') : 'Toàn chunk theo guards'],
    ...passages.map(p => [`${p.passage_id} · offsets ${p.char_start}–${p.char_end}`, p.text_sha256]),
  ]));
  entry.append(technical);
  const url = safeHttpUrl(source.source_url);
  if (url) {
    const link = node('a', 'Mở tài liệu nguồn ↗', 'source-link');
    link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer';
    entry.append(link);
  }
  return entry;
}
function renderSources(payload) {
  const sources = [...payload.sources].sort((a, b) => Number(b.cited) - Number(a.cited));
  $('source-count').textContent = sources.length;
  const cited = sources.filter(source => source.cited).length;
  $('source-description').textContent = sources.length ? `${cited} nguồn được trích dẫn · ${sources.length} nguồn trong context. Trang hiển thị theo phạm vi chunk.` : 'Không có nguồn được dùng làm bằng chứng cho kết quả này.';
  const list = $('source-list'); list.replaceChildren();
  if (!sources.length) list.append(node('p', 'Khi cần hỏi lại hoặc thiếu bằng chứng, hệ thống không tự tạo citation.', 'field-hint'));
  sources.forEach((source, index) => list.append(sourceEntry(source, payload, index)));
}
function renderResult(payload, request, elapsedMs) {
  if (!STATUS[payload.status] || typeof payload.answer !== 'string' || !Array.isArray(payload.sources)) throw new Error('Response backend không đúng cấu trúc mong đợi.');
  lastResult = { request, response: payload, elapsed_ms: Math.round(elapsedMs), received_at: new Date().toISOString() };
  feedback = null;
  badge(payload.status, STATUS[payload.status].badge);
  $('result-time').textContent = `${(elapsedMs / 1000).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} giây`;
  $('answer-heading').textContent = STATUS[payload.status].heading;
  $('empty-state').hidden = true; $('answer-state').hidden = false;
  renderAnswer(payload.answer, payload.sources); renderSources(payload);
  $('clarification-actions').hidden = payload.status !== 'needs_clarification';
  $('request-metrics').replaceChildren();
  const metrics = [
    ['Nguồn trích dẫn', payload.sources.filter(s => s.cited).length],
    ['Input tokens', payload.input_tokens ?? '—'], ['Lượt chọn đoạn', payload.selection_attempts ?? '—'],
  ];
  metrics.forEach(([label, value]) => { const item = node('div', undefined, 'metric'); item.append(node('strong', String(value)), node('span', label)); $('request-metrics').append(item); });
  const warnings = payload.warnings || [];
  $('notes-panel').hidden = !warnings.length;
  $('warnings-list').replaceChildren(...warnings.map(text => node('li', text)));
  $('technical-json').textContent = pretty(lastResult);
  $('download-result').disabled = false;
  document.querySelectorAll('[data-feedback]').forEach(button => { button.disabled = false; });
  document.querySelectorAll('[data-feedback]').forEach(button => button.setAttribute('aria-pressed', 'false'));
  $('feedback-note').textContent = 'Góp ý chỉ được giữ trong phiên trình duyệt này.';
  announce(STATUS[payload.status].badge);
  $('answer-heading').focus({ preventScroll: true });
}
function renderError(message, request) {
  lastResult = null;
  $('download-result').disabled = true;
  document.querySelectorAll('[data-feedback]').forEach(button => { button.disabled = true; });
  badge('error', 'Chưa nhận được kết quả');
  $('empty-state').hidden = true; $('answer-state').hidden = false;
  $('answer-heading').textContent = 'Bạn có thể thử lại với cùng câu hỏi';
  $('answer-text').textContent = message;
  $('clarification-actions').hidden = true;
  $('request-metrics').replaceChildren(); $('notes-panel').hidden = true;
  $('technical-json').textContent = pretty({ request, error: message });
  $('source-count').textContent = '0'; $('source-description').textContent = 'Yêu cầu chưa hoàn tất.';
  $('source-list').replaceChildren(node('p', 'Không hiển thị nguồn cũ như bằng chứng cho request chưa thành công.', 'field-hint'));
  announce(message); $('answer-heading').focus({ preventScroll: true });
}
async function ask(event) {
  event.preventDefault(); if (busy) return;
  let request;
  try { request = buildRequest(values()); }
  catch (error) { $('form-error').textContent = error.message; $('form-error').hidden = false; $('question').focus(); return; }
  $('form-error').hidden = true;
  setBusy(true); $('empty-state').hidden = true; $('answer-state').hidden = true; $('loading-state').hidden = false;
  $('source-list').replaceChildren(node('p', 'Đang chờ response của request hiện tại…', 'field-hint'));
  $('source-count').textContent = '—'; $('source-description').textContent = 'Nguồn sẽ được lấy từ response thực của backend.';
  badge('neutral', 'Đang tra cứu'); $('result-time').textContent = '';
  $('result-panel').scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  announce('Đang xử lý yêu cầu. Model local có thể cần thời gian tải.');
  const start = performance.now();
  const timer = setInterval(() => { $('elapsed-time').textContent = `Đã chờ ${Math.floor((performance.now() - start) / 1000)} giây`; }, 1000);
  $('elapsed-time').textContent = 'Đã chờ 0 giây';
  const controller = new AbortController(); activeController = controller;
  const timeout = setTimeout(() => controller.abort('timeout'), 300000);
  try {
    const response = await fetch('/api/v1/ask', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request), signal: controller.signal });
    const payload = await response.json();
    if (!response.ok) throw new Error(backendError(response.status, payload));
    renderResult(payload, request, performance.now() - start);
  } catch (error) {
    const message = controller.signal.aborted ? 'Đã dừng chờ ở trình duyệt. Backend có thể vẫn đang xử lý; request tiếp theo sẽ chờ lượt của nó. Câu hỏi và phạm vi của bạn được giữ lại.' : error instanceof TypeError ? 'Không kết nối được API. Kiểm tra terminal Uvicorn và kết nối local, rồi gửi lại câu hỏi.' : error.message;
    renderError(message, request);
  } finally {
    clearInterval(timer); clearTimeout(timeout); activeController = null;
    $('loading-state').hidden = true; setBusy(false);
  }
}
function applyPreset(preset) {
  if (busy) return;
  if ((preset.documentIds?.length || preset.domain) && (!catalog || (preset.documentIds || []).some(id => !catalog.documents.some(doc => doc.document_id === id)))) {
    $('form-error').hidden = false;
    $('form-error').textContent = 'Danh mục chưa sẵn sàng để áp dụng đúng bộ lọc của mẫu này. Tải lại trang sau khi kiểm tra cấu hình nguồn.';
    return;
  }
  fields.forEach(id => { $(id).value = ''; });
  $('domain').value = preset.domain || '';
  document.querySelectorAll('[name=document-id]').forEach(input => { input.checked = (preset.documentIds || []).includes(input.value); });
  $('question').value = preset.question;
  $('form-error').hidden = true;
  $('filter-panel').open = Boolean(preset.documentIds?.length); $('scope-panel').open = false;
  countChars(); $('question').focus(); announce(`Đã điền mẫu ${preset.title}. Bấm Tra cứu để gửi.`);
}
async function checkHealth() {
  $('health-label').textContent = 'Đang kiểm tra kết nối';
  try {
    const response = await fetch('/health', { signal: AbortSignal.timeout(10000) });
    const body = await response.json();
    const ok = response.ok && body.database?.status === 'ok';
    $('health-button').className = `health-chip ${ok ? 'ok' : 'bad'}`;
    $('health-label').textContent = ok ? 'API & database sẵn sàng' : 'Database chưa sẵn sàng';
    $('health-button').title = ok ? 'Health kiểm API/database. Model được tải khi có request.' : 'Bật Docker Desktop và chạy docker compose up -d --wait. Bấm để kiểm tra lại.';
  } catch {
    $('health-button').className = 'health-chip bad'; $('health-label').textContent = 'Chưa kết nối được API';
  }
}
async function loadCatalog() {
  try {
    const response = await fetch('/api/v1/demo/catalog');
    if (!response.ok) throw new Error('Không tải được danh mục. Kiểm tra cấu hình/source manifest trong terminal API.');
    catalog = await response.json();
    $('catalog-count').textContent = catalog.documents.length;
    $('top-k').value = catalog.top_k; $('retrieval-mode').value = catalog.retrieval_mode;
    $('catalog-note').textContent = catalog.corpus_note;
    $('document-options').replaceChildren(); $('catalog-list').replaceChildren();
    const domains = [...new Set(catalog.documents.map(doc => doc.domain))].sort();
    domains.forEach(domain => { const option = node('option', DOMAINS[domain] || domain); option.value = domain; $('domain').append(option); });
    catalog.documents.forEach(doc => {
      const label = node('label', undefined, 'document-option');
      const input = node('input'); input.type = 'checkbox'; input.name = 'document-id'; input.value = doc.document_id;
      const text = node('span'); text.append(node('strong', doc.document_number), node('span', doc.title));
      label.append(input, text); $('document-options').append(label);
      const item = node('article', undefined, 'catalog-item'); item.append(node('strong', doc.document_number), node('p', doc.title), node('small', `Ban hành ${doc.issued_date || 'chưa ghi nhận'} · trạng thái pháp lý ${doc.legal_status}`));
      const url = safeHttpUrl(doc.source_url);
      if (url) { const link = node('a', 'Mở nguồn ↗', 'source-link'); link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; item.append(link); }
      $('catalog-list').append(item);
    });
  } catch (error) {
    $('document-options').replaceChildren(node('p', error.message, 'field-hint'));
    $('catalog-note').textContent = error.message;
  }
  PRESETS.forEach(preset => {
    const button = node('button', undefined, 'sample-button'); button.type = 'button'; button.dataset.preset = preset.id;
    button.append(node('strong', preset.title), node('span', preset.hint));
    button.addEventListener('click', () => applyPreset(preset)); $('sample-buttons').append(button);
  });
}
$('ask-form').addEventListener('submit', ask);
$('question').addEventListener('input', countChars);
$('question').addEventListener('keydown', event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); $('ask-form').requestSubmit(); } });
$('stop-waiting').addEventListener('click', () => activeController?.abort('user'));
$('health-button').addEventListener('click', checkHealth);
$('open-catalog').addEventListener('click', () => $('catalog-dialog').showModal());
$('fill-scope').addEventListener('click', () => { $('scope-panel').open = true; $('scope-panel').scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }); $('cohort').focus({ preventScroll: true }); });
document.querySelectorAll('[data-feedback]').forEach(button => button.addEventListener('click', () => {
  if (!lastResult) return;
  feedback = button.dataset.feedback;
  document.querySelectorAll('[data-feedback]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  $('feedback-note').textContent = 'Đã đánh dấu trong phiên này. Tải JSON để lưu cùng kết quả; chưa gửi góp ý lên server.';
}));
$('download-result').addEventListener('click', () => {
  if (!lastResult) return;
  const blob = new Blob([pretty({ ...lastResult, feedback })], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob); const link = node('a'); link.href = url; link.download = `regularag-result-${Date.now()}.json`;
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
checkHealth(); loadCatalog();
