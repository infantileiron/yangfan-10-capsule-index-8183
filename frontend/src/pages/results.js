import { api } from '../api/workspace.js';
import { resultChart } from '../components/chart.js';
import { empty, exportButton, heading } from '../components/common/heading.js';
import { status } from '../components/common/status.js';
import { table } from '../components/common/table.js';
import { escapeHtml as e, shortId, timeText } from '../utils/format.js';

export async function resultsPage(profile, account, id) {
  const runs = await api.runs();
  const chosen = id || runs[0]?.id;
  if (!chosen) return { html: heading(profile.labels.results, profile.algorithm) +
    empty('还没有计算结果', '创建计算单，等待后台完成计算。', '<a href="#runs">回计算页面</a>') };
  const run = await api.run(chosen);
  const selector = runs.map(item => `<option value="${item.id}" ${item.id === run.id ? 'selected' : ''}>
      ${e(item.label)} · ${e(shortId(item.id))}</option>`).join('');
  const actions = run.result ? exportButton('/runs/' + run.id + '/csv', 'analysis.csv', '导出计算结果') : '';
  const intro = heading(profile.labels.results, profile.labels.action, actions) +
    `<div class="result-pick"><label>计算单<select id="choose-result">${selector}</select></label>
    ${status(run.status)}<span class="muted">${e(timeText(run.created_at))}</span></div>`;
  const mount = root => {
    root.querySelector('#choose-result').onchange = event => { location.hash = '#results/' + event.target.value; };
  };
  if (!run.result) {
    return {
      html: intro + (run.status === 'failed' ?
        empty('计算失败', run.error, '<a href="#runs">调整输入后重试</a>') :
        `<div class="empty"><h2>等待后台计算</h2><p>页面会自动更新当前计算状态。</p></div>`),
      mount,
      poll: ['queued', 'running'].includes(run.status),
    };
  }
  const result = run.result;
  return {
    html: intro + `<div class="board results-board"><aside class="side">
      <h2>本次口径</h2><dl class="meta"><dt>${e(profile.parameter.label)}</dt><dd>${e(run.parameter)}</dd>
      <dt>数据版本</dt><dd><a href="#datasets/${run.dataset_id}">${shortId(run.dataset_id)}</a></dd>
      </dl><p class="muted">${e(profile.downstream)}</p>
      <a class="button" href="#handoff/${run.id}">查看签审</a>
      </aside><section class="work">
      <h2>${e(result.summary)}</h2>
      <dl class="metrics">${result.metrics.map(metric => `<div><dt>${e(metric.label)}</dt><dd>${e(metric.value)}</dd></div>`).join('')}</dl>
      ${resultChart(result.rows, profile.chart)}
      <h3>${e(profile.labels.action)}</h3>
      ${table(profile.result_columns, result.rows)}
      <details class="details"><summary>计算说明</summary><ul>${result.notes.map(note => '<li>' + e(note) + '</li>').join('')}</ul></details>
      </section></div>`,
    mount,
  };
}
