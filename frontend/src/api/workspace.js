import { request } from './client.js';

export const api = {
  signIn: data => request('/auth/login', { method: 'POST', body: data }),
  profile: () => request('/profile'),
  datasets: () => request('/datasets'),
  dataset: id => request('/datasets/' + id),
  upload: data => request('/datasets', { method: 'POST', body: data }),
  correct: (id, data) => request('/datasets/' + id + '/corrections', { method: 'POST', body: data }),
  calibrations: () => request('/calibrations'),
  runs: () => request('/runs'),
  run: id => request('/runs/' + id),
  submit: data => request('/runs', { method: 'POST', body: data }),
  review: (id, data) => request('/runs/' + id + '/review', { method: 'POST', body: data }),
  reviews: () => request('/reviews'),
  audit: () => request('/audit'),
  download: path => request(path, { download: true }),
};
