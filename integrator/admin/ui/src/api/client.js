let _toastEl = null;
let _toastTimer = null;
const _queue = [];
let _showing = false;

function _next() {
  if (_showing || _queue.length === 0 || !_toastEl) return;
  const { msg, kind, dur } = _queue.shift();
  _showing = true;
  _toastEl.textContent = msg;
  _toastEl.className = `toast${kind ? ` toast--${kind}` : ""}`;
  _toastEl.style.display = "block";
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => {
    _toastEl.style.display = "none";
    _showing = false;
    _next();
  }, dur || 4000);
}

export function bindToast(el) {
  _toastEl = el;
}

export function toast(msg, kind = "", dur) {
  if (!_toastEl) return;
  _queue.push({ msg, kind, dur });
  _next();
}

export async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    ...opts,
  });
  const data = await res.json().catch(() => ({}));
  if (data.ok === false && data.error) {
    throw new Error(data.error);
  }
  if (!res.ok && data.error && data.ok !== true) {
    throw new Error(data.error);
  }
  return data;
}
