let noticeTimer;

export function notice(message, kind = 'info') {
  const box = document.querySelector('#notice');
  box.textContent = message;
  box.dataset.kind = kind;
  box.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { box.hidden = true; }, 7000);
}

export function bindForm(root, id, handler) {
  const form = root.querySelector('#' + id);
  if (!form) return;
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button[type=submit]');
    const error = form.querySelector('[data-error]');
    if (error) error.textContent = '';
    button.disabled = true;
    try {
      await handler(new FormData(form), form);
    } catch (problem) {
      if (error) error.textContent = problem.message;
      else notice(problem.message, 'error');
    } finally {
      button.disabled = false;
    }
  });
}
