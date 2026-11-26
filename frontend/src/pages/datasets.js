import { api } from '../api/workspace.js';
import { table } from '../components/common/table.js';
import { empty, exportButton, heading } from '../components/common/heading.js';
import { bindForm, notice } from '../hooks/forms.js';
import { navigate } from '../router/routes.js';
import { columnNames } from '../types/profile.js';
import { escapeHtml as e } from '../utils/format.js';

export async function datasetsPage(profile, account, id) {
  const items = await api.datasets();
  const active = items.find(item => item.id === id) || items[0];
  const detail = active && await api.dataset(active.id);
  const versionSelector = items.map(item => `<a class="version ${active?.id === item.id ? 'current' : ''}" href="#datasets/${item.id}">
    <strong>${e(item.name)}</strong><span>${item.count} 行 · ${e(item.checksum.slice(0, 8))}</span></a>`).join('');
  const intake = account.role === 'analyst' ? `<details class="intake" ${items.length ? '' : 'open'}>
    <summary>导入 CSV</summary>
    <form id="import-form">
      <label>版本名称<input name="name" maxlength="100" required></label>
      <label>选取 CSV 文件<input name="file" type="file" accept=".csv,text/csv" required></label>
      <p class="muted">表头字段按此顺序排列</p><code class="header-example">${e(columnNames(profile.columns))}</code>
      <div class="form-error" data-error role="alert"></div><button type="submit">保存版本</button>
    </form></details>` : '';
  return {
    html: heading(profile.labels.datasets, profile.upstream,
      detail ? exportButton('/datasets/' + detail.id + '/csv', 'input.csv', '下载原始数据') : '') +
      `<div class="board"><aside class="side"><h2>数据版本</h2>${versionSelector || '<p>尚无数据</p>'}${intake}</aside>
      <section class="work">${detail ? `<div class="work-head"><div><h2>${e(detail.name)}</h2>
      <p class="muted">共 ${detail.count} 行 · 预览前 ${Math.min(detail.count, 18)} 行</p></div>
      ${account.role === 'analyst' ? `<a class="button" href="#runs/${detail.id}">新建计算单</a>` : ''}</div>
      ${table(profile.columns, detail.rows.slice(0, 18))}` :
      empty('还没有可读样本', '分析员可上传符合字段要求的 CSV 文件。')}

      <details class="details"><summary>采集口径</summary><p>${e(profile.workflow)}</p>
      <ul>${profile.pain_points.map(point => `<li>${e(point)}</li>`).join('')}</ul></details></section></div>`,
    mount(root, refresh) {
      bindForm(root, 'import-form', async data => {
        const file = data.get('file');
        if (!file || file.size > 4_000_000) throw new Error('请选择不超过 4 MB 的 CSV 文件。');
        const saved = await api.upload({ name: data.get('name'), csv: await file.text() });
        notice(saved.created ? '已保存新版本。' : '数据内容已存在，已打开原版本。');
        if (id === saved.id) refresh();
        else navigate('datasets', saved.id);
      });
    },
  };
}
