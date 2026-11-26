import { api } from '../api/workspace.js';
import { notice } from '../hooks/forms.js';

export function bindDownloads(root) {
  for (const button of root.querySelectorAll('[data-download]')) {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const blob = await api.download(button.dataset.download);
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = button.dataset.file;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } catch (error) {
        notice(error.message, 'error');
      } finally {
        button.disabled = false;
      }
    });
  }
}
