/**
 * @param {string} tag
 * @param {Record<string, any>} [attrs]
 * @param {(Node|string)[]} [children]
 */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "className") node.className = v;
    else if (k === "disabled") node.disabled = !!v;
    else if (k.startsWith("on") && typeof v === "function")
      node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v != null && k !== "disabled")
      node.setAttribute(k, String(v));
  }
  for (const c of children) {
    if (c == null || c === "") continue;
    node.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

export function Card(title, bodyChildren = []) {
  const card = el("section", { className: "card" });
  if (title) card.append(el("h2", { className: "card__title" }, [title]));
  for (const c of bodyChildren) {
    if (c) card.append(c);
  }
  return card;
}

export function hint(text) {
  return el("p", { className: "card__hint" }, [text]);
}

export function btnRow(...buttons) {
  return el("div", { className: "btn-row" }, buttons.filter(Boolean));
}

/**
 * @param {string} label
 * @param {{ variant?: string, disabled?: boolean, loading?: boolean, onClick?: (e: Event) => void }} opts
 */
export function Button(label, opts = {}) {
  const cls = ["btn", opts.variant ? `btn--${opts.variant}` : "", opts.loading ? "btn--loading" : ""]
    .filter(Boolean)
    .join(" ");
  return el(
    "button",
    {
      type: "button",
      className: cls,
      disabled: !!(opts.disabled || opts.loading),
      onClick: opts.onClick,
    },
    [label],
  );
}

export function StatusPill(label, tone = "") {
  return el("span", { className: `pill${tone ? ` pill--${tone}` : ""}` }, [label]);
}

const STATUS_ICON = { OK: "✓", FALTA: "✗", AVISO: "⚠", INFO: "ℹ" };
const STATUS_LABEL = { OK: "ok", FALTA: "falta", AVISO: "aviso", INFO: "info" };

export function Checklist(items = []) {
  const ul = el("ul", { className: "checklist" });
  for (const c of items) {
    const icon = STATUS_ICON[c.status] || c.status;
    const tone = STATUS_LABEL[c.status] || "";
    const li = el("li", { className: `checklist__item` });
    li.append(
      el("span", { className: `chk-icon chk--${tone}` }, [icon]),
      el("span", { className: "chk-body" }, [
        el("span", { className: "chk-label" }, [c.label]),
        c.detail ? el("span", { className: "chk-detail" }, [": " + c.detail]) : "",
        c.hint ? el("span", { className: "chk-hint" }, [" · " + c.hint]) : "",
      ]),
    );
    ul.append(li);
  }
  return ul;
}

export function KeyValue(pairs) {
  const dl = el("dl", { className: "kv" });
  for (const [k, v] of pairs) {
    dl.append(el("dt", {}, [k]), el("dd", {}, [String(v ?? "—")]));
  }
  return dl;
}

export function field(id, labelText, inputEl) {
  const wrap = el("div", { className: "field" });
  wrap.append(el("label", { for: id }, [labelText]), inputEl);
  return wrap;
}
