import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBanner } from "@/components/ui/alert";
import { useApp } from "@/context/AppContext";
import type { PersistenceState } from "@/types";

const LABELS: Record<string, string> = {
  installed: "Instalado",
  running: "Em execução",
  pid: "PID",
  status: "Status",
  plist_path: "Arquivo plist",
  host: "Host",
  port: "Porta",
  label: "Label",
};

export function ServicoView() {
  const { state, svcAction, confirmUninstallSvc } = useApp();
  const [busy, setBusy] = useState<string | null>(null);

  if (!state) return null;
  const svc = state.mac_service || {};
  const deploy = state.deployment || {};
  const persist = (state.persistence || {}) as Partial<PersistenceState>;

  async function run(action: string) {
    setBusy(action);
    try {
      await svcAction(action);
    } finally {
      setBusy(null);
    }
  }

  if (deploy.docker) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Serviço (Docker / Coolify)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {persist.status && persist.status !== "ok" ? (
            <StatusBanner tone={persist.status === "error" ? "err" : "warn"}>
              {persist.message}
              {persist.hint ? (
                <p className="mt-1 text-xs opacity-90">{persist.hint}</p>
              ) : null}
            </StatusBanner>
          ) : null}
          <p className="text-sm text-muted">
            Produção roda no container. Não use LaunchAgent local no Mac — dois workers
            neonize disputam worker.lock e quebram WhatsApp.
          </p>
          <p className="text-sm text-muted">
            Persistência: monte volume Coolify em /app/data (WhatsApp + tokens Google). Ver
            docs/COOLIFY.md no repositório.
          </p>
          <pre className="overflow-x-auto rounded-md border border-border bg-background p-4 font-mono text-xs">
            docker compose up -d   # ou redeploy no Coolify
          </pre>
        </CardContent>
      </Card>
    );
  }

  if (!svc.available) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Serviço em segundo plano</CardTitle>
          <CardDescription>
            Inicie o servidor manualmente e mantenha o terminal aberto. Para execução
            contínua, use systemd ou Docker.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-md border border-border bg-background p-4 font-mono text-xs">
            uv run integrator serve-http
          </pre>
          <p className="mt-3 text-xs text-muted">
            O LaunchAgent automático está disponível apenas no macOS.
          </p>
        </CardContent>
      </Card>
    );
  }

  const entries = Object.entries(svc).filter(([k]) => k !== "available");

  return (
    <Card>
      <CardHeader>
        <CardTitle>Serviço macOS (LaunchAgent)</CardTitle>
        <CardDescription>
          O LaunchAgent inicia o servidor automaticamente ao fazer login no macOS.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <dl className="grid gap-3 sm:grid-cols-2">
          {entries.map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs uppercase tracking-wide text-muted">
                {LABELS[k] || k}
              </dt>
              <dd className="mt-1 font-mono text-sm">{String(v ?? "—")}</dd>
            </div>
          ))}
        </dl>
        <div className="flex flex-wrap gap-2">
          <Button
            disabled={!!(svc.installed && svc.running)}
            loading={busy === "install"}
            onClick={() => run("install")}
          >
            Instalar e iniciar
          </Button>
          <Button
            variant="secondary"
            disabled={!!svc.running}
            loading={busy === "start"}
            onClick={() => run("start")}
          >
            Iniciar
          </Button>
          <Button
            variant="secondary"
            disabled={!svc.running}
            loading={busy === "stop"}
            onClick={() => run("stop")}
          >
            Parar
          </Button>
          <Button variant="destructive" onClick={confirmUninstallSvc}>
            Desinstalar
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
