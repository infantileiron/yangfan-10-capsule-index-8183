import { escapeHtml as e } from '../../utils/format.js';

export function table(columns, rows, cell = (_, column, value) => e(value), select = false) {
  return `<div class="table-scroll" tabindex="0"><table>
    <thead><tr>${select ? '<th scope="col">选择</th>' : ''}${columns.map(column =>
      `<th scope="col">${e(column.label)}</th>`).join('')}</tr></thead>
    <tbody>${rows.map(row => `<tr>${select ? `<td><input type="checkbox" name="samples" value="${e(row.sample_id)}" aria-label="选择 ${e(row.sample_id)}"></td>` : ''}
      ${columns.map(column => `<td>${cell(row, column, row[column.key])}</td>`).join('')}</tr>`).join('')}</tbody>
  </table></div>`;
}
