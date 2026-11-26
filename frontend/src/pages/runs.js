import { api } from '../api/workspace.js';
import { table } from '../components/common/table.js';
import { heading, empty } from '../components/common/heading.js';
import { status } from '../components/common/status.js';
import { bindForm, notice } from '../hooks/forms.js';
import { navigate } from '../router/routes.js';
import { escapeHtml as e, timeText } from '../utils/format.js';

export async function runsPage(profile, account, id) {
  const [runs, datasets] = await Promise.all([api.runs(), api.datasets()]);
  const parameter = profile.parameter;
  const canSubmit = account.role === 'analyst' && datasets.length > 0;
  const form = canSubmit ? `<form id="run-form">
    <label>计算单名称<input name="label" maxlength="100" placeholder="例如本班复核" required></label>
    <label>数据版本<select name="dataset_id">${datasets.map(row =>
      `<option value="${row.id}" ${row.id === id ? 'selected' : ''}>${e(row.name)} · ${row.count} 行</option>`).join('')}</select></label>
    <label>${e(parameter.label)}<input type="number" name="parameter" min="${parameter.min}" max="${parameter.max}"
      step="${parameter.step}" value="${parameter.default}" required></label>
    <p class="muted">${e(parameter.description)}</p><div class="form-error" data-error role="alert"></div>
    <button type="submit">提交计算</button></form>` :
    '<p class="muted">分析员可使用已导入的数据版本创建计算单。</p>';
  return {
    html: heading(profile.labels.runs, profile.algorithm) +
      `<div class="board"><aside class="side"><h2>计算设置</h2>${form}</aside>
      <section class="work"><div class="work-head"><h2>计算记录</h2><button type="button" class="quiet" id="refresh-runs">刷新</button></div>
      ${runs.length ? table([
        {key:'label',label:'计算单'}, {key:'parameter',label:parameter.label}, {key:'status',label:'状态'},
        {key:'created_at',label:'提交时间'},
      ], runs, (run, column, value) => {
        if (column.key === 'label') return `<a href="#results/${run.id}">${e(value)}</a>`;
        if (column.key === 'status') return status(value);
        return column.key === 'created_at' ? e(timeText(value)) : e(value);
      }) : empty('等待首个计算单', '选择数据和参数后提交计算，随后可以在此查看记录。')}
      <details class="details"><summary>算法与适用边界</summary><p>${e(profile.method)}</p></details></section></div>`,
    mount(root, refresh) {
      root.querySelector('#refresh-runs').onclick = refresh;
      bindForm(root, 'run-form', async data => {
        const submitted = await api.submit({
          ...Object.fromEntries(data),
          parameter: Number(data.get('parameter')),
        });
        notice('计算单已提交。');
        navigate('results', submitted.id);
      });
    },
  };
}
