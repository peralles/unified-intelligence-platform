import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input, Label, Textarea } from "@/components/ui/input";
import { useApp } from "@/context/AppContext";
import { ExternalLink, Upload } from "lucide-react";

export function GoogleView() {
  const {
    state,
    onGoogleLogin,
    setDefaultAccount,
    logoutAccount,
    onGoogleSteps,
    onImportCreds,
    onSaveCreds,
  } = useApp();
  const [accountId, setAccountId] = useState("pessoal");
  const [label, setLabel] = useState("");
  const [credsJson, setCredsJson] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  if (!state) return null;
  const accounts = state.accounts?.accounts || [];
  const setup = state.setup || {};

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } catch (e) {
      console.error(e);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Contas Google conectadas</CardTitle>
          <CardDescription>
            Cada conta dá acesso ao Gmail e Google Agenda do usuário correspondente.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-secondary/30 text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Conta</th>
                  <th className="px-4 py-3 font-medium">E-mail</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {!accounts.length ? (
                  <tr>
                    <td colSpan={4} className="px-4 py-8 text-center text-muted">
                      Nenhuma conta conectada ainda.
                    </td>
                  </tr>
                ) : (
                  accounts.map((a) => (
                    <tr key={a.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-3 font-medium">
                        {a.id}
                        {a.is_default ? (
                          <Badge tone="ok" className="ml-2">
                            padrão
                          </Badge>
                        ) : null}
                      </td>
                      <td className="px-4 py-3 text-muted">{a.email || "—"}</td>
                      <td className="px-4 py-3">
                        <Badge tone={a.has_token ? "ok" : "warn"}>
                          {a.has_token ? "autenticado" : "sem token"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap justify-end gap-2">
                          {!a.is_default ? (
                            <Button
                              variant="secondary"
                              size="sm"
                              loading={busy === `def-${a.id}`}
                              onClick={() => run(`def-${a.id}`, () => setDefaultAccount(a.id))}
                            >
                              Tornar padrão
                            </Button>
                          ) : null}
                          <Button
                            variant="destructive"
                            size="sm"
                            loading={busy === `rm-${a.id}`}
                            onClick={() => run(`rm-${a.id}`, () => logoutAccount(a.id))}
                          >
                            Remover
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Conectar nova conta Google</CardTitle>
          <CardDescription>
            Abre Google OAuth na mesma aba. Credencial OAuth tipo Web com redirect{" "}
            <code className="rounded bg-secondary px-1 py-0.5 font-mono text-xs">
              {window.location.origin}/admin/oauth/google/callback
            </code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="login_account">ID da conta (ex: pessoal, trabalho)</Label>
              <Input
                id="login_account"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                placeholder="pessoal"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="login_label">Nome amigável (opcional)</Label>
              <Input
                id="login_label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Pessoal"
              />
            </div>
          </div>
          <Button onClick={() => onGoogleLogin(accountId, label)}>
            <ExternalLink className="h-4 w-4" />
            Abrir autorização no navegador
          </Button>
        </CardContent>
      </Card>

      {!setup.credentials_ready ? (
        <Card>
          <CardHeader>
            <CardTitle>Arquivo OAuth (client_secret.json)</CardTitle>
            <CardDescription>
              Baixe do Google Cloud Console (APIs &amp; Services → Credentials) e cole o
              conteúdo abaixo, ou use Importar.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                loading={busy === "steps"}
                onClick={() => run("steps", onGoogleSteps)}
              >
                Abrir Google Cloud
              </Button>
              <Button
                variant="secondary"
                loading={busy === "import"}
                onClick={() => run("import", onImportCreds)}
              >
                <Upload className="h-4 w-4" />
                Importar de ~/Downloads
              </Button>
            </div>
            <div className="space-y-2">
              <Label htmlFor="creds-json">Ou cole o JSON aqui</Label>
              <Textarea
                id="creds-json"
                rows={4}
                value={credsJson}
                onChange={(e) => setCredsJson(e.target.value)}
                placeholder='{"installed":{"client_id":"...","client_secret":"...",...}}'
                className="font-mono text-xs"
              />
            </div>
            <Button
              loading={busy === "save-creds"}
              onClick={() => run("save-creds", () => onSaveCreds(credsJson))}
            >
              Salvar JSON colado
            </Button>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
