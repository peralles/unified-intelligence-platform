import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useApp } from "@/context/AppContext";
import { Play, Square, RotateCcw } from "lucide-react";

export function WhatsAppView() {
  const {
    state,
    qrBase64,
    qrHint,
    startPair,
    stopPair,
    confirmFreshPair,
    onWaDisconnect,
    onWaRemove,
  } = useApp();
  const [busy, setBusy] = useState<string | null>(null);

  if (!state) return null;
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const isConnected = !!st.logged_in && !wa.error;

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Status da conexão</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted">Conexão</dt>
              <dd className="mt-1 font-medium">
                {isConnected
                  ? "Conectado"
                  : wa.error
                    ? `Erro: ${wa.error}`
                    : st.state || "Desconectado"}
              </dd>
            </div>
            {st.push_name ? (
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted">Dispositivo</dt>
                <dd className="mt-1 font-medium">{st.push_name}</dd>
              </div>
            ) : null}
            {isConnected && state.effective?.whatsapp ? (
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted">
                  Transcrição automática
                </dt>
                <dd className="mt-1 font-medium">
                  {state.effective.whatsapp.auto_transcribe ? "Ativa" : "Desativada"}
                </dd>
              </div>
            ) : null}
          </dl>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              loading={busy === "disc"}
              onClick={() => run("disc", onWaDisconnect)}
            >
              <RotateCcw className="h-4 w-4" />
              Reiniciar conexão
            </Button>
            <Button
              variant="destructive"
              loading={busy === "rm"}
              onClick={() => run("rm", onWaRemove)}
            >
              Apagar sessão local
            </Button>
          </div>
          <p className="text-xs text-muted">
            Reiniciar reconecta sem apagar dados. Apagar sessão remove tudo e exige novo
            pareamento.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Parear dispositivo WhatsApp</CardTitle>
          <CardDescription>
            WhatsApp no celular → Menu → Dispositivos conectados → Adicionar dispositivo →
            escaneie o QR.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background/50 p-6">
            {qrBase64 ? (
              <img
                alt="QR Code WhatsApp"
                src={`data:image/png;base64,${qrBase64}`}
                className="max-h-56 rounded-md"
              />
            ) : (
              <p className="text-center text-sm text-muted">{qrHint}</p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              loading={busy === "pair"}
              onClick={() => run("pair", () => startPair(false))}
            >
              <Play className="h-4 w-4" />
              {isConnected ? "Reparear dispositivo" : "Iniciar pareamento (QR)"}
            </Button>
            <Button variant="secondary" onClick={confirmFreshPair}>
              Parear do zero (nova sessão)
            </Button>
            <Button
              variant="secondary"
              loading={busy === "stop"}
              onClick={() => run("stop", stopPair)}
            >
              <Square className="h-4 w-4" />
              Parar
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
