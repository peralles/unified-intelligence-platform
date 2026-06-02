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

// ─── Navigation ──────────────────────────────────────────────────────────────

const NAV = [
  { id: "painel",      label: "Painel",       icon: "📊" },
  { id: "google",      label: "Google",        icon: "✉️" },
  { id: "whatsapp",    label: "WhatsApp",      icon: "💬" },
  { id: "servico",     label: "Serviço",       icon: "⚡" },
  { id: "mcp",         label: "MCP / Hermes",  icon: "🔗" },
  { id: "config",      label: "Configuração",  icon: "⚙️" },
  { id: "ferramentas", label: "Ferramentas",   icon: "🛠️" },
  { id: "logs",        label: "Logs",          icon: "📋" },
];

// ─── App state ───────────────────────────────────────────────────────────────

const views = {};
let state = null;
let pairTimer = null;
let activeView = "painel";
let configDirty = false;
let toolsLoaded = false;
let mcpDoctorLoaded = false;
const refs = {};

// ─── Mount ───────────────────────────────────────────────────────────────────

export function mountApp(root) {
  const toastEl = el("div", { id: "toast", className: "toast" });
  document.body.append(toastEl);
  bindToast(toastEl);

  const sidebar = buildSidebar();
  const main = el("main", { className: "main" });

  refs.headerPills = el("div", { className: "pills" });
  refs.lastUpdated = el("span", { className: "last-updated" });
  const header = el("div", { className: "main__header" }, [
    el("div", { className: "main__header-left" }, [
      el("h2", { className: "app-title" }, ["Console de Administração"]),
      refs.lastUpdated,
    ]),
    refs.headerPills,
  ]);

  refs.stack = el("div", { className: "view-stack" });
  main.append(header, refs.stack);

  const shell = el("div", { className: "app-shell" }, [sidebar, main]);
  root.append(shell);

  for (const item of NAV) {
    views[item.id] = el("div", { id: `view-${item.id}`, "data-view": item.id });
    refs.stack.append(views[item.id]);
  }

  bindGlobalActions();
  showView("painel");
  refreshAll().catch((e) => toast(e.message, "err"));
  setInterval(() => refreshAll().catch(() => {}), 30_000);
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────

function buildSidebar() {
  refs.navBadges = {};
  const nav = el("nav", {});
  for (const item of NAV) {
    const badge = el("span", { className: "nav-badge" });
    refs.navBadges[item.id] = badge;
    const link = el("a", {
      href: `#${item.id}`,
      className: "nav-link",
      "data-nav": item.id,
      onClick: (e) => { e.preventDefault(); showView(item.id); },
    }, [
      el("span", { className: "nav-icon" }, [item.icon]),
      el("span", { className: "nav-label" }, [item.label]),
      badge,
    ]);
    nav.append(link);
  }
  refs.navLinks = nav.querySelectorAll(".nav-link");

  return el("aside", { className: "sidebar" }, [
    el("div", { className: "sidebar__brand" }, [
      el("div", { className: "brand-mark" }, ["⚡"]),
      el("div", {}, [
        el("h1", {}, ["Integrator"]),
        el("p", {}, ["Administração local"]),
      ]),
    ]),
    nav,
    el("div", { className: "sidebar__footer" }, [
      Button("↺  Atualizar", {
        variant: "secondary",
        onClick: (e) => withLoading(e.currentTarget, () => refreshAll()),
      }),
    ]),
  ]);
}

function showView(id) {
  activeView = id;
  for (const [k, v] of Object.entries(views)) {
    v.style.display = k === id ? "" : "none";
  }
  refs.navLinks?.forEach((a) =>
    a.classList.toggle("is-active", a.dataset.nav === id),
  );
  // Lazy loads
  if (id === "ferramentas" && !toolsLoaded) loadTools();
  if (id === "mcp" && !mcpDoctorLoaded) {
    mcpDoctorLoaded = true;
    onHermesDoctor();
  }
}

// ─── Refresh ─────────────────────────────────────────────────────────────────

async function refreshAll() {
  state = await api("/admin/api/state");
  refs.lastUpdated.textContent = `Atualizado às ${new Date().toLocaleTimeString("pt-BR")}`;
  updateHeaderPills();
  updateNavBadges();
  renderPainel();
  renderGoogle();
  renderWhatsApp();
  renderServico();
  renderMcp();
  if (!configDirty) renderConfig();
}

function updateHeaderPills() {
  refs.headerPills.replaceChildren();
  const setup = state.setup || {};
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};

  refs.headerPills.append(
    StatusPill(setup.configured ? "Google ✓" : "Google —", setup.configured ? "ok" : "warn"),
  );

  let waTone = "", waLabel = "WA " + (st.state || "—");
  if (wa.error) { waTone = "err"; waLabel = "WA erro"; }
  else if (st.logged_in) {
    waTone = "ok"; waLabel = "WA ✓";
    if (state.effective?.whatsapp?.auto_transcribe)
      refs.headerPills.append(StatusPill("🎙 transcrição", "ok"));
  }
  refs.headerPills.append(StatusPill(waLabel, waTone));

  const fails = setup.critical_failures ?? 0;
  refs.headerPills.append(
    StatusPill(fails ? `MCP ${fails} problema(s)` : "MCP ✓", fails ? "warn" : "ok"),
  );
}

function updateNavBadges() {
  const setup = state.setup || {};
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const svc = state.mac_service || {};
  const fails = setup.critical_failures ?? 0;
  setNavBadge("google",      setup.configured ? "ok" : "warn");
  setNavBadge("whatsapp",    wa.error ? "err" : st.logged_in ? "ok" : "warn");
  setNavBadge("mcp",         fails === 0 ? "ok" : "warn");
  setNavBadge("servico",     svc.running ? "ok" : "");
}

function setNavBadge(id, tone) {
  const b = refs.navBadges?.[id];
  if (!b) return;
  b.className = `nav-badge${tone ? ` nav-badge--${tone}` : ""}`;
  b.textContent = tone === "err" ? "●" : tone === "warn" ? "●" : tone === "ok" ? "●" : "";
}

// ─── Painel (dashboard) ──────────────────────────────────────────────────────

function renderPainel() {
  const setup = state.setup || {};
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const fails = setup.critical_failures ?? 0;
  const svc = state.mac_service || {};

  const googleOk = !!setup.configured;
  const waOk = !!st.logged_in && !wa.error;
  const mcpOk = fails === 0;
  const allOk = googleOk && waOk && mcpOk;

  // Status banner
  const banner = allOk
    ? el("div", { className: "status-banner status-banner--ok" }, [
        el("span", { className: "banner-icon" }, ["✓"]),
        " Tudo funcionando — integrador pronto para uso.",
      ])
    : el("div", { className: "status-banner status-banner--warn" }, [
        el("span", { className: "banner-icon" }, ["⚠"]),
        " " + (setup.next_step ? `Próximo passo: ${setup.next_step}` : "Complete a configuração abaixo."),
      ]);

  // Status cards
  const cards = el("div", { className: "status-cards" }, [
    buildStatusCard(
      "✉️  Google",
      googleOk ? "Conectado" : "Não configurado",
      googleOk ? "ok" : "warn",
      googleOk ? `Conta: ${(state.accounts?.accounts || []).find((a) => a.is_default)?.email || "configurada"}` : "Configure uma conta Google para usar Gmail e Agenda.",
      { label: googleOk ? "Gerenciar" : "Configurar →", view: "google" },
    ),
    buildStatusCard(
      "💬  WhatsApp",
      waOk ? "Conectado" : wa.error ? "Erro" : st.state || "Desconectado",
      waOk ? "ok" : wa.error ? "err" : "warn",
      waOk
        ? `Transcrição automática: ${state.effective?.whatsapp?.auto_transcribe ? "ativa" : "desativada"}`
        : wa.error ? String(wa.error) : "Pareie o WhatsApp para usar o agente.",
      { label: waOk ? "Gerenciar" : "Parear →", view: "whatsapp" },
    ),
    buildStatusCard(
      "🔗  MCP / Hermes",
      mcpOk ? "Configurado" : `${fails} problema(s)`,
      mcpOk ? "ok" : "warn",
      mcpOk
        ? "Integração com agentes ativa."
        : "Configure para que agentes possam usar as ferramentas.",
      { label: "Ver MCP →", view: "mcp" },
    ),
  ]);

  // URL de acesso
  const svcUrl = state.service?.url_admin || "";
  const urlCard = svcUrl ? Card("Endereço do console", [
    hint("Acesse este endereço no navegador para abrir o console de administração."),
    el("div", { className: "url-row" }, [
      el("code", { className: "url-code" }, [svcUrl]),
      Button("Copiar", {
        variant: "secondary",
        onClick: () => {
          navigator.clipboard?.writeText(svcUrl).catch(() => {});
          toast("URL copiada.");
        },
      }),
    ]),
  ]) : null;

  // Wizard (only if setup incomplete)
  const wizardSteps = [
    ["Dependências instaladas",     setup.deps_ok],
    ["Credenciais OAuth configuradas", setup.credentials_ready],
    ["Conta Google conectada",      setup.configured],
    ["MCP / Hermes configurado",    mcpOk],
  ];
  const wizardDone = wizardSteps.every(([, d]) => d);
  const wizard = !wizardDone ? Card("Passos de configuração inicial", [
    el("ol", { className: "setup-steps" },
      wizardSteps.map(([label, done]) =>
        el("li", { className: `setup-step ${done ? "step-done" : "step-todo"}` }, [
          el("span", { className: "step-icon" }, [done ? "✓" : "○"]),
          " " + label,
        ]),
      ),
    ),
    btnRow(
      Button("Instalar dependências", {
        disabled: setup.deps_ok,
        onClick: (e) => withLoading(e.currentTarget, onSyncDeps),
      }),
      Button("Configurar Google →", {
        variant: "secondary",
        onClick: () => showView("google"),
      }),
      Button("Configurar MCP →", {
        variant: "secondary",
        onClick: () => showView("mcp"),
      }),
    ),
  ]) : null;

  views.painel.replaceChildren(
    banner,
    cards,
    ...(urlCard ? [urlCard] : []),
    ...(wizard ? [wizard] : []),
  );
}

function buildStatusCard(title, statusText, tone, detail, action) {
  return el("div", { className: `status-card status-card--${tone}` }, [
    el("div", { className: "status-card__head" }, [
      el("span", { className: "status-card__title" }, [title]),
      el("span", { className: `badge badge--${tone}` }, [statusText]),
    ]),
    el("p", { className: "status-card__detail" }, [detail]),
    Button(action.label, {
      variant: "secondary",
      onClick: () => showView(action.view),
    }),
  ]);
}

// ─── Google ──────────────────────────────────────────────────────────────────

function renderGoogle() {
  const accounts = state.accounts?.accounts || [];
  const setup = state.setup || {};

  // Accounts table
  const tbody = el("tbody");
  if (!accounts.length) {
    tbody.append(el("tr", {}, [
      el("td", { colspan: "4", className: "empty-cell" }, ["Nenhuma conta conectada ainda."]),
    ]));
  } else {
    for (const a of accounts) {
      tbody.append(el("tr", {}, [
        el("td", {}, [
          a.is_default
            ? el("span", {}, [a.id, " ", el("span", { className: "badge badge--ok" }, ["padrão"])])
            : a.id,
        ]),
        el("td", {}, [a.email || "—"]),
        el("td", {}, [
          el("span", { className: `badge badge--${a.has_token ? "ok" : "warn"}` }, [
            a.has_token ? "autenticado" : "sem token",
          ]),
        ]),
        el("td", { className: "td-actions" }, [
          btnRow(
            ...(a.is_default ? [] : [
              Button("Tornar padrão", {
                variant: "secondary",
                onClick: (e) => withLoading(e.currentTarget, () => setDefault(a.id)),
              }),
            ]),
            Button("Remover", {
              variant: "danger",
              onClick: (e) => withLoading(e.currentTarget, () => logout(a.id)),
            }),
          ),
        ]),
      ]));
    }
  }

  // Login form
  const loginId    = el("input", { id: "login_account", type: "text", placeholder: "pessoal" });
  const loginLabel = el("input", { id: "login_label",   type: "text", placeholder: "Pessoal (opcional)" });
  refs.loginStatus = el("p", { className: "card__hint", style: "min-height:1.4em" });

  // Credentials card (only if credentials missing)
  const credsArea = el("textarea", {
    id: "creds-json", rows: "4",
    placeholder: '{"installed":{"client_id":"...","client_secret":"...",...}}',
  });
  const credsCard = !setup.credentials_ready ? Card("Arquivo OAuth (client_secret.json)", [
    hint("Baixe do Google Cloud Console (APIs & Services → Credentials) e cole o conteúdo abaixo, ou use 'Importar'."),
    btnRow(
      Button("Abrir Google Cloud →", {
        variant: "secondary",
        onClick: (e) => withLoading(e.currentTarget, onGoogleSteps),
      }),
      Button("Importar de ~/Downloads", {
        variant: "secondary",
        onClick: (e) => withLoading(e.currentTarget, onImportCreds),
      }),
    ),
    el("div", { className: "field", style: "margin-top:0.65rem" }, [
      el("label", { for: "creds-json" }, ["Ou cole o JSON aqui:"]),
      credsArea,
    ]),
    btnRow(
      Button("Salvar JSON colado", {
        onClick: (e) => withLoading(e.currentTarget, () => onSaveCreds(credsArea)),
      }),
    ),
  ]) : null;

  views.google.replaceChildren(
    Card("Contas Google conectadas", [
      hint("Cada conta dá acesso ao Gmail e Google Agenda do usuário correspondente."),
      el("div", { className: "table-wrap" }, [
        el("table", { className: "accounts-table" }, [
          el("thead", {}, [el("tr", {}, [
            el("th", {}, ["Conta"]),
            el("th", {}, ["E-mail"]),
            el("th", {}, ["Status"]),
            el("th", {}, [""]),
          ])]),
          tbody,
        ]),
      ]),
    ]),
    Card("Conectar nova conta Google", [
      hint("Abrirá o navegador para autorização OAuth. Conclua no navegador e aguarde."),
      el("div", { className: "grid-2", style: "margin-top:0.5rem" }, [
        field("login_account", "ID da conta (ex: pessoal, trabalho)", loginId),
        field("login_label", "Nome amigável (opcional)", loginLabel),
      ]),
      btnRow(
        Button("Abrir autorização no navegador →", {
          onClick: (e) => withLoading(e.currentTarget, () => onGoogleLogin(loginId, loginLabel)),
        }),
      ),
      refs.loginStatus,
    ]),
    ...(credsCard ? [credsCard] : []),
  );
}

// ─── WhatsApp ────────────────────────────────────────────────────────────────

function renderWhatsApp() {
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const isConnected = !!st.logged_in && !wa.error;

  refs.qrBox = el("div", { className: "qr-box" }, [
    hint("O QR code aparecerá aqui quando o pareamento for iniciado."),
  ]);

  const statusKv = [
    ["Conexão", isConnected ? "✓ Conectado" : wa.error ? `Erro: ${wa.error}` : (st.state || "Desconectado")],
    ...(st.push_name ? [["Dispositivo", st.push_name]] : []),
    ...(isConnected && state.effective?.whatsapp
      ? [["Transcrição automática", state.effective.whatsapp.auto_transcribe ? "Ativa" : "Desativada"]]
      : []),
  ];

  views.whatsapp.replaceChildren(
    Card("Status da conexão", [
      KeyValue(statusKv),
      btnRow(
        Button("Reiniciar conexão", {
          variant: "secondary",
          onClick: (e) => withLoading(e.currentTarget, onWaDisconnect),
        }),
        Button("Apagar sessão local", {
          variant: "danger",
          onClick: (e) => withLoading(e.currentTarget, onWaRemove),
        }),
      ),
      hint("'Reiniciar' reconecta sem apagar dados. 'Apagar sessão' remove tudo e exige novo pareamento."),
    ]),
    Card("Parear dispositivo WhatsApp", [
      hint("Abra o WhatsApp no celular → Menu (⋮) → Dispositivos conectados → Adicionar dispositivo → escaneie o QR."),
      refs.qrBox,
      btnRow(
        Button(isConnected ? "↺ Reparear dispositivo" : "▶ Iniciar pareamento (QR)", {
          onClick: (e) => withLoading(e.currentTarget, () => startPair(false)),
        }),
        Button("Parear do zero (nova sessão)", {
          variant: "secondary",
          onClick: () => confirmFreshPair(),
        }),
        Button("Parar", {
          variant: "secondary",
          onClick: (e) => withLoading(e.currentTarget, stopPair),
        }),
      ),
    ]),
  );
}

// ─── Serviço ─────────────────────────────────────────────────────────────────

function renderServico() {
  const svc = state.mac_service || {};

  if (!svc.available) {
    views.servico.replaceChildren(
      Card("Serviço em segundo plano", [
        hint("Inicie o servidor manualmente com o comando abaixo e mantenha o terminal aberto. Para execução contínua, use systemd ou Docker."),
        el("pre", { className: "code-block" }, ["uv run integrator serve-http"]),
        hint("O LaunchAgent automático está disponível apenas no macOS."),
      ]),
    );
    return;
  }

  const kvPairs = Object.entries(svc)
    .filter(([k]) => !["available"].includes(k))
    .map(([k, v]) => {
      const LABELS = {
        installed: "Instalado", running: "Em execução", pid: "PID",
        status: "Status", plist_path: "Arquivo plist", host: "Host", port: "Porta",
        label: "Label",
      };
      return [LABELS[k] || k, String(v ?? "—")];
    });

  views.servico.replaceChildren(
    Card("Serviço macOS (LaunchAgent)", [
      hint("O LaunchAgent inicia o servidor automaticamente ao fazer login no macOS."),
      KeyValue(kvPairs),
      btnRow(
        Button("Instalar e iniciar", {
          disabled: !!(svc.installed && svc.running),
          onClick: (e) => withLoading(e.currentTarget, () => svcAction("install")),
        }),
        Button("Iniciar", {
          variant: "secondary",
          disabled: !!svc.running,
          onClick: (e) => withLoading(e.currentTarget, () => svcAction("start")),
        }),
        Button("Parar", {
          variant: "secondary",
          disabled: !svc.running,
          onClick: (e) => withLoading(e.currentTarget, () => svcAction("stop")),
        }),
        Button("Desinstalar", {
          variant: "danger",
          onClick: () => confirmUninstallSvc(),
        }),
      ),
    ]),
  );
}

// ─── MCP / Hermes ────────────────────────────────────────────────────────────

function renderMcp() {
  if (refs.mcpCard) return; // structure already rendered; only doctor updates it
  refs.mcpChecks = el("div", { className: "mcp-checks" }, [hint("Carregando diagnóstico…")]);
  refs.mcpCard = Card("Hermes & Claude Desktop", [
    hint("Configure os agentes de IA para usar as ferramentas do integrador. Após configurar, reinicie o Claude (⌘Q) ou use /reload-mcp no Hermes."),
    refs.mcpChecks,
    btnRow(
      Button("Configurar integração MCP", {
        onClick: (e) => withLoading(e.currentTarget, onHermesSetup),
      }),
      Button("Instalar Hermes", {
        variant: "secondary",
        onClick: (e) => withLoading(e.currentTarget, onHermesInstall),
      }),
      Button("↺ Rodar diagnóstico", {
        variant: "secondary",
        onClick: (e) => withLoading(e.currentTarget, onHermesDoctor),
      }),
    ),
  ]);
  views.mcp.replaceChildren(refs.mcpCard);
}

// ─── Configuração ────────────────────────────────────────────────────────────

function renderConfig() {
  if (configDirty) return;

  const w = state.effective?.whatsapp || {};
  const t = state.effective?.tools || {};
  const l = state.effective?.logging || {};

  function inp(id, type = "text") {
    return el("input", { id, type, ...(type === "number" ? { min: "1" } : {}) });
  }
  function chk(id) { return el("input", { type: "checkbox", id }); }

  const f = {
    auto_transcribe:              chk("auto_transcribe"),
    transcribe_private_only:      chk("transcribe_private_only"),
    transcribe_only_incoming:     chk("transcribe_only_incoming"),
    transcribe_model:             inp("transcribe_model"),
    transcribe_language:          inp("transcribe_language"),
    transcribe_prefix:            inp("transcribe_prefix"),
    max_message_chars:            inp("max_message_chars", "number"),
    max_cached_messages_per_chat: inp("max_cached_per_chat", "number"),
    allowlist:                    inp("allowlist"),
    denylist:                     inp("denylist"),
    confirm_required_tools:       inp("confirm_required_tools"),
    log_level: el("select", { id: "log_level" }, [
      ["DEBUG", "INFO", "WARNING", "ERROR"].map((v) => el("option", { value: v }, [v])),
    ].flat()),
    audit_log_enabled:  chk("audit_log_enabled"),
    audit_log_success:  chk("audit_log_success"),
    log_tool_success:   chk("log_tool_success"),
    persist_env:        chk("persist_env"),
  };

  // Set values from server state
  f.auto_transcribe.checked           = !!w.auto_transcribe;
  f.transcribe_private_only.checked   = !!w.transcribe_private_only;
  f.transcribe_only_incoming.checked  = !!w.transcribe_only_incoming;
  f.transcribe_model.value            = w.transcribe_model || "";
  f.transcribe_language.value         = w.transcribe_language || "";
  f.transcribe_prefix.value           = w.transcribe_prefix || "";
  f.max_message_chars.value           = String(w.max_message_chars || 800);
  f.max_cached_messages_per_chat.value = String(w.max_cached_messages_per_chat || 5000);
  f.allowlist.value                   = t.allowlist || "";
  f.denylist.value                    = t.denylist || "";
  f.confirm_required_tools.value      = t.confirm_required_tools || "";
  f.log_level.value                   = (l.level || "INFO").toUpperCase();
  f.audit_log_enabled.checked         = !!l.audit_log_enabled;
  f.audit_log_success.checked         = !!l.audit_log_success;
  f.log_tool_success.checked          = !!l.log_tool_success;
  f.persist_env.checked               = true;

  refs.configFields = f;

  const ignore = el("textarea", {
    id: "ignore_numbers", rows: "5",
    placeholder: "5511999999999\n5521888888888\n(um número por linha)",
  });
  ignore.value = state.ignore_numbers_text || "";
  refs.ignoreField = ignore;

  refs.configDirtyHint = el("p", {
    className: "card__hint dirty-hint",
    style: "display:none;color:var(--warn)",
  }, ["● Alterações não salvas"]);

  function markDirty() {
    configDirty = true;
    if (refs.configDirtyHint) refs.configDirtyHint.style.display = "";
  }
  Object.values(f).forEach((el_) => {
    el_.addEventListener("change", markDirty);
    el_.addEventListener("input", markDirty);
  });
  ignore.addEventListener("input", markDirty);

  views.config.replaceChildren(
    Card("Transcrição automática de áudio (WhatsApp)", [
      hint("Transcreve mensagens de voz usando Whisper (mlx-whisper). Requer Apple Silicon."),
      el("div", { className: "check-group" }, [
        el("label", { className: "check" }, [f.auto_transcribe, " Ativar transcrição automática"]),
        el("label", { className: "check" }, [f.transcribe_private_only, " Apenas chats privados (não grupos)"]),
        el("label", { className: "check" }, [f.transcribe_only_incoming, " Apenas mensagens recebidas"]),
      ]),
      el("div", { className: "grid-2", style: "margin-top:0.75rem" }, [
        field("transcribe_model", "Modelo Whisper", f.transcribe_model),
        field("transcribe_language", "Idioma (pt, en, auto…)", f.transcribe_language),
        field("transcribe_prefix", "Prefixo da transcrição", f.transcribe_prefix),
        field("max_message_chars", "Máximo de caracteres por mensagem", f.max_message_chars),
        field("max_cached_per_chat", "Mensagens em cache por conversa", f.max_cached_messages_per_chat),
      ]),
    ]),
    Card("Números ignorados na transcrição", [
      hint("Mensagens desses números não serão transcritas automaticamente. Um número por linha, apenas dígitos."),
      el("div", { className: "field" }, [ignore]),
    ]),
    Card("Controle de ferramentas MCP", [
      hint("Deixe em branco para permitir todas. Separe nomes de ferramentas por vírgula."),
      el("div", { className: "grid-2" }, [
        field("allowlist", "Permitir apenas (allowlist)", f.allowlist),
        field("denylist",  "Bloquear (denylist)",         f.denylist),
        field("confirm_required_tools", "Exigir confirmação explícita", f.confirm_required_tools),
      ]),
      hint("Ferramentas que exigem confirmação: o agente deve incluir confirm=true antes de executar."),
    ]),
    Card("Logs e auditoria", [
      el("div", { className: "grid-2" }, [
        field("log_level", "Nível de log", f.log_level),
      ]),
      el("div", { className: "check-group", style: "margin-top:0.65rem" }, [
        el("label", { className: "check" }, [f.audit_log_enabled, " Gravar log de auditoria (recomendado)"]),
        el("label", { className: "check" }, [f.audit_log_success, " Incluir ações bem-sucedidas no audit"]),
        el("label", { className: "check" }, [f.log_tool_success,  " Registrar uso de ferramentas no log"]),
      ]),
    ]),
    el("div", { className: "config-save-bar" }, [
      refs.configDirtyHint,
      btnRow(
        Button("💾  Salvar configurações", {
          onClick: (e) => withLoading(e.currentTarget, saveConfig),
        }),
        Button("↺  Descartar alterações", {
          variant: "secondary",
          onClick: () => { configDirty = false; renderConfig(); },
        }),
        el("label", { className: "check" }, [
          f.persist_env,
          " Salvar no .env (persistir após reinício)",
        ]),
      ),
    ]),
  );
}

// ─── Ferramentas ─────────────────────────────────────────────────────────────

function bindGlobalActions() {
  renderLogsPanel();
  views.ferramentas.replaceChildren(
    el("div", { className: "view-placeholder" }, [hint("Carregando…")]),
  );
}

async function loadTools() {
  toolsLoaded = true;
  try {
    const data = await api("/admin/api/tools");
    const tools = data.tools || [];
    const list = el("div", { className: "tools-grid" });
    tools.forEach((t) =>
      list.append(
        el("div", { className: "tool-item" }, [
          el("code", { className: "tool-name" }, [t.name]),
          t.description
            ? el("span", { className: "tool-desc" }, [
                t.description.slice(0, 90) + (t.description.length > 90 ? "…" : ""),
              ])
            : "",
        ]),
      ),
    );
    views.ferramentas.replaceChildren(
      Card(`Ferramentas MCP disponíveis — ${tools.length} no total`, [
        hint("Estas são as ações que os agentes de IA podem executar através deste integrador."),
        list,
      ]),
    );
  } catch {
    toast("Erro ao carregar ferramentas.", "err");
  }
}

// ─── Logs ────────────────────────────────────────────────────────────────────

function renderLogsPanel() {
  if (refs.logView) return;
  refs.logView = el("pre", { className: "log-view" }, ["Clique em um botão abaixo para carregar o log."]);
  views.logs.replaceChildren(
    Card("Logs do sistema", [
      hint("Últimas linhas dos arquivos de log. Use para diagnosticar problemas."),
      btnRow(
        Button("integrator.log", {
          variant: "secondary",
          onClick: (e) => withLoading(e.currentTarget, () => loadLog("integrator")),
        }),
        Button("errors.log", {
          variant: "secondary",
          onClick: (e) => withLoading(e.currentTarget, () => loadLog("errors")),
        }),
        Button("Falhas de auditoria", {
          variant: "secondary",
          onClick: (e) => withLoading(e.currentTarget, loadFailures),
        }),
        Button("↺  Atualizar", {
          variant: "secondary",
          onClick: (e) => withLoading(e.currentTarget, () => loadLog(refs.currentLog || "integrator")),
        }),
      ),
      refs.logView,
    ]),
  );
}

// ─── Loading helper ──────────────────────────────────────────────────────────

function withLoading(btn, fn) {
  if (btn && typeof btn.classList !== "undefined") {
    btn.disabled = true;
    btn.classList.add("btn--loading");
  }
  return Promise.resolve()
    .then(fn)
    .catch((e) => toast(e.message || "Erro inesperado.", "err"))
    .finally(() => {
      if (btn && typeof btn.classList !== "undefined") {
        btn.disabled = false;
        btn.classList.remove("btn--loading");
      }
    });
}

// ─── Config actions ──────────────────────────────────────────────────────────

function collectPayload() {
  const f = refs.configFields;
  return {
    persist_env: f.persist_env.checked,
    ignore_numbers_text: refs.ignoreField.value,
    whatsapp: {
      auto_transcribe:              f.auto_transcribe.checked,
      transcribe_private_only:      f.transcribe_private_only.checked,
      transcribe_only_incoming:     f.transcribe_only_incoming.checked,
      transcribe_model:             f.transcribe_model.value.trim(),
      transcribe_language:          f.transcribe_language.value.trim() || null,
      transcribe_prefix:            f.transcribe_prefix.value,
      max_message_chars:            parseInt(f.max_message_chars.value, 10) || 800,
      max_cached_messages_per_chat: parseInt(f.max_cached_messages_per_chat.value, 10) || 5000,
    },
    tools: {
      allowlist:             f.allowlist.value.trim() || null,
      denylist:              f.denylist.value.trim() || null,
      confirm_required_tools: f.confirm_required_tools.value.trim() || null,
    },
    logging: {
      level:             f.log_level.value,
      audit_log_enabled: f.audit_log_enabled.checked,
      audit_log_success: f.audit_log_success.checked,
      log_tool_success:  f.log_tool_success.checked,
    },
  };
}

async function saveConfig() {
  const data = await api("/admin/api/config", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectPayload()),
  });
  configDirty = false;
  await refreshAll();
  toast(
    data.restart_recommended
      ? "Salvo. Reinicie o serviço para aplicar mudanças de modelo ou ferramentas."
      : "Configurações salvas com sucesso.",
    data.restart_recommended ? "warn" : "",
  );
}

// ─── Setup actions ───────────────────────────────────────────────────────────

async function onSyncDeps() {
  await api("/admin/api/setup/sync", { method: "POST", body: "{}" });
  toast("Instalando dependências…");
  let retries = 0;
  await new Promise((resolve) => {
    const poll = setInterval(async () => {
      try {
        const j = await api("/admin/api/setup/sync");
        if (j.status !== "running") {
          clearInterval(poll);
          toast(
            j.status === "ok" ? "Dependências instaladas com sucesso." : "Falha ao instalar dependências.",
            j.status === "ok" ? "" : "err",
          );
          await refreshAll();
          resolve();
        }
      } catch {
        if (++retries > 15) { clearInterval(poll); resolve(); }
      }
    }, 2000);
  });
}

async function onGoogleSteps() {
  await api("/admin/api/setup/google-steps", { method: "POST", body: "{}" });
  toast("Passos do Google Cloud abertos no navegador.");
}

async function onImportCreds() {
  const r = await api("/admin/api/setup/credentials", { method: "POST", body: "{}" });
  toast(r.ok ? "Credenciais importadas com sucesso." : r.error || "Falha ao importar.", r.ok ? "" : "err");
  if (r.ok) refreshAll();
}

async function onSaveCreds(textarea) {
  const json = textarea.value.trim();
  if (!json) return toast("Cole o JSON OAuth antes de salvar.", "warn");
  const r = await api("/admin/api/setup/credentials", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ json }),
  });
  toast(r.ok ? "Credenciais salvas com sucesso." : r.error, r.ok ? "" : "err");
  if (r.ok) refreshAll();
}

// ─── Google actions ──────────────────────────────────────────────────────────

async function onGoogleLogin(loginIdEl, loginLabelEl) {
  const account_id = loginIdEl.value.trim() || "pessoal";
  const label = loginLabelEl.value.trim() || null;
  await api("/admin/api/google/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id, label }),
  });
  toast("Aguardando autorização no navegador…");
  let retries = 0;
  await new Promise((resolve) => {
    const poll = setInterval(async () => {
      try {
        const j = await api("/admin/api/google/login");
        if (refs.loginStatus) {
          refs.loginStatus.textContent =
            j.status === "running" ? "Aguardando conclusão da autorização no navegador…" : "";
        }
        if (j.status === "ok") {
          clearInterval(poll);
          toast(`Conta "${account_id}" conectada com sucesso.`);
          await refreshAll();
          resolve();
        } else if (j.status === "error") {
          clearInterval(poll);
          toast(j.error || "Falha na autorização.", "err");
          if (refs.loginStatus) refs.loginStatus.textContent = "";
          resolve();
        } else if (++retries > 80) { // ~2 min timeout
          clearInterval(poll);
          toast("Tempo esgotado. Tente novamente.", "warn");
          if (refs.loginStatus) refs.loginStatus.textContent = "";
          resolve();
        }
      } catch {
        if (++retries > 80) { clearInterval(poll); resolve(); }
      }
    }, 1500);
  });
}

async function setDefault(id) {
  await api("/admin/api/google/default", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id: id }),
  });
  toast("Conta padrão atualizada.");
  refreshAll();
}

async function logout(id) {
  if (!confirm(`Remover a conta "${id}"?\nEsta ação não pode ser desfeita.`)) return;
  await api("/admin/api/google/logout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ account_id: id }),
  });
  toast("Conta removida.");
  refreshAll();
}

// ─── WhatsApp actions ────────────────────────────────────────────────────────

function showQr(b64) {
  if (!refs.qrBox) return;
  if (!b64) {
    refs.qrBox.replaceChildren(hint("Gerando QR code…"));
    return;
  }
  refs.qrBox.replaceChildren(
    el("img", { alt: "QR Code WhatsApp", src: `data:image/png;base64,${b64}` }),
    hint("Escaneie com o WhatsApp: Dispositivos conectados → Adicionar dispositivo"),
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
      toast("WhatsApp pareado com sucesso!");
      refs.qrBox?.replaceChildren(el("p", { className: "card__hint" }, ["✓ Dispositivo conectado."]));
      refreshAll();
    }
  } catch { /* transient */ }
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
  toast("QR code sendo gerado — escaneie com o WhatsApp.");
}

function confirmFreshPair() {
  if (confirm("Isso vai apagar a sessão atual e iniciar um novo pareamento.\nContinuar?"))
    startPair(true);
}

async function stopPair() {
  if (pairTimer) { clearInterval(pairTimer); pairTimer = null; }
  await api("/admin/api/whatsapp/pair?action=stop");
  if (refs.qrBox) refs.qrBox.replaceChildren(hint("Pareamento interrompido."));
}

async function onWaDisconnect() {
  await api("/admin/api/whatsapp/session", { method: "POST", body: "{}" });
  toast("Conexão reiniciada.");
  refreshAll();
}

async function onWaRemove() {
  if (!confirm("Apagar todos os dados da sessão WhatsApp local?\nSerá necessário parear novamente.")) return;
  await api("/admin/api/whatsapp/session", { method: "DELETE", body: "{}" });
  toast("Sessão removida.");
  refreshAll();
}

// ─── Service actions ─────────────────────────────────────────────────────────

async function svcAction(action) {
  try {
    const data = await api("/admin/api/service", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    if (!data.ok) { toast(data.error || `Falha: ${action}`, "err"); return; }
    const MSGS = {
      install: "Serviço instalado e iniciado.",
      start:   "Serviço iniciado.",
      stop:    "Serviço parado.",
      uninstall: "Serviço desinstalado.",
    };
    toast(MSGS[action] || `Ação executada: ${action}`);
    await refreshAll();
  } catch (e) {
    toast(e.message || "Erro ao gerenciar serviço.", "err");
  }
}

function confirmUninstallSvc() {
  if (confirm("Desinstalar o LaunchAgent?\nO servidor não iniciará automaticamente no próximo login."))
    svcAction("uninstall");
}

// ─── MCP / Hermes actions ────────────────────────────────────────────────────

async function onHermesDoctor() {
  if (!refs.mcpChecks) return;
  refs.mcpChecks.replaceChildren(hint("Rodando diagnóstico…"));
  try {
    const d = await api("/admin/api/hermes/doctor");
    refs.mcpChecks.replaceChildren(Checklist(d.checks));
  } catch {
    refs.mcpChecks.replaceChildren(hint("Falha ao rodar diagnóstico."));
  }
}

async function onHermesSetup() {
  const r = await api("/admin/api/hermes/setup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: "sse", yes: true }),
  });
  if (r.ok) {
    toast("Integração MCP configurada com sucesso.");
    if (r.restart_hints?.length)
      setTimeout(() => toast("Reinicie o Claude Desktop (⌘Q) ou use /reload-mcp no Hermes.", "warn"), 4100);
  } else {
    toast(r.error || "Falha ao configurar MCP.", "err");
  }
}

async function onHermesInstall() {
  await api("/admin/api/hermes/install", { method: "POST", body: "{}" });
  toast("Link de instalação do Hermes aberto no navegador.");
}

// ─── Log actions ─────────────────────────────────────────────────────────────

async function loadLog(name) {
  refs.currentLog = name;
  const data = await api(`/admin/api/logs?file=${encodeURIComponent(name)}&lines=300`);
  refs.logView.textContent = data.text || "(arquivo vazio)";
  refs.logView.scrollTop = refs.logView.scrollHeight;
}

async function loadFailures() {
  refs.currentLog = null;
  const data = await api("/admin/api/failures?limit=50");
  refs.logView.textContent =
    (data.failures || [])
      .map((r) => `${r.ts}  ${r.tool}  ${r.error || "?"}${r.blocked ? "  [bloqueado]" : ""}`)
      .join("\n") || "Nenhuma falha registrada.";
  refs.logView.scrollTop = refs.logView.scrollHeight;
}
