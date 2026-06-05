import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox, Input, Label, Select, Textarea } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import {
  whatsappConfigPayload,
  whatsappFormFromState,
  type WhatsAppConfigForm,
} from "@/lib/configForm";
import { Play, RotateCcw, Save, Square } from "lucide-react";

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
    saveConfig,
  } = useApp();
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState<WhatsAppConfigForm | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (state && !dirty) setForm(whatsappFormFromState(state));
  }, [state, dirty]);

  if (!state || !form) return null;
  const wa = state.whatsapp_live || {};
  const st = wa.live || wa.status || {};
  const tx = wa.transcription;
  const isConnected = !!st.logged_in && !wa.error;

  function patch(p: Partial<WhatsAppConfigForm>) {
    setForm((f) => (f ? { ...f, ...p } : f));
    setDirty(true);
  }

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  }

  async function onSave() {
    if (!form) return;
    setSaving(true);
    try {
      await saveConfig(whatsappConfigPayload(form));
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Status da conexão</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
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
            <div>
              <dt className="text-xs uppercase tracking-wide text-muted">Transcriber</dt>
              <dd className="mt-1 flex items-center gap-2">
                {form.auto_transcribe ? (
                  <>
                    <Badge tone={tx?.transcriber_ready === false ? "warn" : "ok"}>
                      {tx?.transcriber_ready === false ? "carregando" : "pronto"}
                    </Badge>
                    {tx?.model ? (
                      <span className="text-sm text-muted">{tx.model}</span>
                    ) : null}
                  </>
                ) : (
                  <span className="text-sm text-muted">Desativada</span>
                )}
              </dd>
            </div>
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
            Reiniciar reconecta sem apagar dados. Apagar sessão remove tudo e exige novo QR.
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

      <Card>
        <CardHeader>
          <CardTitle>Transcrição automática de áudio</CardTitle>
          <CardDescription>
            faster-whisper no worker (CPU). Primeiro áudio pode demorar enquanto o modelo
            carrega. Números ignorados aplicam em tempo real.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.auto_transcribe}
                onChange={(e) => patch({ auto_transcribe: e.target.checked })}
              />
              Ativar transcrição automática
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.transcribe_private_only}
                onChange={(e) => patch({ transcribe_private_only: e.target.checked })}
              />
              Apenas chats privados (não grupos)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.transcribe_only_incoming}
                onChange={(e) => patch({ transcribe_only_incoming: e.target.checked })}
              />
              Apenas mensagens recebidas
            </label>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Modelo Whisper</Label>
              <Select
                value={form.transcribe_model}
                onChange={(e) => patch({ transcribe_model: e.target.value })}
              >
                {["tiny", "base", "small", "large-v3-turbo", "large-v3"].map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Idioma (pt, en, vazio=auto)</Label>
              <Input
                value={form.transcribe_language}
                onChange={(e) => patch({ transcribe_language: e.target.value })}
                placeholder="pt"
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Prefixo da transcrição</Label>
              <Input
                value={form.transcribe_prefix}
                onChange={(e) => patch({ transcribe_prefix: e.target.value })}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>Números ignorados (um por linha, só dígitos)</Label>
            <Textarea
              rows={4}
              value={form.ignore_numbers_text}
              onChange={(e) => patch({ ignore_numbers_text: e.target.value })}
              placeholder="5511999999999"
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.persist_env}
                onChange={(e) => patch({ persist_env: e.target.checked })}
              />
              Salvar no .env quando possível
            </label>
            <div className="flex gap-2">
              {dirty ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setDirty(false);
                    setForm(whatsappFormFromState(state));
                  }}
                >
                  Descartar
                </Button>
              ) : null}
              <Button loading={saving} onClick={() => void onSave()}>
                <Save className="h-4 w-4" />
                Salvar transcrição
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
