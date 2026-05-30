/**
 * @param {string} tag
 * @param {Record<string, string | function>} [attrs]
 * @param {(Node|string)[]} [children]
 */
export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "className") node.className = v;
    else if (k === "disabled") node.disabled = !!v;
    else if (k.startsWith("on") && typeof v === "function") {
      node.addEventListener(k.slice(2).toLowerCase(), v);
    } else if (v != null && k !== "disabled") node.setAttribute(k, String(v));
  }
  for (const c of children) {
    node.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

export function Card(title, bodyChildren = []) {
  const card = el("section", { className: "card" });
  card.append(el("h2", { className: "card__title" }, [title]));
  for (const c of bodyChildren) card.append(c);
  return card;
}

export function hint(text) {
  return el("p", { className: "card__hint" }, [text]);
}

export function btnRow(...buttons) {
  return el("div", { className: "btn-row" }, buttons);
}

/**
 * @param {string} label
 * @param {{ variant?: string, disabled?: boolean, loading?: boolean, onClick?: () => void }} opts
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
  return el("span", { className: `pill pill--${tone}`.trim() }, [label]);
}

export function Checklist(items = []) {
  const ul = el("ul", { className: "checklist" });
  for (const c of items) {
    ul.append(
      el("li", {}, [
        el("span", { className: `st-${c.status}` }, [`[${c.status}] `]),
        `${c.label}: ${c.detail}`,
      ]),
    );
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
