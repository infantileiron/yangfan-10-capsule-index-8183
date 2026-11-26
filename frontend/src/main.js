import { identity } from './identity.js';
import { empty } from './components/common/heading.js';
import { roles } from './constants/enums.js';
import { notice } from './hooks/forms.js';
import { datasetsPage } from './pages/datasets.js';
import { handoffPage } from './pages/handoff.js';
import { loginPage } from './pages/login.js';
import { resultsPage } from './pages/results.js';
import { runsPage } from './pages/runs.js';
import { route } from './router/routes.js';
import { session, setSession } from './stores/session.js';
import { loadProfile, resetWorkspace } from './stores/workspace.js';
import { bindDownloads } from './utils/download.js';
import { escapeHtml as e } from './utils/format.js';

const app = document.querySelector('#app');
document.body.dataset.layout = identity.theme.layout;
const pages = { datasets: datasetsPage, runs: runsPage, results: resultsPage, handoff: handoffPage };
let renderId = 0;
let timer;

function shell(profile, active, role) {
  return `<header class="mast"><a class="mast-brand" href="#datasets">${e(profile.title)}</a>
    <nav aria-label="工作区">${Object.keys(pages).map(page =>
      `<a href="#${page}" ${page === active ? 'aria-current="page"' : ''}>${e(profile.labels[page])}</a>`).join('')}</nav>
    <div class="account"><span>${e(roles[role] ?? role)}</span><button class="quiet" type="button" id="logout">退出</button></div></header>
    <main id="content"></main>`;
}

async function render() {
  clearTimeout(timer);
  const tick = ++renderId;
  const account = session();
  if (!account) {
    loginPage(app, identity, render);
    app.setAttribute('aria-busy', 'false');
    return;
  }
  const {page, id} = route();
  app.setAttribute('aria-busy', 'true');
  try {
    const profile = await loadProfile();
    const view = await pages[page](profile, account, id);
    if (tick !== renderId) return;
    app.innerHTML = shell(profile, page, account.role);
    app.querySelector('#logout').onclick = () => {
      setSession(null);
      resetWorkspace();
      render();
    };
    const content = app.querySelector('#content');
    content.innerHTML = view.html;
    bindDownloads(content);
    view.mount?.(content, render);
    if (view.poll) timer = setTimeout(render, 750);
  } catch (error) {
    if (tick !== renderId) return;
    app.innerHTML = `<main id="content">${empty('载入失败', error.message,
      '<button id="retry" type="button">重新载入</button> <a href="#datasets">返回数据页</a>')}</main>`;
    app.querySelector('#retry').onclick = render;
  } finally {
    if (tick === renderId) app.setAttribute('aria-busy', 'false');
  }
}

window.addEventListener('hashchange', render);
window.addEventListener('session-expired', () => {
  resetWorkspace();
  render();
  notice('会话结束，请重新登录。', 'error');
});
render();
