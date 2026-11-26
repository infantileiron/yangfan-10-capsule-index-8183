import { escapeHtml as e } from '../utils/format.js';

export function resultChart(rows, {key, label}) {
  const shown = rows.slice(0, 8);
  const scale = Math.max(...shown.map(row => Math.abs(row[key])), 1e-12);
  return `<figure class="plot"><figcaption>${e(label)}${rows.length > shown.length ? ' · 前 8 条' : ''}</figcaption>
    <ol>${shown.map(row => {
      const value = row[key];
      return `<li><span class="plot-name" title="${e(row.sample_id)}">${e(row.sample_id)}</span>
      <span class="track" aria-hidden="true"><i class="${value < 0 ? 'negative' : ''}" style="--amount:${100 * Math.abs(value) / scale}%"></i></span>
      <strong>${e(value)}</strong></li>`;
    }).join('')}</ol></figure>`;
}
