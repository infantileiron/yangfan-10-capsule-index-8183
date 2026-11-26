import { api } from '../api/workspace.js';

const cache = {
  profile: null,
};

export function resetWorkspace() {
  cache.profile = null;
}

export async function loadProfile() {
  if (!cache.profile) cache.profile = await api.profile();
  return cache.profile;
}
