export const PRESETS = [
  { id: 'summer', title: 'Tín chỉ học kỳ hè', hint: 'Có đáp án · giới hạn 12 tín chỉ', question: 'Trong học kỳ hè sinh viên được đăng ký tối đa bao nhiêu tín chỉ?', domain: 'academic_training' },
  { id: 'clarify', title: 'Chuẩn ngoại ngữ của em', hint: 'Cần hỏi lại · thiếu phạm vi', question: 'Sau ba học kỳ chưa đạt ngoại ngữ bị giới hạn đăng ký thế nào?' },
  { id: 'effective', title: 'Ngày hiệu lực quy định', hint: 'Có đáp án · phân biệt ngày ban hành', question: 'Quyết định851 quy định liêm chính học thuật có hiệu lực từ ngày nào?', documentIds: ['uit_851_2024'] },
  { id: 'old-filter', title: 'Bộ lọc chỉ cho văn bản cũ', hint: 'Thiếu bằng chứng cập nhật · từ chối', question: 'Theo Quyết định790 lớp đại cương mở khi có tối thiểu bao nhiêu sinh viên?', documentIds: ['uit_790_2022'] },
];
export const STATUS = {
  answered: { badge: 'Có bằng chứng trả lời', heading: 'Kết quả từ nguồn đã truy xuất' },
  needs_clarification: { badge: 'Cần làm rõ phạm vi', heading: 'Thêm một chút thông tin để đối chiếu' },
  insufficient_evidence: { badge: 'Chưa đủ bằng chứng', heading: 'Chưa thể kết luận trong phạm vi này' },
};
export const DOMAINS = {
  academic_training: 'Đào tạo tín chỉ', graduation_thesis: 'Khóa luận tốt nghiệp',
  foreign_language: 'Đào tạo ngoại ngữ', credit_recognition: 'Công nhận tín chỉ',
  dual_degree: 'Đào tạo song ngành', extension_tuition: 'Học phí gia hạn',
  graduation_project: 'Đồ án tốt nghiệp', graduation_project_enterprise: 'Đồ án doanh nghiệp',
  admission: 'Tuyển sinh', academic_integrity: 'Liêm chính học thuật',
  diplomas_certificates: 'Văn bằng, chứng chỉ', academic_case_handling: 'Xử lý học vụ',
  academic_warning: 'Cảnh báo học tập',
};
function integer(value, name, low, high) {
  if (!/^\d+$/.test(String(value)) || Number(value) < low || Number(value) > high) {
    throw new Error(`${name} cần là số nguyên từ ${low} đến ${high}.`);
  }
  return Number(value);
}
export function buildRequest(values) {
  const question = values.question.trim();
  if (question.length < 3 || question.length > 1000) throw new Error('Câu hỏi cần từ 3 đến 1.000 ký tự.');
  const request = { question, top_k: integer(values.topK, 'Top-k', 1, 20) };
  if (!['hybrid', 'vector', 'keyword'].includes(values.mode)) throw new Error('Chế độ truy xuất không hợp lệ.');
  request.retrieval_mode = values.mode;
  const scope = {};
  if (values.studyProgress !== undefined && values.studyProgress !== '') scope.study_progress = integer(values.studyProgress, 'Học kỳ chính đã hoàn thành', 0, 40);
  if (values.cohort) scope.cohort_year = integer(values.cohort, 'Khóa tuyển sinh', 1980, 2100);
  if (values.audience) {
    if (!['undergraduate_regular', 'undergraduate_distance', 'joint_program'].includes(values.audience)) throw new Error('Hệ đào tạo không hợp lệ.');
    scope.applies_to = [values.audience];
  }
  if (values.programme) {
    if (!['ctc', 'cttn', 'cta', 'cttt', 'viet_japan'].includes(values.programme)) throw new Error('Chương trình không hợp lệ.');
    scope.programmes = [values.programme];
  }
  if (values.asOf) {
    const date = new Date(`${values.asOf}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(values.asOf) || Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== values.asOf) throw new Error('Ngày cần đối chiếu phải là một ngày lịch hợp lệ.');
    scope.as_of = values.asOf;
  }
  if (values.designYears) {
    const years = Number(values.designYears);
    if (!Number.isFinite(years) || years <= 0 || years > 10) throw new Error('Thời gian thiết kế cần lớn hơn 0 và không quá 10 năm.');
    scope.design_years = years;
  }
  if (values.projectType) {
    if (!['regular', 'enterprise'].includes(values.projectType)) throw new Error('Loại đồ án không hợp lệ.');
    scope.project_type = values.projectType;
  }
  if (Object.keys(scope).length) request.scope = scope;
  const filters = {};
  if (values.documentIds?.length) {
    if (values.documentIds.length > 20 || values.documentIds.some(id => !/^[A-Za-z0-9_-]+$/.test(id))) throw new Error('Danh sách mã nguồn không hợp lệ.');
    filters.document_ids = [...new Set(values.documentIds)];
  }
  if (values.domain) {
    if (!/^[a-z][a-z0-9_]*$/.test(values.domain)) throw new Error('Chủ đề nguồn không hợp lệ.');
    filters.domains = [values.domain];
  }
  if (Object.keys(filters).length) request.filters = filters;
  return request;
}
export function safeHttpUrl(value) {
  try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; }
  catch { return null; }
}
export function backendError(status, body) {
  if (status === 422) {
    const detail = Array.isArray(body?.detail) ? body.detail.map(item => `${item.loc?.slice(1).join('.') || 'Dữ liệu'}: ${item.msg}`).join('; ') : body?.detail;
    return `Backend chưa chấp nhận dữ liệu: ${detail || 'kiểm tra câu hỏi và phạm vi.'}`;
  }
  if (status === 503) return 'Database hoặc model chưa sẵn sàng. Kiểm tra Docker và terminal chạy API, rồi thử lại.';
  return `Yêu cầu không thành công (HTTP ${status}). Bạn có thể thử lại với cùng câu hỏi.`;
}
