import { session, setSession } from '../stores/session.js';

export async function request(path, { method = 'GET', body, download = false } = {}) {
  const token = session()?.token;
  let response;
  try {
    response = await fetch('/api' + path, {
      method,
      headers: {
        ...(token ? { Authorization: 'Bearer ' + token } : {}),
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('无法连接工作台，请检查服务后重试。');
  }
  if (response.ok) return download ? response.blob() : response.json();
  let data;
  try { data = await response.json(); } catch { data = {}; }
  if (response.status === 401 && token) {
    setSession(null);
    window.dispatchEvent(new Event('session-expired'));
  }
  const detail = data.detail;
  throw new Error(typeof detail === 'string' ? detail : '表单包含无效数据，请检查输入后重试。');
}
