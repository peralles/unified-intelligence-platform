import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox, Input, Label } from "@/components/ui/input";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { useApp } from "@/context/AppContext";
import {
  toolsConfigPayload,
  toolsFormFromState,
  type ToolsConfigForm,
} from "@/lib/configForm";
import { Save } from "lucide-react";

export function FerramentasView() {
  const { state, loadTools, toolsLoaded, saveConfig } = useApp();
  const [tools, setTools] = useState<{ name: string; description?: string }[] | null>(
    null,
  );
  const [loading, setLoading] = useState(!toolsLoaded);
  const [filter, setFilter] = useState("");
  const [form, setForm] = useState<ToolsConfigForm | null>(null);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (state && !dirty) setForm(toolsFormFromState(state));
  }, [state, dirty]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadTools().then((list) => {
      if (!cancelled) {
        setTools(list);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [loadTools]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q || !tools) return tools || [];
    return tools.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        (t.description || "").toLowerCase().includes(q),
    );
  }, [tools, filter]);

  if (!state || !form) return null;

  function patch(p: Partial<ToolsConfigForm>) {
    setForm((f) => (f ? { ...f, ...p } : f));
    setDirty(true);
  }

  async function onSave() {
    if (!form) return;
    setSaving(true);
    try {
      await saveConfig(toolsConfigPayload(form));
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Política de ferramentas MCP</CardTitle>
          <CardDescription>
            Restringe o que agentes podem chamar. Vazio = todas permitidas (padrão).
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Permitir apenas (allowlist)</Label>
            <Input
              value={form.allowlist}
              onChange={(e) => patch({ allowlist: e.target.value })}
              placeholder="send_gmail_message, find_whatsapp_chats"
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
            <Label>Exigir confirmação explícita (enviar/apagar)</Label>
            <Input
              value={form.confirm_required_tools}
              onChange={(e) => patch({ confirm_required_tools: e.target.value })}
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 sm:col-span-2 border-t border-border pt-4">
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
                    setForm(toolsFormFromState(state));
                  }}
                >
                  Descartar
                </Button>
              ) : null}
              <Button loading={saving} onClick={() => void onSave()}>
                <Save className="h-4 w-4" />
                Salvar política
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-row flex-wrap items-end justify-between gap-3 space-y-0">
          <div>
            <CardTitle>
              Ferramentas disponíveis
              {tools ? ` — ${tools.length}` : ""}
            </CardTitle>
            <CardDescription>Superfície exposta via MCP neste servidor.</CardDescription>
          </div>
          <Input
            className="max-w-xs"
            placeholder="Filtrar por nome…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-12">
              <Spinner className="h-8 w-8" />
            </div>
          ) : !filtered.length ? (
            <EmptyState
              title="Nenhuma ferramenta"
              description={filter ? "Nenhum match para o filtro." : "Servidor MCP indisponível."}
            />
          ) : (
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {filtered.map((t) => (
                <div
                  key={t.name}
                  className="rounded-md border border-border bg-background/40 px-3 py-2.5"
                >
                  <code className="block font-mono text-xs text-primary">{t.name}</code>
                  {t.description ? (
                    <p className="mt-1 text-xs leading-relaxed text-muted">
                      {t.description.length > 120
                        ? `${t.description.slice(0, 120)}…`
                        : t.description}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
