import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { StatusBanner } from "@/components/ui/alert";
import { useApp } from "@/context/AppContext";
import type { PersistenceState } from "@/types";
import { CheckCircle2 } from "lucide-react";

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
  const { state, setActiveView } = useApp();
  if (!state) return null;

  const setup = state.setup || {};
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const persist = (state.persistence || {}) as Partial<PersistenceState>;
  const tx = wa.transcription;

  const googleOk = !!setup.configured;
  const waOk = !!st.logged_in && !wa.error;
  const allOk = googleOk && waOk && persist.status !== "warn" && persist.status !== "error";

  const defaultEmail =
    state.accounts?.accounts?.find((a) => a.is_default)?.email || "configurada";

  const pending: string[] = [];
  if (!setup.credentials_ready) pending.push("credencial OAuth Google");
  if (!googleOk) pending.push("conta Google conectada");
  if (!waOk) pending.push("WhatsApp pareado");

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
            Integrador operacional — Google e WhatsApp prontos.
          </span>
        ) : pending.length ? (
          `Pendente: ${pending.join(", ")}.`
        ) : (
          "Complete a configuração nos menus Google e WhatsApp."
        )}
      </StatusBanner>

      <div className="grid gap-4 md:grid-cols-2">
        <StatusCard
          title="Google"
          status={googleOk ? "Conectado" : "Não configurado"}
          tone={googleOk ? "ok" : "warn"}
          detail={
            googleOk
              ? `Conta padrão: ${defaultEmail}`
              : "Configure OAuth e conecte uma conta para Gmail e Agenda."
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
              ? `Transcrição: ${state.effective?.whatsapp?.auto_transcribe ? "ativa" : "desativada"}${
                  tx?.model ? ` · modelo ${tx.model}` : ""
                }${tx?.transcriber_ready === false && state.effective?.whatsapp?.auto_transcribe ? " · worker carregando modelo" : ""}`
              : wa.error
                ? String(wa.error)
                : "Pareie o WhatsApp para mensagens e transcrição de áudio."
          }
          actionLabel={waOk ? "Gerenciar" : "Parear"}
          onAction={() => setActiveView("whatsapp")}
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm font-semibold">Agentes de IA (Hermes / Claude)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted">
          <p>
            Configuração MCP fica no seu computador, não neste console remoto. Veja o menu{" "}
            <button
              type="button"
              className="text-primary underline-offset-2 hover:underline"
              onClick={() => setActiveView("guia")}
            >
              Guia
            </button>{" "}
            e rode <code className="rounded bg-secondary px-1 font-mono text-xs">./scripts/setup-local-agents.sh</code>{" "}
            na máquina onde rodam Hermes ou Claude Desktop.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
