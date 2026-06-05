import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox, Label, Select } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import {
  loggingConfigPayload,
  loggingFormFromState,
  type LoggingConfigForm,
} from "@/lib/configForm";
import { Copy, RefreshCw, Save } from "lucide-react";

export function LogsView() {
  const { state, logText, currentLog, loadLog, loadFailures, saveConfig } = useApp();
  const [busy, setBusy] = useState<string | null>(null);
  const [form, setForm] = useState<LoggingConfigForm | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (state && !dirty) setForm(loggingFormFromState(state));
  }, [state, dirty]);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  }

  async function copyLog() {
    try {
      await navigator.clipboard.writeText(logText);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = logText;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
  }

  async function onSaveLogging() {
    if (!form) return;
    setSaving(true);
    try {
      await saveConfig(loggingConfigPayload(form));
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }

  if (!state || !form) return null;

  function patch(p: Partial<LoggingConfigForm>) {
    setForm((f) => (f ? { ...f, ...p } : f));
    setDirty(true);
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Logs do sistema</CardTitle>
          <CardDescription>
            Últimas linhas dos arquivos de log. Use Copiar para colar no suporte.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="secondary"
              size="sm"
              loading={busy === "integrator"}
              onClick={() => run("integrator", () => loadLog("integrator"))}
            >
              integrator.log
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={busy === "errors"}
              onClick={() => run("errors", () => loadLog("errors"))}
            >
              errors.log
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={busy === "failures"}
              onClick={() => run("failures", loadFailures)}
            >
              Falhas de auditoria
            </Button>
            <Button
              variant="secondary"
              size="sm"
              loading={busy === "refresh"}
              disabled={!currentLog}
              onClick={() =>
                currentLog && run("refresh", () => loadLog(currentLog))
              }
            >
              <RefreshCw className="h-4 w-4" />
              Atualizar
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!logText || logText.startsWith("Clique")}
              onClick={() => run("copy", copyLog)}
            >
              <Copy className="h-4 w-4" />
              Copiar
            </Button>
          </div>
          <pre className="scrollbar-thin max-h-[520px] overflow-auto rounded-md border border-border bg-background p-4 font-mono text-xs leading-relaxed text-foreground/90">
            {logText}
          </pre>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Logs e auditoria</CardTitle>
          <CardDescription>Nível de verbosidade e registro de uso de ferramentas.</CardDescription>
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
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox
                checked={form.persist_env}
                onChange={(e) => patch({ persist_env: e.target.checked })}
              />
              Salvar no .env quando possível
            </label>
            <Button loading={saving} onClick={() => void onSaveLogging()}>
              <Save className="h-4 w-4" />
              Salvar logging
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
