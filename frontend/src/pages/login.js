import { api } from '../api/workspace.js';
import { bindForm } from '../hooks/forms.js';
import { setSession } from '../stores/session.js';
import { escapeHtml as e } from '../utils/format.js';

export function loginPage(root, identity, enter) {
  root.innerHTML = `<main class="login" id="content">
    <section class="login-identity"><p class="brand">${e(identity.team)}</p>
    <h1>${e(identity.title)}</h1><p class="login-sub">${e(identity.subtitle)}</p>
    <div class="method"><span>计算方法</span><strong>${e(identity.algorithm)}</strong></div>
    <div class="login-symbol" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div></section>
    <section class="login-panel">
      <form id="login-form"><h2>登录工作台</h2>
        <label>邮箱<input id="email" name="email" type="email" autocomplete="username" required></label>
        <label>密码<input name="password" type="password" autocomplete="current-password" required></label>
        <div class="form-error" data-error role="alert"></div>
        <button type="submit">登录</button>
      </form>
      <details><summary>演示账号</summary>
        <div class="demo-buttons">
          <button class="quiet" type="button" data-role="analyst">分析员</button>
          <button class="quiet" type="button" data-role="reviewer">复核员</button>
          <button class="quiet" type="button" data-role="viewer">观察员</button>
        </div>
      </details>
    </section></main>`;
  const form = root.querySelector('#login-form');
  for (const button of root.querySelectorAll('[data-role]')) button.onclick = () => {
    form.elements.email.value = button.dataset.role + '@demo.local';
    form.elements.password.value = 'Yangfan-demo-2026';
    form.elements.email.focus();
  };
  bindForm(root, 'login-form', async data => {
    setSession(await api.signIn(Object.fromEntries(data)));
    enter();
  });
}
