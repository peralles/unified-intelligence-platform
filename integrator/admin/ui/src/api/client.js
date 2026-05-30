/** @typedef {{ show: (msg: string, kind?: string) => void }} Toast */

/** @type {Toast | null} */
let toastRef = null;

export function bindToast(el) {
  toastRef = {
    show(msg, kind = "") {
      el.textContent = msg;
      el.className = "toast" + (kind ? ` toast--${kind}` : "");
      el.style.display = "block";
      clearTimeout(el._t);
      el._t = setTimeout(() => {
        el.style.display = "none";
      }, 5000);
    },
  };
}

export function toast(msg, kind = "") {
  toastRef?.show(msg, kind);
}

export async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok && data.error && data.ok !== true) {
    throw new Error(data.error);
  }
  return data;
}
