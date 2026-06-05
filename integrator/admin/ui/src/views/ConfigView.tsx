import { useEffect, useState } from "react";
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
import { Save } from "lucide-react";

interface ConfigForm {
  auto_transcribe: boolean;
  transcribe_private_only: boolean;
  transcribe_only_incoming: boolean;
  transcribe_model: string;
  transcribe_language: string;
  transcribe_prefix: string;
  max_message_chars: string;
  max_cached_per_chat: string;
  allowlist: string;
  denylist: string;
  confirm_required_tools: string;
  log_level: string;
  audit_log_enabled: boolean;
  audit_log_success: boolean;
  log_tool_success: boolean;
  persist_env: boolean;
  ignore_numbers_text: string;
}

function fromState(state: NonNullable<ReturnType<typeof useApp>["state"]>): ConfigForm {
  const w = state.effective?.whatsapp || {};
  const t = state.effective?.tools || {};
  const l = state.effective?.logging || {};
  return {
    auto_transcribe: !!w.auto_transcribe,
    transcribe_private_only: !!w.transcribe_private_only,
    transcribe_only_incoming: !!w.transcribe_only_incoming,
    transcribe_model: String(w.transcribe_model || ""),
    transcribe_language: String(w.transcribe_language || ""),
    transcribe_prefix: String(w.transcribe_prefix || ""),
    max_message_chars: String(w.max_message_chars || 800),
    max_cached_per_chat: String(w.max_cached_messages_per_chat || 5000),
    allowlist: String(t.allowlist || ""),
    denylist: String(t.denylist || ""),
    confirm_required_tools: String(t.confirm_required_tools || ""),
    log_level: String(l.level || "INFO").toUpperCase(),
    audit_log_enabled: !!l.audit_log_enabled,
    audit_log_success: !!l.audit_log_success,
    log_tool_success: !!l.log_tool_success,
    persist_env: true,
    ignore_numbers_text: state.ignore_numbers_text || "",
  };
}

export function ConfigView() {
  const { state, configDirty, setConfigDirty, saveConfig } = useApp();
  const [form, setForm] = useState<ConfigForm | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (state && !configDirty) {
      setForm(fromState(state));
    }
  }, [state, configDirty]);

  if (!state || !form) return null;

  function patch(p: Partial<ConfigForm>) {
    setForm((f) => (f ? { ...f, ...p } : f));
    setConfigDirty(true);
  }

  async function onSave() {
    if (!form) return;
    setSaving(true);
    try {
      await saveConfig({
        persist_env: form.persist_env,
        ignore_numbers_text: form.ignore_numbers_text,
        whatsapp: {
          auto_transcribe: form.auto_transcribe,
          transcribe_private_only: form.transcribe_private_only,
          transcribe_only_incoming: form.transcribe_only_incoming,
          transcribe_model: form.transcribe_model.trim(),
          transcribe_language: form.transcribe_language.trim() || null,
          transcribe_prefix: form.transcribe_prefix,
          max_message_chars: parseInt(form.max_message_chars, 10) || 800,
          max_cached_messages_per_chat: parseInt(form.max_cached_per_chat, 10) || 5000,
        },
        tools: {
          allowlist: form.allowlist.trim() || null,
          denylist: form.denylist.trim() || null,
          confirm_required_tools: form.confirm_required_tools.trim() || null,
        },
        logging: {
          level: form.log_level,
          audit_log_enabled: form.audit_log_enabled,
          audit_log_success: form.audit_log_success,
          log_tool_success: form.log_tool_success,
        },
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Transcrição automática de áudio (WhatsApp)</CardTitle>
          <CardDescription>
            Transcreve mensagens de voz usando Whisper (mlx-whisper). Requer Apple Silicon.
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
              <Input
                value={form.transcribe_model}
                onChange={(e) => patch({ transcribe_model: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Idioma (pt, en, auto…)</Label>
              <Input
                value={form.transcribe_language}
                onChange={(e) => patch({ transcribe_language: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Prefixo da transcrição</Label>
              <Input
                value={form.transcribe_prefix}
                onChange={(e) => patch({ transcribe_prefix: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Máximo de caracteres por mensagem</Label>
              <Input
                type="number"
                min={1}
                value={form.max_message_chars}
                onChange={(e) => patch({ max_message_chars: e.target.value })}
              />
            </div>
            <div className="space-y-2 sm:col-span-2">
              <Label>Mensagens em cache por conversa</Label>
              <Input
                type="number"
                min={1}
                value={form.max_cached_per_chat}
                onChange={(e) => patch({ max_cached_per_chat: e.target.value })}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Números ignorados na transcrição</CardTitle>
          <CardDescription>
            Um número por linha, apenas dígitos. Mensagens desses números não serão
            transcritas.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            rows={5}
            value={form.ignore_numbers_text}
            onChange={(e) => patch({ ignore_numbers_text: e.target.value })}
            placeholder="5511999999999"
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Controle de ferramentas MCP</CardTitle>
          <CardDescription>
            Deixe em branco para permitir todas. Separe nomes por vírgula.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Permitir apenas (allowlist)</Label>
            <Input
              value={form.allowlist}
              onChange={(e) => patch({ allowlist: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label>Bloquear (denylist)</Label>
            <Input
              value={form.denylist}
              onChange={(e) => patch({ denylist: e.target.value })}
            />
          </div>
          <div className="space-y-2 sm:col-span-2">
            <Label>Exigir confirmação explícita</Label>
            <Input
              value={form.confirm_required_tools}
              onChange={(e) => patch({ confirm_required_tools: e.target.value })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Logs e auditoria</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2 max-w-xs">
            <Label>Nível de log</Label>
            <Select
              value={form.log_level}
              onChange={(e) => patch({ log_level: e.target.value })}
            >
              {["DEBUG", "INFO", "WARNING", "ERROR"].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </Select>
          </div>
          <div className="space-y-3">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.audit_log_enabled}
                onChange={(e) => patch({ audit_log_enabled: e.target.checked })}
              />
              Gravar log de auditoria (recomendado)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.audit_log_success}
                onChange={(e) => patch({ audit_log_success: e.target.checked })}
              />
              Incluir ações bem-sucedidas no audit
            </label>
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.log_tool_success}
                onChange={(e) => patch({ log_tool_success: e.target.checked })}
              />
              Registrar uso de ferramentas no log
            </label>
          </div>
        </CardContent>
      </Card>

      <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card/95 p-4 backdrop-blur">
        {configDirty ? (
          <p className="text-sm text-warning">Alterações não salvas</p>
        ) : (
          <span />
        )}
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={form.persist_env}
              onChange={(e) => patch({ persist_env: e.target.checked })}
            />
            Salvar no .env (persistir após reinício)
          </label>
          <Button
            variant="secondary"
            onClick={() => {
              setConfigDirty(false);
              if (state) setForm(fromState(state));
            }}
          >
            Descartar alterações
          </Button>
          <Button loading={saving} onClick={() => void onSave()}>
            <Save className="h-4 w-4" />
            Salvar configurações
          </Button>
        </div>
      </div>
    </div>
  );
}
