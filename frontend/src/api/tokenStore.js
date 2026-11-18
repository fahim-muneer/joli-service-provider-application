// Where the JWT pair lives. localStorage keeps the user signed in across tabs and
// reloads; if it is unavailable (private mode, tests) we fall back to memory.
const ACCESS_KEY = "joli.access";
const REFRESH_KEY = "joli.refresh";
const memory = new Map();

function store() {
  try {
    return typeof localStorage !== "undefined" ? localStorage : null;
  } catch {
    return null; // some browsers throw when storage is blocked
  }
}

function read(key) {
  const s = store();
  return (s ? s.getItem(key) : memory.get(key)) ?? null;
}

function write(key, value) {
  const s = store();
  if (s) s.setItem(key, value);
  else memory.set(key, value);
}

function remove(key) {
  const s = store();
  if (s) s.removeItem(key);
  memory.delete(key);
}

export const tokenStore = {
  getAccess: () => read(ACCESS_KEY),
  getRefresh: () => read(REFRESH_KEY),
  hasSession: () => Boolean(read(REFRESH_KEY) || read(ACCESS_KEY)),
  set({ access, refresh }) {
    if (access) write(ACCESS_KEY, access);
    if (refresh) write(REFRESH_KEY, refresh);
  },
  clear() {
    remove(ACCESS_KEY);
    remove(REFRESH_KEY);
  },
};
