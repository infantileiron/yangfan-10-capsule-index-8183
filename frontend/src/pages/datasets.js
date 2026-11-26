import { api } from '../api/workspace.js';
import { table } from '../components/common/table.js';
import { empty, exportButton, heading } from '../components/common/heading.js';
import { status } from '../components/common/status.js';
import { bindForm, notice } from '../hooks/forms.js';
import { navigate } from '../router/routes.js';
import { columnNames } from '../types/profile.js';
import { escapeHtml as e, shortId, timeText } from '../utils/format.js';

export async function datasetsPage(profile, account, id) {
  const [items, calibrations] = await Promise.all([
    api.datasets(),
    api.calibrations().catch(() => []),
  ]);
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
  const numericFields = profile.columns.filter(column => column.type === 'number');
  const correction = account.role === 'analyst' && detail ? `<details class="intake correction-intake">
    <summary>按试转编号更正读数</summary>
    <form id="correction-form">
      <label>试转编号<input name="sample_id" list="sample-id-list" placeholder="例如 ZM-TR65-04" required></label>
      <datalist id="sample-id-list">${detail.rows.map(row => `<option value="${e(row.sample_id)}">${e(row.cabinet)}</option>`).join('')}</datalist>
      ${numericFields.map(column => `<label>${e(column.label)}
        <input name="${e(column.key)}" type="number" step="any" ${column.min == null ? '' : `min="${column.min}"`} ${column.max == null ? '' : `max="${column.max}"`} placeholder="留空表示不修改"></label>`).join('')}
      <label>更正原因（可选）<input name="reason" maxlength="1000" placeholder="例如现场复测后更正"></label>
      <p class="muted">可直接填写要更正的字段；留空字段保持原值。更正会生成新的数据版本，不覆盖旧台账，受影响口径的复检线将重算。</p>
      <div class="form-error" data-error role="alert"></div><button type="submit">生成更正版本</button>
    </form></details>` : '';
  const lineage = detail?.correction ? `<div class="correction-record">
      <h3>更正追溯</h3>
      <p>试转编号 <strong>${e(detail.correction.sample_id)}</strong> · 字段 ${detail.correction.changed_fields.map(e).join('、')}</p>
      ${detail.parent_id ? `<p class="muted">来源版本 <a href="#datasets/${detail.parent_id}">${shortId(detail.parent_id)}</a>${detail.correction.reason ? ' · ' + e(detail.correction.reason) : ''}</p>` : ''}
    </div>` : '';
  const lineRows = calibrations.slice(0, 8).map(line => ({
    ...line,
    line: `${line.caliber} mm · ${line.quantile}`,
    state: line.active ? (line.stale ? '沿用旧线' : '当前线') : status(line.status),
    threshold: line.threshold == null ? '—' : Number(line.threshold).toFixed(2),
    dataset: shortId(line.dataset_id),
    created_at: timeText(line.created_at),
  }));
  const previewColumns = [...profile.columns, { key: '_correct_action', label: '更正' }];
  const previewCell = (row, column, value) => {
    if (column.key === '_correct_action') {
      if (account.role !== 'analyst') return '';
      return `<button type="button" class="quiet correct-row" data-sample-id="${e(row.sample_id)}" data-row="${e(JSON.stringify(row))}">按编号更正</button>`;
    }
    return e(value);
  };
  return {
    html: heading(profile.labels.datasets, profile.upstream,
      detail ? exportButton('/datasets/' + detail.id + '/csv', 'input.csv', '下载原始数据') : '') +
      `<div class="board"><aside class="side"><h2>数据版本</h2>${versionSelector || '<p>尚无数据</p>'}${intake}${correction}</aside>
      <section class="work">${detail ? `<div class="work-head"><div><h2>${e(detail.name)}</h2>
      <p class="muted">共 ${detail.count} 行 · 预览前 ${Math.min(detail.count, 18)} 行</p></div>
      ${account.role === 'analyst' ? `<a class="button" href="#runs/${detail.id}">新建计算单</a>` : ''}</div>
      ${lineage}
      ${table(previewColumns, detail.rows.slice(0, 18), previewCell)}` :
      empty('还没有可读样本', '分析员可上传符合字段要求的 CSV 文件。')}

      ${lineRows.length ? `<h3>同口径复检线版本</h3>${table([
        {key:'line',label:'口径 / 分位'}, {key:'threshold',label:'复检线'},
        {key:'state',label:'状态'}, {key:'dataset',label:'来源版本'}, {key:'created_at',label:'时间'},
      ], lineRows, (row, column, value) => {
        if (column.key === 'state' && row.active) return `<span class="status ${row.stale ? 's-held' : 's-succeeded'}">${e(value)}</span>`;
        if (column.key === 'state') return value;
        return e(value);
      })}` : ''}

      <details class="details"><summary>采集口径</summary><p>${e(profile.workflow)}</p>
      <ul>${profile.pain_points.map(point => `<li>${e(point)}</li>`).join('')}</ul></details></section></div>`,
    mount(root, refresh) {
      root.querySelectorAll('.correct-row').forEach(button => {
        button.addEventListener('click', () => {
          const form = root.querySelector('#correction-form');
          if (!form) return;
          form.closest('details')?.setAttribute('open', '');
          form.querySelector('[name="sample_id"]').value = button.dataset.sampleId;
          let sourceRow = {};
          try { sourceRow = JSON.parse(button.dataset.row || '{}'); } catch { sourceRow = {}; }
          numericFields.forEach(field => {
            const input = form.querySelector(`[name="${field.key}"]`);
            if (input) input.value = sourceRow[field.key] ?? '';
          });
          form.querySelector(`[name="${numericFields[0]?.key}"]`)?.focus();
        });
      });
      bindForm(root, 'import-form', async data => {
        const file = data.get('file');
        if (!file || file.size > 4_000_000) throw new Error('请选择不超过 4 MB 的 CSV 文件。');
        const saved = await api.upload({ name: data.get('name'), csv: await file.text() });
        notice(saved.created ? '已保存新版本。' : '数据内容已存在，已打开原版本。');
        if (id === saved.id) refresh();
        else navigate('datasets', saved.id);
      });
      bindForm(root, 'correction-form', async data => {
        const sampleId = data.get('sample_id');
        const original = detail.rows.find(row => row.sample_id === sampleId) || {};
        const payload = { sample_id: sampleId, reason: data.get('reason') || null };
        numericFields.forEach(field => {
          const raw = data.get(field.key);
          if (raw === '' || raw == null) return;
          const value = Number(raw);
          if (original[field.key] == null || Math.abs(value - Number(original[field.key])) > 1e-10) {
            payload[field.key] = value;
          }
        });
        if (Object.keys(payload).length <= 2) {
          throw new Error('请至少修改一个读数后再生成更正版本。');
        }
        const saved = await api.correct(detail.id, payload);
        notice(saved.created ? '已生成更正版本，受影响复检线将重算。' : '更正后内容已存在，已打开对应版本。');
        navigate('datasets', saved.id);
      });
    },
  };
}
