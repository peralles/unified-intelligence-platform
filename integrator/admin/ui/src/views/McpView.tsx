import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checklist, Spinner } from "@/components/ui/misc";
import { useApp } from "@/context/AppContext";
import { RefreshCw, Settings2, Download } from "lucide-react";

export function McpView() {
  const { mcpChecks, mcpLoading, onHermesDoctor, onHermesSetup, onHermesInstall } =
    useApp();
  const [busy, setBusy] = useState<string | null>(null);

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Hermes &amp; Claude Desktop</CardTitle>
        <CardDescription>
          Configure os agentes de IA para usar as ferramentas do integrador. Após configurar,
          reinicie o Claude (⌘Q) ou use /reload-mcp no Hermes.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {mcpLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted">
            <Spinner />
            Rodando diagnóstico…
          </div>
        ) : mcpChecks ? (
          <Checklist items={mcpChecks} />
        ) : (
          <p className="text-sm text-muted">Carregando diagnóstico…</p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button loading={busy === "setup"} onClick={() => run("setup", onHermesSetup)}>
            <Settings2 className="h-4 w-4" />
            Configurar integração MCP
          </Button>
          <Button
            variant="secondary"
            loading={busy === "install"}
            onClick={() => run("install", onHermesInstall)}
          >
            <Download className="h-4 w-4" />
            Instalar Hermes
          </Button>
          <Button
            variant="secondary"
            loading={busy === "doctor"}
            onClick={() => run("doctor", onHermesDoctor)}
          >
            <RefreshCw className="h-4 w-4" />
            Rodar diagnóstico
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
