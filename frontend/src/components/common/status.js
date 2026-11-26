import { decisions, stages } from '../../constants/enums.js';
import { escapeHtml as e } from '../../utils/format.js';

export const status = value => `<span class="status s-${e(value)}">${e(stages[value] ?? decisions[value] ?? value)}</span>`;
