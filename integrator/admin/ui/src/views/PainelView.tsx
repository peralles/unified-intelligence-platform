import { Badge } from "@/components/ui/badge";
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
import { CheckCircle2, Copy } from "lucide-react";

function StatusCard({
  title,
  status,
  tone,
  detail,
  actionLabel,
  onAction,
}: {
  title: string;
  status: string;
  tone: "ok" | "warn" | "err";
  detail: string;
  actionLabel: string;
  onAction: () => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex-row items-start justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-semibold">{title}</CardTitle>
        <Badge tone={tone}>{status}</Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted">{detail}</p>
        <Button variant="secondary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      </CardContent>
    </Card>
  );
}

export function PainelView() {
  const { state, setActiveView, onSyncDeps } = useApp();
  if (!state) return null;

  const setup = state.setup || {};
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const fails = setup.critical_failures ?? 0;
  const persist = (state.persistence || {}) as Partial<PersistenceState>;

  const googleOk = !!setup.configured;
  const waOk = !!st.logged_in && !wa.error;
  const mcpOk = fails === 0;
  const allOk =
    googleOk && waOk && mcpOk && persist.status !== "warn" && persist.status !== "error";

  const defaultEmail =
    state.accounts?.accounts?.find((a) => a.is_default)?.email || "configurada";

  const wizardSteps: [string, boolean][] = [
    ["Dependências instaladas", !!setup.deps_ok],
    ["Credenciais OAuth configuradas", !!setup.credentials_ready],
    ["Conta Google conectada", !!setup.configured],
    ["MCP / Hermes configurado", mcpOk],
  ];
  const wizardDone = wizardSteps.every(([, d]) => d);
  const svcUrl = state.service?.url_admin || "";

  return (
    <div className="space-y-5">
      {(persist.status === "warn" || persist.status === "error") && (
        <StatusBanner tone={persist.status === "error" ? "err" : "warn"}>
          <strong>Persistência de dados:</strong> {persist.message}
          {persist.hint ? <p className="mt-1 text-xs opacity-90">{persist.hint}</p> : null}
          {persist.volume_id ? (
            <p className="mt-1 font-mono text-xs opacity-80">Volume ID: {persist.volume_id}</p>
          ) : null}
        </StatusBanner>
      )}

      <StatusBanner tone={allOk ? "ok" : "warn"}>
        {allOk ? (
          <span className="inline-flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            Tudo funcionando — integrador pronto para uso.
          </span>
        ) : (
          setup.next_step
            ? `Próximo passo: ${setup.next_step}`
            : "Complete a configuração abaixo."
        )}
      </StatusBanner>

      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard
          title="Google"
          status={googleOk ? "Conectado" : "Não configurado"}
          tone={googleOk ? "ok" : "warn"}
          detail={
            googleOk
              ? `Conta: ${defaultEmail}`
              : "Configure uma conta Google para usar Gmail e Agenda."
          }
          actionLabel={googleOk ? "Gerenciar" : "Configurar"}
          onAction={() => setActiveView("google")}
        />
        <StatusCard
          title="WhatsApp"
          status={waOk ? "Conectado" : wa.error ? "Erro" : String(st.state || "Desconectado")}
          tone={waOk ? "ok" : wa.error ? "err" : "warn"}
          detail={
            waOk
              ? `Transcrição automática: ${state.effective?.whatsapp?.auto_transcribe ? "ativa" : "desativada"}`
              : wa.error
                ? String(wa.error)
                : "Pareie o WhatsApp para usar o agente."
          }
          actionLabel={waOk ? "Gerenciar" : "Parear"}
          onAction={() => setActiveView("whatsapp")}
        />
        <StatusCard
          title="MCP / Hermes"
          status={mcpOk ? "Configurado" : `${fails} problema(s)`}
          tone={mcpOk ? "ok" : "warn"}
          detail={
            mcpOk
              ? "Integração com agentes ativa."
              : "Configure para que agentes possam usar as ferramentas."
          }
          actionLabel="Ver MCP"
          onAction={() => setActiveView("mcp")}
        />
      </div>

      {svcUrl ? (
        <Card>
          <CardHeader>
            <CardTitle>Endereço do console</CardTitle>
            <CardDescription>
              Acesse este endereço no navegador para abrir o console de administração.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap items-center gap-3">
              <code className="flex-1 rounded-md border border-border bg-background px-3 py-2 font-mono text-xs">
                {svcUrl}
              </code>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  void navigator.clipboard?.writeText(svcUrl);
                }}
              >
                <Copy className="h-4 w-4" />
                Copiar
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {!wizardDone ? (
        <Card>
          <CardHeader>
            <CardTitle>Passos de configuração inicial</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ol className="space-y-2">
              {wizardSteps.map(([label, done]) => (
                <li
                  key={label}
                  className="flex items-center gap-2 text-sm"
                >
                  <span
                    className={
                      done ? "text-success" : "text-muted-foreground"
                    }
                  >
                    {done ? "✓" : "○"}
                  </span>
                  {label}
                </li>
              ))}
            </ol>
            <div className="flex flex-wrap gap-2">
              <Button disabled={setup.deps_ok} onClick={() => onSyncDeps()}>
                Instalar dependências
              </Button>
              <Button variant="secondary" onClick={() => setActiveView("google")}>
                Configurar Google
              </Button>
              <Button variant="secondary" onClick={() => setActiveView("mcp")}>
                Configurar MCP
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
