import { api, bindToast, toast } from "./api/client.js";
import {
  Button,
  Card,
  Checklist,
  KeyValue,
  StatusPill,
  btnRow,
  el,
  field,
  hint,
} from "./components/ui.js";

const NAV = [
  { id: "setup", label: "Instalação" },
  { id: "google", label: "Google" },
  { id: "whatsapp", label: "WhatsApp" },
  { id: "service", label: "Serviço" },
  { id: "mcp", label: "MCP" },
  { id: "config", label: "Config" },
  { id: "tools", label: "Tools" },
  { id: "logs", label: "Logs" },
];

/** @type {Record<string, HTMLElement>} */
const views = {};

/** @type {object | null} */
let state = null;

let pairTimer = null;
let activeView = "setup";

const refs = {};

export function mountApp(root) {
  const toastEl = el("div", { id: "toast", className: "toast" });
  document.body.append(toastEl);
  bindToast(toastEl);

  const shell = el("div", { className: "app-shell" });
  const sidebar = buildSidebar();
  const main = el("main", { className: "main" });
  const header = el("div", { className: "main__header" });
  refs.pills = el("div", { className: "pills" });
  header.append(
    el("div", {}, [el("h2", { style: "margin:0;font-size:1.05rem" }, ["Console"]), hint("Operação local · sem CLI")]),
    refs.pills,
  );
  refs.stack = el("div", { className: "view-stack" });
  main.append(header, refs.stack);
  shell.append(sidebar, main);
  root.append(shell);

  for (const item of NAV) {
    views[item.id] = el("div", { id: `view-${item.id}`, "data-view": item.id });
    refs.stack.append(views[item.id]);
  }

  bindGlobalActions();
  showView("setup");
  refreshAll().catch((e) => toast(e.message, "err"));
  setInterval(() => {
    refreshAll().catch(() => {});
  }, 30_000);
}

function buildSidebar() {
  const nav = el("nav", {});
  for (const item of NAV) {
    const link = el("a", {
      href: `#${item.id}`,
      className: "nav-link",
      "data-nav": item.id,
      onClick: (e) => {
        e.preventDefault();
        showView(item.id);
      },
    }, [item.label]);
    nav.append(link);
  }
  refs.navLinks = nav.querySelectorAll(".nav-link");
  const side = el("aside", { className: "sidebar" }, [
    el("div", { className: "sidebar__brand" }, [
      el("h1", {}, ["Integrator"]),
      el("p", {}, ["127.0.0.1 · admin"]),
    ]),
    nav,
    btnRow(Button("Recarregar", { variant: "secondary", onClick: () => refreshAll().catch((e) => toast(e.message, "err")) })),
  ]);
  return side;
}

function showView(id) {
  activeView = id;
  for (const [k, v] of Object.entries(views)) {
    v.style.display = k === id ? "block" : "none";
  }
  refs.navLinks?.forEach((a) => {
    a.classList.toggle("is-active", a.dataset.nav === id);
  });
}

async function refreshAll() {
  state = await api("/admin/api/state");
  updatePills();
  renderSetup();
  renderGoogle();
  renderWhatsApp();
  renderService();
  renderMcp();
  renderConfig();
  await renderTools();
}

function updatePills() {
  refs.pills.replaceChildren();
  const setup = state.setup || {};
  refs.pills.append(
    StatusPill(setup.configured ? "Google OK" : "Google —", setup.configured ? "ok" : "warn"),
  );
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  let waTone = "";
  let waLabel = "WA " + (st.state || "off");
  if (wa.error) {
    waTone = "err";
    waLabel = "WA erro";
  } else if (st.logged_in) {
    waTone = "ok";
    waLabel = "WA OK";
    if (state.effective?.whatsapp?.auto_transcribe) {
      refs.pills.append(StatusPill("🎙 transcrição", "ok"));
    }
  }
  refs.pills.append(StatusPill(waLabel, waTone));
  const fails = setup.critical_failures ?? 0;
  refs.pills.append(StatusPill(fails ? `MCP ${fails} falta` : "MCP OK", fails ? "warn" : "ok"));
}

function renderSetup() {
  const setup = state.setup || {};
  const credsArea = el("textarea", { id: "creds-json", rows: "4", placeholder: '{"installed":{...}}' });
  const summary = setup.configuration_label
    ? `Config: ${setup.configuration_label}${setup.next_step ? " · próximo: " + setup.next_step : ""}`
    : "—";

  const steps = el("div", { className: "wizard-steps" });
  const wizard = [
    ["deps", setup.deps_ok],
    ["google", setup.credentials_ready],
    ["conta", setup.configured],
    ["mcp", (setup.critical_failures ?? 1) === 0],
  ];
  wizard.forEach(([name, done], i) => {
    steps.append(
      el("span", {
        className: `wizard-step ${done ? "is-done" : i === wizard.findIndex(([, d]) => !d) ? "is-current" : ""}`,
      }, [name]),
    );
  });

  views.setup.replaceChildren(
    Card("Instalação", [
      steps,
      hint(summary),
      Checklist(setup.checks),
      btnRow(
        Button("Instalar dependências", { onClick: onSyncDeps }),
        Button("Abrir Google Cloud", { variant: "secondary", onClick: onGoogleSteps }),
        Button("Importar Downloads", { variant: "secondary", onClick: onImportCreds }),
      ),
      field("creds-json", "Ou colar JSON OAuth", credsArea),
      btnRow(Button("Salvar credentials.json", { variant: "secondary", onClick: () => onSaveCreds(credsArea) })),
    ]),
  );
}

function renderGoogle() {
  const tbody = el("tbody");
  (state.accounts?.accounts || []).forEach((a) => {
    const tr = el("tr");
    tr.append(
      el("td", {}, [`${a.id}${a.is_default ? " *" : ""}`]),
      el("td", {}, [a.email || "—"]),
      el("td", {}, [a.has_token ? "OK" : "—"]),
      el("td", {}, [
        btnRow(
          Button("Padrão", { variant: "secondary", onClick: () => setDefault(a.id) }),
          Button("Remover", { variant: "secondary", onClick: () => logout(a.id) }),
        ),
      ]),
    );
    tbody.append(tr);
  });
  const loginId = el("input", { id: "login_account", type: "text", placeholder: "pessoal" });
  const loginLabel = el("input", { id: "login_label", type: "text", placeholder: "Pessoal" });
  refs.loginStatus = el("span", { className: "card__hint" });

  views.google.replaceChildren(
    Card("Contas Google", [
      el("table", { className: "accounts-table" }, [
        el("thead", {}, [el("tr", {}, [el("th", {}, ["ID"]), el("th", {}, ["Email"]), el("th", {}, ["Token"]), el("th", {}, [""])])]),
        tbody,
      ]),
      el("div", { className: "grid-2", style: "margin-top:0.65rem" }, [
        field("login_account", "ID nova conta", loginId),
        field("login_label", "Nome (opcional)", loginLabel),
      ]),
      btnRow(Button("Conectar no navegador", { onClick: () => onGoogleLogin(loginId, loginLabel) })),
      refs.loginStatus,
    ]),
  );
}

function renderWhatsApp() {
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  refs.qrBox = el("div", { className: "qr-box" }, [hint("QR aparece ao iniciar pareamento")]);

  views.whatsapp.replaceChildren(
    Card("WhatsApp", [
      KeyValue([
        ["Estado", st.state || wa.error || "—"],
        ["Logado", st.logged_in ? "sim" : "não"],
        ["Sessão", state.paths?.whatsapp_session || "—"],
      ]),
      refs.qrBox,
      btnRow(
        Button("Parear (QR)", { onClick: () => startPair(false) }),
        Button("Parear do zero", { variant: "secondary", onClick: () => confirmFreshPair() }),
        Button("Parar", { variant: "secondary", onClick: stopPair }),
        Button("Reiniciar worker", { variant: "secondary", onClick: onWaDisconnect }),
        Button("Apagar sessão", { variant: "danger", onClick: onWaRemove }),
      ),
    ]),
  );
}

function renderService() {
  const svc = state.mac_service || {};
  let body;
  if (!svc.available) {
    body = KeyValue([["Plataforma", "LaunchAgent só macOS"]]);
  } else {
    body = KeyValue(
      Object.entries(svc)
        .filter(([k]) => k !== "available")
        .slice(0, 8),
    );
  }
  views.service.replaceChildren(
    Card("Serviço macOS", [
      body,
      hint("Fora do macOS: uv run integrator serve-http"),
      btnRow(
        Button("Instalar + iniciar", { onClick: () => svcAction("install") }),
        Button("Iniciar", { variant: "secondary", onClick: () => svcAction("start") }),
        Button("Parar", { variant: "secondary", onClick: () => svcAction("stop") }),
        Button("Desinstalar", { variant: "danger", onClick: () => confirmUninstallSvc() }),
      ),
    ]),
  );
}

function renderMcp() {
  refs.mcpChecks = el("div");
  views.mcp.replaceChildren(
    Card("MCP — Hermes & Claude", [
      hint("Reinicie Claude (⌘Q) após configurar; Hermes: /reload-mcp"),
      refs.mcpChecks,
      btnRow(
        Button("Configurar MCP", { onClick: onHermesSetup }),
        Button("Instalar Hermes", { variant: "secondary", onClick: onHermesInstall }),
        Button("Diagnóstico", { variant: "secondary", onClick: onHermesDoctor }),
      ),
    ]),
  );
  onHermesDoctor();
}

function renderConfig() {
  const w = state.effective.whatsapp;
  const t = state.effective.tools;
  const l = state.effective.logging;

  const ignore = el("textarea", { id: "ignore_numbers" });
  ignore.value = state.ignore_numbers_text || "";
  const fields = {
    auto_transcribe: el("input", { type: "checkbox", id: "auto_transcribe" }),
    transcribe_private_only: el("input", { type: "checkbox", id: "transcribe_private_only" }),
    transcribe_only_incoming: el("input", { type: "checkbox", id: "transcribe_only_incoming" }),
    transcribe_model: el("input", { id: "transcribe_model", type: "text" }),
    transcribe_language: el("input", { id: "transcribe_language", type: "text" }),
    transcribe_prefix: el("input", { id: "transcribe_prefix", type: "text" }),
    max_message_chars: el("input", { id: "max_message_chars", type: "number", min: "100" }),
    allowlist: el("input", { id: "allowlist", type: "text" }),
    denylist: el("input", { id: "denylist", type: "text" }),
    confirm_required_tools: el("input", { id: "confirm_required_tools", type: "text" }),
    log_level: el("select", { id: "log_level" }, [
      el("option", { value: "DEBUG" }, ["DEBUG"]),
      el("option", { value: "INFO" }, ["INFO"]),
      el("option", { value: "WARNING" }, ["WARNING"]),
      el("option", { value: "ERROR" }, ["ERROR"]),
    ]),
    audit_log_enabled: el("input", { type: "checkbox", id: "audit_log_enabled" }),
    audit_log_success: el("input", { type: "checkbox", id: "audit_log_success" }),
    log_tool_success: el("input", { type: "checkbox", id: "log_tool_success" }),
    persist_env: el("input", { type: "checkbox", id: "persist_env" }),
  };

  fields.auto_transcribe.checked = !!w.auto_transcribe;
  fields.transcribe_private_only.checked = !!w.transcribe_private_only;
  fields.transcribe_only_incoming.checked = !!w.transcribe_only_incoming;
  fields.transcribe_model.value = w.transcribe_model || "";
  fields.transcribe_language.value = w.transcribe_language || "";
  fields.transcribe_prefix.value = w.transcribe_prefix || "";
  fields.max_message_chars.value = String(w.max_message_chars || 800);
  fields.allowlist.value = t.allowlist || "";
  fields.denylist.value = t.denylist || "";
  fields.confirm_required_tools.value = t.confirm_required_tools || "";
  fields.log_level.value = (l.level || "INFO").toUpperCase();
  fields.audit_log_enabled.checked = !!l.audit_log_enabled;
  fields.audit_log_success.checked = !!l.audit_log_success;
  fields.log_tool_success.checked = !!l.log_tool_success;
  fields.persist_env.checked = true;

  refs.configFields = fields;
  refs.ignoreField = ignore;

  views.config.replaceChildren(
    Card("Números ignorados", [hint("Um por linha · tempo real"), ignore]),
    Card("WhatsApp · transcrição & MCP", [
      hint("Repetições no fim da transcrição (ex.: «slang slang…») são filtradas no worker; reinicie o serviço após atualizar o código."),
      el("div", { className: "grid-2" }, [
        el("label", { className: "check" }, [fields.auto_transcribe, " Auto-transcrição"]),
        el("label", { className: "check" }, [fields.transcribe_private_only, " Só privados"]),
        el("label", { className: "check" }, [fields.transcribe_only_incoming, " Só recebidos"]),
      ]),
      el("div", { className: "grid-2", style: "margin-top:0.65rem" }, [
        field("transcribe_model", "Modelo MLX", fields.transcribe_model),
        field("transcribe_language", "Idioma", fields.transcribe_language),
        field("transcribe_prefix", "Prefixo", fields.transcribe_prefix),
        field("max_message_chars", "Truncagem chars", fields.max_message_chars),
        field("allowlist", "Allowlist", fields.allowlist),
        field("denylist", "Denylist", fields.denylist),
        field("confirm_required_tools", "Confirm required", fields.confirm_required_tools),
        field("log_level", "Log nível", fields.log_level),
      ]),
      el("div", { className: "grid-2", style: "margin-top:0.5rem" }, [
        el("label", { className: "check" }, [fields.audit_log_enabled, " Audit"]),
        el("label", { className: "check" }, [fields.audit_log_success, " Audit sucesso"]),
        el("label", { className: "check" }, [fields.log_tool_success, " Log tool OK"]),
      ]),
      btnRow(
        Button("Salvar configuração", { onClick: saveConfig }),
        el("label", { className: "check" }, [fields.persist_env, " Persistir .env"]),
      ),
    ]),
  );
}

async function renderTools() {
  const data = await api("/admin/api/tools");
  const list = el("div", { className: "tools-grid" });
  (data.tools || []).forEach((t) => list.append(el("div", {}, [`• ${t.name}`])));
  views.tools.replaceChildren(
    Card("Tools MCP", [hint(`${data.count} tools MCP`), list]),
  );
}

function renderLogsPanel() {
  refs.logView = el("pre", { className: "log-view" }, ["(clique abaixo)"]);
  views.logs.replaceChildren(
    Card("Logs & falhas", [
      btnRow(
        Button("integrator.log", { variant: "secondary", onClick: () => loadLog("integrator") }),
        Button("errors.log", { variant: "secondary", onClick: () => loadLog("errors") }),
        Button("Falhas audit", { variant: "secondary", onClick: loadFailures }),
      ),
      refs.logView,
    ]),
  );
}

function bindGlobalActions() {
  renderLogsPanel();
}

function collectPayload() {
  const f = refs.configFields;
  return {
    persist_env: f.persist_env.checked,
    ignore_numbers_text: refs.ignoreField.value,
    whatsapp: {
      auto_transcribe: f.auto_transcribe.checked,
      transcribe_private_only: f.transcribe_private_only.checked,
      transcribe_only_incoming: f.transcribe_only_incoming.checked,
      transcribe_model: f.transcribe_model.value.trim(),
      transcribe_language: f.transcribe_language.value.trim() || null,
      transcribe_prefix: f.transcribe_prefix.value,
      max_message_chars: parseInt(f.max_message_chars.value, 10) || 800,
    },
    tools: {
      allowlist: f.allowlist.value.trim() || null,
      denylist: f.denylist.value.trim() || null,
      confirm_required_tools: f.confirm_required_tools.value.trim() || null,
    },
    logging: {
      level: f.log_level.value,
      audit_log_enabled: f.audit_log_enabled.checked,
      audit_log_success: f.audit_log_success.checked,
      log_tool_success: f.log_tool_success.checked,
    },
  };
}

async function saveConfig() {
  try {
    const data = await api("/admin/api/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectPayload()),
    });
    await refreshAll();
    let msg = "Salvo.";
    if (data.restart_recommended) msg += " Reinicie serviço p/ tools/modelo.";
    toast(msg, data.restart_recommended ? "warn" : "");
  } catch (e) {
    toast(e.message, "err");
  }
}

async function onSyncDeps() {
  await api("/admin/api/setup/sync", { method: "POST", body: "{}" });
  toast("uv sync rodando…");
  const poll = setInterval(async () => {
    const j = await api("/admin/api/setup/sync");
    if (j.status !== "running") {
      clearInterval(poll);
      toast(j.status === "ok" ? "Deps OK" : "Sync falhou", j.status === "ok" ? "" : "err");
      refreshAll();
    }
  }, 2000);
}

async function onGoogleSteps() {
  await api("/admin/api/setup/google-steps", { method: "POST", body: "{}" });
  toast("Passos Google abertos");
}

async function onImportCreds() {
  const r = await api("/admin/api/setup/credentials", { method: "POST", body: "{}" });
  toast(r.ok ? "Credentials OK" : r.error || "Falha", r.ok ? "" : "err");
  refreshAll();
}

async function onSaveCreds(textarea) {
  const json = textarea.value.trim();
  if (!json) return toast("Cole o JSON", "warn");
  const r = await api("/admin/api/setup/credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ json }),
  });
  toast(r.ok ? "Salvo" : r.error, r.ok ? "" : "err");
  refreshAll();
}

async function onGoogleLogin(loginId, loginLabel) {
  const account_id = loginId.value.trim() || "pessoal";
  const label = loginLabel.value.trim() || null;
  await api("/admin/api/google/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id, label }),
  });
  toast("OAuth no navegador…");
  const poll = setInterval(async () => {
    const j = await api("/admin/api/google/login");
    if (refs.loginStatus) refs.loginStatus.textContent = j.status || "";
    if (j.status === "ok") {
      clearInterval(poll);
      toast("Conta conectada");
      refreshAll();
    }
    if (j.status === "error") {
      clearInterval(poll);
      toast(j.error, "err");
    }
  }, 1500);
}

async function setDefault(id) {
  await api("/admin/api/google/default", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id: id }),
  });
  toast("Padrão atualizado");
  refreshAll();
}

async function logout(id) {
  if (!confirm(`Remover conta ${id}?`)) return;
  await api("/admin/api/google/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id: id }),
  });
  refreshAll();
}

function showQr(b64) {
  if (!refs.qrBox) return;
  if (!b64) {
    refs.qrBox.replaceChildren(hint("Aguardando QR…"));
    return;
  }
  refs.qrBox.replaceChildren(
    el("img", { alt: "QR WhatsApp", src: `data:image/png;base64,${b64}` }),
    hint("WhatsApp → Dispositivos conectados"),
  );
}

async function pollPair() {
  try {
    const r = await api("/admin/api/whatsapp/pair?action=poll");
    const d = r.data || {};
    if (d.qr_png_base64) showQr(d.qr_png_base64);
    if (d.logged_in) {
      clearInterval(pairTimer);
      pairTimer = null;
      toast("WhatsApp pareado!");
      refs.qrBox.replaceChildren(hint("Conectado."));
      refreshAll();
    }
  } catch {
    /* transient */
  }
}

async function startPair(fresh) {
  if (pairTimer) clearInterval(pairTimer);
  showQr(null);
  await api("/admin/api/whatsapp/pair?action=start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fresh: !!fresh }),
  });
  pairTimer = setInterval(pollPair, 1500);
  pollPair();
  toast("Escaneie o QR");
}

function confirmFreshPair() {
  if (confirm("Apaga sessão antes?")) startPair(true);
}

async function stopPair() {
  if (pairTimer) clearInterval(pairTimer);
  await api("/admin/api/whatsapp/pair?action=stop");
  if (refs.qrBox) refs.qrBox.replaceChildren(hint("—"));
}

async function onWaDisconnect() {
  await api("/admin/api/whatsapp/session", { method: "POST", body: "{}" });
  toast("Worker reiniciado");
  refreshAll();
}

async function onWaRemove() {
  if (!confirm("Apagar sessão WhatsApp local?")) return;
  await api("/admin/api/whatsapp/session", { method: "DELETE", body: "{}" });
  toast("Sessão removida");
  refreshAll();
}

async function svcAction(action) {
  const data = await api("/admin/api/service", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!data.ok) throw new Error(data.error);
  toast(`Serviço: ${action}`);
  refreshAll();
}

function confirmUninstallSvc() {
  if (!confirm("Desinstalar LaunchAgent?")) return;
  svcAction("uninstall").catch((e) => toast(e.message, "err"));
}

async function onHermesDoctor() {
  const d = await api("/admin/api/hermes/doctor");
  refs.mcpChecks.replaceChildren(Checklist(d.checks));
}

async function onHermesSetup() {
  const r = await api("/admin/api/hermes/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: "sse", yes: true }),
  });
  toast(r.ok ? "MCP gravado" : r.error || "Falha", r.ok ? "" : "err");
  if (r.ok && r.restart_hints?.[0]) toast(r.restart_hints[0]);
}

async function onHermesInstall() {
  await api("/admin/api/hermes/install", { method: "POST", body: "{}" });
  toast("Link Hermes aberto");
}

async function loadLog(name) {
  const data = await api(`/admin/api/logs?file=${encodeURIComponent(name)}&lines=200`);
  refs.logView.textContent = data.text || "";
}

async function loadFailures() {
  const data = await api("/admin/api/failures?limit=30");
  refs.logView.textContent =
    (data.failures || []).map((r) => `${r.ts} | ${r.tool} | ${r.error}`).join("\n") ||
    "Nenhuma falha recente";
}
