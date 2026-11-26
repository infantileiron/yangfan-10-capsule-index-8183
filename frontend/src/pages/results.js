import { api } from '../api/workspace.js';
import { resultChart } from '../components/chart.js';
import { empty, exportButton, heading } from '../components/common/heading.js';
import { status } from '../components/common/status.js';
import { table } from '../components/common/table.js';
import { escapeHtml as e, shortId, timeText } from '../utils/format.js';

const lineModeLabels = {
  current: '当前新线',
  fallback_old_line: '沿用可信旧线',
  fallback_old_line_requantiled: '沿用旧线机台分数并按新分位计算',
  new_line_atomic_switch: '本次算好并一次性切换',
  fitted_now: '本次同版计算',
};

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
  if (run.status === 'held') {
    const queue = run.held_queue || [];
    return {
      html: intro + `<div class="empty"><h2>没有可用复检线，已暂缓排队</h2>
        <p>${e(run.hold_reason || '同口径新线尚未算好，也没有仍可信的旧线。')}</p>
        <p>${queue.length} 条试转等待复检线就绪后自动恢复。</p>
        ${queue.length ? `<details class="details"><summary>暂缓队列</summary><ul>${queue.slice(0, 100).map(item =>
          `<li>${e(item.sample_id)} · ${e(item.caliber)} mm · ${e(item.reason)}</li>`).join('')}</ul></details>` : ''}
        <p><a class="button" href="#datasets">查看数据与复检线版本</a></p></div>`,
      mount,
      poll: true,
    };
  }
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
  const versions = result.source_versions || run.line_versions || [];
  return {
    html: intro + `<div class="board results-board"><aside class="side">
      <h2>本次口径</h2><dl class="meta"><dt>${e(profile.parameter.label)}</dt><dd>${e(run.parameter)}</dd>
      <dt>待检读数版本</dt><dd><a href="#datasets/${run.dataset_id}">${shortId(run.dataset_id)}</a></dd>
      </dl>
      <h3>拟合 / 估线 / 待检版本</h3>
      ${versions.map(item => `<div class="version-line">
        <strong>${e(item.capsule_mm)} mm</strong>
        <span>拟合：<a href="#datasets/${e(item.fit_version)}">${shortId(item.fit_version)}</a></span>
        <span>估线：<a href="#datasets/${e(item.threshold_version)}">${shortId(item.threshold_version)}</a></span>
        <span>待检：<a href="#datasets/${e(item.inspection_version)}">${shortId(item.inspection_version)}</a></span>
        <span class="muted">${e(lineModeLabels[item.line_mode] || item.line_mode || '当前线')} · ${item.threshold == null ? '—' : Number(item.threshold).toFixed(2)}</span>
      </div>`).join('')}
      <p class="muted">${e(profile.downstream)}</p>
      <a class="button" href="#handoff/${run.id}">查看签审</a>
      </aside><section class="work">
      <h2>${e(result.summary)}</h2>
      <dl class="metrics">${result.metrics.map(metric => `<div><dt>${e(metric.label)}</dt><dd>${e(metric.value)}</dd></div>`).join('')}</dl>
      ${resultChart(result.rows, profile.chart)}
      <h3>${e(profile.labels.action)}</h3>
      ${table(profile.result_columns, result.rows)}
      <details class="details"><summary>计算说明与完整版本追溯</summary><ul>${result.notes.map(note => '<li>' + e(note) + '</li>').join('')}</ul></details>
      </section></div>`,
    mount,
    poll: false,
  };
}
