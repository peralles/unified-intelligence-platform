import { cn } from "@/lib/utils";
import { NAV } from "@/config/nav";
import { useApp } from "@/context/AppContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RefreshCw, Zap } from "lucide-react";

export function Sidebar() {
  const { activeView, setActiveView, navBadgeTone, refreshAll, loading } = useApp();

  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-card/40 backdrop-blur-sm">
      <div className="flex items-center gap-3 border-b border-border px-5 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Zap className="h-5 w-5" strokeWidth={2.2} />
        </div>
        <div>
          <h1 className="text-base font-semibold tracking-tight">Integrator</h1>
          <p className="text-xs text-muted">Console local</p>
        </div>
      </div>

      <nav className="flex-1 space-y-0.5 p-3">
        {NAV.map((item) => {
          const Icon = item.icon;
          const tone = navBadgeTone(item.id);
          const active = activeView === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveView(item.id)}
              className={cn(
                "flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm font-medium transition-colors",
                active
                  ? "bg-primary/10 text-primary"
                  : "text-muted hover:bg-secondary/60 hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
              <span className="flex-1">{item.label}</span>
              {tone ? (
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    tone === "ok" && "bg-success",
                    tone === "warn" && "bg-warning",
                    tone === "err" && "bg-destructive",
                  )}
                />
              ) : null}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-border p-3">
        <Button
          variant="secondary"
          className="w-full"
          loading={loading}
          onClick={() => refreshAll().catch(() => {})}
        >
          <RefreshCw className="h-4 w-4" />
          Atualizar
        </Button>
      </div>
    </aside>
  );
}

export function TopBar() {
  const { state, lastUpdated } = useApp();
  const setup = state?.setup || {};
  const wa = state?.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const fails = setup.critical_failures ?? 0;

  return (
    <header className="flex flex-wrap items-start justify-between gap-4 border-b border-border px-6 py-5">
      <div>
        <h2 className="text-lg font-semibold tracking-tight">Console de Administração</h2>
        {lastUpdated ? (
          <p className="mt-0.5 text-xs text-muted">{lastUpdated}</p>
        ) : null}
      </div>
      <div className="flex flex-wrap gap-2">
        <Badge tone={setup.configured ? "ok" : "warn"}>
          Google {setup.configured ? "OK" : "pendente"}
        </Badge>
        <Badge tone={wa.error ? "err" : st.logged_in ? "ok" : "warn"}>
          WhatsApp {wa.error ? "erro" : st.logged_in ? "OK" : st.state || "—"}
        </Badge>
        {st.logged_in && state?.effective?.whatsapp?.auto_transcribe ? (
          <Badge tone="ok">Transcrição</Badge>
        ) : null}
        <Badge tone={fails ? "warn" : "ok"}>
          MCP {fails ? `${fails} problema(s)` : "OK"}
        </Badge>
      </div>
    </header>
  );
}

export function ToastHost() {
  const { toast } = useApp();
  if (!toast) return null;
  return (
    <div
      className={cn(
        "fixed bottom-5 right-5 z-50 max-w-sm rounded-lg border px-4 py-3 text-sm shadow-lg backdrop-blur",
        toast.tone === "err" && "border-destructive/40 bg-destructive/15 text-destructive",
        toast.tone === "warn" && "border-warning/40 bg-warning/15 text-warning",
        !toast.tone && "border-border bg-card text-foreground",
      )}
      role="status"
    >
      {toast.message}
    </div>
  );
}
