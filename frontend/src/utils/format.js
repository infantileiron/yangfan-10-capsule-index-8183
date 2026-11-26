export function escapeHtml(value) {
  return String(value ?? '—').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

export const timeText = value => value ? new Intl.DateTimeFormat('zh-CN', {
  month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  hourCycle: 'h23', timeZone: 'Asia/Shanghai',
}).format(new Date(value)) : '—';

export function shortId(value) {
  return value ? value.slice(0, 8) : '—';
}
