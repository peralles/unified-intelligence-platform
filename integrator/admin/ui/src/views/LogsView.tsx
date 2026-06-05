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
import { RefreshCw } from "lucide-react";

export function LogsView() {
  const { logText, currentLog, loadLog, loadFailures } = useApp();
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
        <CardTitle>Logs do sistema</CardTitle>
        <CardDescription>
          Últimas linhas dos arquivos de log. Use para diagnosticar problemas.
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
        </div>
        <pre className="scrollbar-thin max-h-[520px] overflow-auto rounded-md border border-border bg-background p-4 font-mono text-xs leading-relaxed text-foreground/90">
          {logText}
        </pre>
      </CardContent>
    </Card>
  );
}
