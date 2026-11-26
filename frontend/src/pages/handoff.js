import { api } from '../api/workspace.js';
import { table } from '../components/common/table.js';
import { empty, exportButton, heading } from '../components/common/heading.js';
import { status } from '../components/common/status.js';
import { auditActions } from '../constants/enums.js';
import { bindForm, notice } from '../hooks/forms.js';
import { escapeHtml as e, shortId, timeText } from '../utils/format.js';

export async function handoffPage(profile, account, id) {
  const [runs, reviews, audit] = await Promise.all([api.runs(), api.reviews(), api.audit()]);
  const completed = runs.filter(run => run.status === 'succeeded');
  const selected = completed.find(run => run.id === id) || completed[0];
  const run = selected && await api.run(selected.id);
  const review = run?.review;
  const selector = completed.map(item => `<option value="${item.id}" ${item.id === selected?.id ? 'selected' : ''}>${e(item.label)}</option>`).join('');
  const actions = review?.decision === 'approve' ?
    exportButton('/runs/' + run.id + '/handoff.csv', 'handoff.csv', '下载签发清单') : '';
  const form = run && account.role === 'reviewer' && !review ? `
    <form id="review-form">
      <p>选择要交接的样本，再填写复核结论。暂缓可不选样本。</p>
      ${table(profile.result_columns, run.result.rows.slice(0, 500), undefined, true)}
      ${run.result.rows.length > 500 ? '<p>本页可签审前 500 条结果。完整计算结果可在结果页下载。</p>' : ''}
      <label>决定<select name="decision"><option value="approve">签发</option><option value="hold">暂缓</option></select></label>
      <label>复核说明<textarea name="note" minlength="2" maxlength="1000" required></textarea></label>
      <div class="form-error" data-error role="alert"></div><button type="submit">保存决定</button>
    </form>` : '';
  return {
    html: heading(profile.labels.handoff, profile.downstream, actions) +
      `<div class="board"><aside class="side"><h2>交接记录</h2>${reviews.map(item => `<a class="version" href="#handoff/${item.run_id}">
        <strong>${e(runs.find(candidate => candidate.id === item.run_id)?.label || shortId(item.run_id))}</strong><span>${status(item.decision)}</span></a>`).join('') || '<p>暂无记录</p>'}</aside>
      <section class="work">
      ${run ? `<label>已完成计算单<select id="choose-review">${selector}</select></label>
      <p><a href="#results/${run.id}">查看完整结果</a></p>${review ? `<div class="review-record">${status(review.decision)}
        <strong>${e(review.reviewer)}</strong><p>${e(review.note)}</p>
        <p class="muted">${review.samples.length} 条交接样本 · ${e(timeText(review.created_at))}</p></div>` :
        form || '<p>此计算单等待复核员签审。</p>'}` :
        empty('还没有可签审的计算单', '后台完成计算后，复核员可选中样本并记录签审结果。')}
      <h3>审计流水</h3>
      ${audit.length ? table([
        {key:'action',label:'动作'}, {key:'actor',label:'操作者'}, {key:'subject',label:'对象'}, {key:'created_at',label:'时间'},
      ], audit, (row, column, value) => {
        if (column.key === 'action') return e(auditActions[value] || value);
        if (column.key === 'subject') return e(shortId(value));
        if (column.key === 'created_at') return e(timeText(value));
        return e(value);
      }) : '<p class="muted">暂无审计事件。</p>'}</section></div>`,
    mount(root, refresh) {
      const pick = root.querySelector('#choose-review');
      if (pick) pick.onchange = () => { location.hash = '#handoff/' + pick.value; };
      bindForm(root, 'review-form', async data => {
        await api.review(run.id, { decision: data.get('decision'), note: data.get('note'), samples: data.getAll('samples') });
        notice('已保存复核决定。');
        refresh();
      });
    },
  };
}
