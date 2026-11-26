import { escapeHtml as e } from '../../utils/format.js';

export const heading = (title, subtitle, actions = '') => `
  <section class="heading"><div><h1>${e(title)}</h1><p>${e(subtitle)}</p></div>
  ${actions ? `<div class="heading-actions">${actions}</div>` : ''}</section>`;

export const empty = (title, guide, action = '') =>
  `<div class="empty"><h2>${e(title)}</h2><p>${e(guide)}</p>${action}</div>`;

export const exportButton = (path, filename, label) =>
  `<button class="quiet" type="button" data-download="${e(path)}" data-file="${e(filename)}">${e(label)}</button>`;
