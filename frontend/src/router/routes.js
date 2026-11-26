const pages = new Set(['datasets', 'runs', 'results', 'handoff']);

export function route() {
  const [page, id] = location.hash.slice(1).split('/');
  return { page: pages.has(page) ? page : 'datasets', id: /^[a-f0-9-]{36}$/.test(id ?? '') ? id : '' };
}

export function navigate(page, id = '') {
  location.hash = '#' + page + (id ? '/' + id : '');
}
