const key = 'workbench-session';
let current = read();

function read() {
  try {
    return JSON.parse(sessionStorage.getItem(key));
  } catch {
    return null;
  }
}

export function session() {
  return current;
}

export function setSession(account) {
  current = account;
  if (account) sessionStorage.setItem(key, JSON.stringify(account));
  else sessionStorage.removeItem(key);
}
