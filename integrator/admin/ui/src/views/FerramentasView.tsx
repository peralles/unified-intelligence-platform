import { useEffect, useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { useApp } from "@/context/AppContext";

export function FerramentasView() {
  const { loadTools, toolsLoaded } = useApp();
  const [tools, setTools] = useState<{ name: string; description?: string }[] | null>(
    null,
  );
  const [loading, setLoading] = useState(!toolsLoaded);

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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (!tools?.length) {
    return (
      <EmptyState
        title="Nenhuma ferramenta carregada"
        description="Verifique se o servidor MCP está em execução."
      />
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Ferramentas MCP disponíveis — {tools.length} no total</CardTitle>
        <CardDescription>
          Ações que os agentes de IA podem executar através deste integrador.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          {tools.map((t) => (
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
      </CardContent>
    </Card>
  );
}
