import { useEffect, useState } from "react";
import { api } from "@/api/client";
import { MarkdownDoc } from "@/components/MarkdownDoc";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/misc";

export function GuiaView() {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api<{ markdown?: string }>("/admin/api/guide")
      .then((data) => {
        if (!cancelled) setMarkdown(data.markdown || "");
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Guia de operação</CardTitle>
        <CardDescription>
          O essencial para operar o integrador no servidor e configurar agentes no seu
          computador.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : markdown === null ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-8 w-8" />
          </div>
        ) : (
          <MarkdownDoc source={markdown} />
        )}
      </CardContent>
    </Card>
  );
}
