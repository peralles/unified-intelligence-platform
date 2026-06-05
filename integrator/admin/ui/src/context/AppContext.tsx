import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { api, registerToast } from "@/api/client";
import type { AppState, Tone, ViewId } from "@/types";

interface ToastState {
  message: string;
  tone: Tone;
}

interface AppContextValue {
  state: AppState | null;
  activeView: ViewId;
  lastUpdated: string;
  loading: boolean;
  toast: ToastState | null;
  setActiveView: (id: ViewId) => void;
  refreshAll: () => Promise<void>;
  navBadgeTone: (id: ViewId) => Tone;
  onGoogleSteps: () => Promise<void>;
  onImportCreds: () => Promise<void>;
  onSaveCreds: (json: string) => Promise<boolean>;
  onGoogleLogin: (accountId: string, label: string) => void;
  setDefaultAccount: (id: string) => Promise<void>;
  logoutAccount: (id: string) => Promise<void>;
  qrBase64: string | null;
  qrHint: string;
  pairActive: boolean;
  startPair: (fresh?: boolean) => Promise<void>;
  stopPair: () => Promise<void>;
  confirmFreshPair: () => void;
  onWaDisconnect: () => Promise<void>;
  onWaRemove: () => Promise<void>;
  saveConfig: (payload: Record<string, unknown>) => Promise<void>;
  logText: string;
  currentLog: string | null;
  loadLog: (name: string) => Promise<void>;
  loadFailures: () => Promise<void>;
  toolsLoaded: boolean;
  loadTools: () => Promise<{ name: string; description?: string }[] | null>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AppState | null>(null);
  const [activeView, setActiveView] = useState<ViewId>("painel");
  const [lastUpdated, setLastUpdated] = useState("");
  const [loading, setLoading] = useState(false);
  const [toastState, setToastState] = useState<ToastState | null>(null);
  const [toolsLoaded, setToolsLoaded] = useState(false);
  const [logText, setLogText] = useState("Clique em um botão abaixo para carregar o log.");
  const [currentLog, setCurrentLog] = useState<string | null>(null);
  const [qrBase64, setQrBase64] = useState<string | null>(null);
  const [qrHint, setQrHint] = useState(
    "O QR code aparecerá aqui quando o pareamento for iniciado.",
  );
  const [pairActive, setPairActive] = useState(false);

  const pairTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const pairPollFailures = useRef(0);

  const showToast = useCallback((message: string, tone: Tone = "", dur = 3200) => {
    setToastState({ message, tone });
    window.setTimeout(() => setToastState(null), dur);
  }, []);

  useEffect(() => {
    registerToast(showToast);
  }, [showToast]);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api<AppState>("/admin/api/state");
      setState(data);
      setLastUpdated(`Atualizado às ${new Date().toLocaleTimeString("pt-BR")}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauth = params.get("oauth");
    if (oauth) {
      const message = params.get("message");
      if (oauth === "ok") {
        showToast("Conta Google conectada com sucesso.");
        setActiveView("google");
      } else {
        const detail = message
          ? decodeURIComponent(message.replace(/\+/g, " "))
          : "Falha na autorização Google.";
        showToast(detail, "err");
        setActiveView("google");
      }
      window.history.replaceState({}, "", window.location.pathname);
    }
    refreshAll().catch((e: Error) => showToast(e.message, "err"));
    const id = window.setInterval(() => {
      refreshAll().catch(() => {});
    }, 30_000);
    return () => window.clearInterval(id);
  }, [refreshAll, showToast]);

  const navBadgeTone = useCallback(
    (id: ViewId): Tone => {
      if (!state) return "";
      const setup = state.setup || {};
      const wa = state.whatsapp_live || {};
      const st = wa.live || wa.status || {};
      if (id === "google") {
        if (!setup.credentials_ready) return "warn";
        const accs = state.accounts?.accounts || [];
        if (!accs.some((a) => a.has_token)) return "warn";
        return "ok";
      }
      if (id === "whatsapp") return wa.error ? "err" : st.logged_in ? "ok" : "warn";
      return "";
    },
    [state],
  );

  const pollPair = useCallback(async () => {
    try {
      const r = await api<{ data?: Record<string, unknown> }>(
        "/admin/api/whatsapp/pair?action=poll",
      );
      const d = r.data || {};
      pairPollFailures.current = 0;
      if (d.error && !d.qr_png_base64 && !d.logged_in) {
        setQrHint(`Erro WhatsApp: ${String(d.error)}`);
        setQrBase64(null);
      }
      if (d.qr_png_base64) {
        setQrBase64(String(d.qr_png_base64));
        setQrHint("Escaneie com o WhatsApp: Dispositivos conectados → Adicionar dispositivo");
      } else if (d.state === "qr") {
        setQrBase64(null);
        setQrHint("Gerando QR code…");
      }
      if (d.logged_in) {
        if (pairTimer.current) clearInterval(pairTimer.current);
        pairTimer.current = null;
        setPairActive(false);
        showToast("WhatsApp pareado com sucesso!");
        setQrBase64(null);
        setQrHint("Dispositivo conectado.");
        await refreshAll();
      }
    } catch (err) {
      pairPollFailures.current += 1;
      if (pairPollFailures.current >= 3) {
        if (pairTimer.current) clearInterval(pairTimer.current);
        pairTimer.current = null;
        setPairActive(false);
        const msg = err instanceof Error ? err.message : "Falha ao gerar QR code.";
        setQrHint(msg);
        showToast(msg, "err");
      }
    }
  }, [refreshAll, showToast]);

  const startPair = useCallback(
    async (fresh = false) => {
      if (pairTimer.current) clearInterval(pairTimer.current);
      pairPollFailures.current = 0;
      setQrBase64(null);
      setQrHint("Gerando QR code…");
      try {
        await api("/admin/api/whatsapp/pair?action=start", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fresh: !!fresh }),
        });
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Não foi possível iniciar pareamento.";
        setQrHint(msg);
        showToast(msg, "err");
        return;
      }
      setPairActive(true);
      pairTimer.current = setInterval(() => {
        void pollPair();
      }, 1500);
      void pollPair();
      showToast("QR code sendo gerado — escaneie com o WhatsApp.");
    },
    [pollPair, showToast],
  );

  const stopPair = useCallback(async () => {
    if (pairTimer.current) {
      clearInterval(pairTimer.current);
      pairTimer.current = null;
    }
    setPairActive(false);
    await api("/admin/api/whatsapp/pair?action=stop");
    setQrBase64(null);
    setQrHint("Pareamento interrompido.");
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      state,
      activeView,
      lastUpdated,
      loading,
      toast: toastState,
      setActiveView,
      refreshAll,
      navBadgeTone,
      onGoogleSteps: async () => {
        await api("/admin/api/setup/google-steps", { method: "POST", body: "{}" });
        showToast("Passos do Google Cloud abertos no navegador.");
      },
      onImportCreds: async () => {
        const r = await api<{ ok?: boolean; error?: string }>(
          "/admin/api/setup/credentials",
          { method: "POST", body: "{}" },
        );
        showToast(
          r.ok ? "Credenciais importadas com sucesso." : r.error || "Falha ao importar.",
          r.ok ? "" : "err",
        );
        if (r.ok) await refreshAll();
      },
      onSaveCreds: async (json: string) => {
        if (!json.trim()) {
          showToast("Cole o JSON OAuth antes de salvar.", "warn");
          return false;
        }
        const r = await api<{ ok?: boolean; error?: string }>(
          "/admin/api/setup/credentials",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ json }),
          },
        );
        showToast(r.ok ? "Credenciais salvas com sucesso." : r.error || "Erro", r.ok ? "" : "err");
        if (r.ok) await refreshAll();
        return !!r.ok;
      },
      onGoogleLogin: (accountId, label) => {
        const id = accountId.trim() || "pessoal";
        const params = new URLSearchParams({ account_id: id });
        if (label.trim()) params.set("label", label.trim());
        window.location.href = `/admin/oauth/google/start?${params.toString()}`;
      },
      setDefaultAccount: async (id) => {
        await api("/admin/api/google/default", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account_id: id }),
        });
        showToast("Conta padrão atualizada.");
        await refreshAll();
      },
      logoutAccount: async (id) => {
        if (!confirm(`Remover a conta "${id}"?\nEsta ação não pode ser desfeita.`)) return;
        await api("/admin/api/google/logout", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account_id: id }),
        });
        showToast("Conta removida.");
        await refreshAll();
      },
      qrBase64,
      qrHint,
      pairActive,
      startPair,
      stopPair,
      confirmFreshPair: () => {
        if (
          confirm(
            "Isso vai apagar a sessão atual e iniciar um novo pareamento.\nContinuar?",
          )
        ) {
          void startPair(true);
        }
      },
      onWaDisconnect: async () => {
        await api("/admin/api/whatsapp/session", { method: "POST", body: "{}" });
        showToast("Conexão reiniciada.");
        await refreshAll();
      },
      onWaRemove: async () => {
        if (
          !confirm(
            "Apagar todos os dados da sessão WhatsApp local?\nSerá necessário parear novamente.",
          )
        )
          return;
        await api("/admin/api/whatsapp/session", { method: "DELETE", body: "{}" });
        showToast("Sessão removida.");
        await refreshAll();
      },
      saveConfig: async (payload) => {
        const data = await api<{ restart_recommended?: boolean }>("/admin/api/config", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        await refreshAll();
        showToast(
          data.restart_recommended
            ? "Salvo. Reinicie o container para aplicar mudanças de modelo ou ferramentas."
            : "Configurações salvas com sucesso.",
          data.restart_recommended ? "warn" : "",
        );
      },
      logText,
      currentLog,
      loadLog: async (name) => {
        setCurrentLog(name);
        const data = await api<{ text?: string }>(
          `/admin/api/logs?file=${encodeURIComponent(name)}&lines=300`,
        );
        setLogText(data.text || "(arquivo vazio)");
      },
      loadFailures: async () => {
        setCurrentLog(null);
        const data = await api<{ failures?: { ts: string; tool: string; error?: string; blocked?: boolean }[] }>(
          "/admin/api/failures?limit=50",
        );
        setLogText(
          (data.failures || [])
            .map(
              (r) =>
                `${r.ts}  ${r.tool}  ${r.error || "?"}${r.blocked ? "  [bloqueado]" : ""}`,
            )
            .join("\n") || "Nenhuma falha registrada.",
        );
      },
      toolsLoaded,
      loadTools: async () => {
        setToolsLoaded(true);
        try {
          const data = await api<{ tools?: { name: string; description?: string }[] }>(
            "/admin/api/tools",
          );
          return data.tools || [];
        } catch {
          showToast("Erro ao carregar ferramentas.", "err");
          return null;
        }
      },
    }),
    [
      state,
      activeView,
      lastUpdated,
      loading,
      toastState,
      refreshAll,
      navBadgeTone,
      qrBase64,
      qrHint,
      pairActive,
      startPair,
      stopPair,
      logText,
      currentLog,
      toolsLoaded,
      showToast,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
