import { useRef, useState } from "react";
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
import { cn } from "@/lib/utils";
import { toast } from "@/api/client";
import { useApp } from "@/context/AppContext";
import { CheckCircle2, Circle, ExternalLink, FileJson } from "lucide-react";

export function GoogleView() {
  const {
    state,
    onGoogleLogin,
    setDefaultAccount,
    logoutAccount,
    onGoogleSteps,
    onSaveCreds,
    setActiveView,
  } = useApp();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [accountId, setAccountId] = useState("pessoal");
  const [label, setLabel] = useState("");
  const [credsJson, setCredsJson] = useState("");
  const [uploadName, setUploadName] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  if (!state) return null;
  const accounts = state.accounts?.accounts || [];
  const setup = state.setup || {};
  const defaultAccount = accounts.find((a) => a.is_default);
  const oauthBase =
    state.deployment?.oauth_public_base_url?.replace(/\/$/, "") ||
    window.location.origin;
  const redirectUri = `${oauthBase}/admin/oauth/google/callback`;
  const credentialsReady = !!setup.credentials_ready;
  const hasLinkedAccount = accounts.some((a) => a.has_token);
  const canAuthorize = credentialsReady;

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Operação falhou", "err");
    } finally {
      setBusy(null);
    }
  }

  async function saveCredentialsFromText(text: string, sourceLabel: string) {
    const trimmed = text.trim();
    if (!trimmed) return;
    try {
      JSON.parse(trimmed);
    } catch {
      throw new Error("Arquivo não é JSON válido.");
    }
    setCredsJson(trimmed);
    const ok = await onSaveCreds(trimmed);
    if (ok) setUploadName(sourceLabel);
  }

  async function handleFile(file: File | null | undefined) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".json") && file.type !== "application/json") {
      throw new Error("Selecione um arquivo .json (client_secret.json).");
    }
    if (file.size > 512_000) {
      throw new Error("Arquivo muito grande (máx. 512 KB).");
    }
    const text = await file.text();
    await saveCredentialsFromText(text, file.name);
  }

  function onFileInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    void run("upload", async () => {
      await handleFile(file);
      e.target.value = "";
    });
  }

  function onDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    void run("upload", () => handleFile(file));
  }

  const steps = [
    {
      done: credentialsReady,
      label: "Enviar client_secret.json (tipo Web application)",
    },
    {
      done: hasLinkedAccount,
      label: "Autorizar conta no Google (redirect acima no Cloud Console)",
    },
  ];

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader>
          <CardTitle>Fluxo Google</CardTitle>
          <CardDescription>
            Dois passos: credencial OAuth no servidor, depois login da conta Gmail/Calendar.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {steps.map((step) => (
            <div key={step.label} className="flex items-start gap-2 text-sm">
              {step.done ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
              ) : (
                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
              )}
              <span className={step.done ? "text-muted line-through" : ""}>{step.label}</span>
            </div>
          ))}
          <p className="pt-2 text-xs text-muted">
            Credencial fica em <code>/app/data/credentials</code> (volume persistente). Redirect
            OAuth:{" "}
            <code className="rounded bg-secondary px-1 font-mono text-[11px]">{redirectUri}</code>
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Resumo</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-border bg-background/40 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-muted">OAuth JSON</p>
            <p className="mt-1 font-medium">
              <Badge tone={credentialsReady ? "ok" : "warn"}>
                {credentialsReady ? "Configurado" : "Pendente"}
              </Badge>
            </p>
          </div>
          <div className="rounded-md border border-border bg-background/40 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-muted">Contas</p>
            <p className="mt-1 font-medium">{accounts.length} conectada(s)</p>
          </div>
          <div className="rounded-md border border-border bg-background/40 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-muted">Padrão</p>
            <p className="mt-1 truncate text-sm font-medium">
              {defaultAccount?.email || defaultAccount?.id || "—"}
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Credencial OAuth (client_secret.json)</CardTitle>
          <CardDescription>
            Tipo <strong>Web application</strong> no Google Cloud. Redirect autorizado:{" "}
            <code className="rounded bg-secondary px-1 py-0.5 font-mono text-xs">
              {redirectUri}
            </code>
            {" "}
            — defina{" "}
            <code className="rounded bg-secondary px-1 font-mono text-xs">
              INTEGRATOR_OAUTH_PUBLIC_BASE_URL
            </code>{" "}
            no Coolify se o domínio público for diferente.
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
          </div>

          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            className="sr-only"
            onChange={onFileInputChange}
          />
          <div
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") fileInputRef.current?.click();
            }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            className={cn(
              "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors",
              dragOver
                ? "border-primary bg-primary/5"
                : "border-border bg-background/50 hover:border-primary/40 hover:bg-secondary/20",
              busy === "upload" && "pointer-events-none opacity-60",
            )}
          >
            <FileJson className="h-8 w-8 text-muted" />
            <p className="text-sm font-medium">
              {busy === "upload"
                ? "Enviando…"
                : "Arraste client_secret.json ou clique para escolher"}
            </p>
            <p className="text-xs text-muted">
              JSON OAuth Web do Google Cloud — chave <code className="font-mono">web</code>, não
              Desktop
            </p>
            {uploadName ? (
              <p className="text-xs text-success">Último envio: {uploadName}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="creds-json">Ou cole o JSON aqui</Label>
            <Textarea
              id="creds-json"
              rows={4}
              value={credsJson}
              onChange={(e) => setCredsJson(e.target.value)}
              placeholder='{"web":{"client_id":"...","client_secret":"...",...}}'
              className="font-mono text-xs"
            />
          </div>
          <Button
            loading={busy === "save-creds"}
            onClick={() =>
              run("save-creds", () => saveCredentialsFromText(credsJson, "JSON colado"))
            }
          >
            Salvar JSON colado
          </Button>
          {credentialsReady ? (
            <p className="text-xs text-muted">
              Credencial salva. Envie outro arquivo ou cole JSON para substituir.
            </p>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Conectar nova conta Google</CardTitle>
          <CardDescription>
            Após salvar o JSON, autorize Gmail e Calendar para o ID da conta abaixo.
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
                disabled={!canAuthorize}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="login_label">Nome amigável (opcional)</Label>
              <Input
                id="login_label"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Pessoal"
                disabled={!canAuthorize}
              />
            </div>
          </div>
          {!canAuthorize ? (
            <p className="text-sm text-warning">
              Envie o client_secret.json antes de autorizar uma conta.
            </p>
          ) : null}
          <Button disabled={!canAuthorize} onClick={() => onGoogleLogin(accountId, label)}>
            <ExternalLink className="h-4 w-4" />
            Abrir autorização no navegador
          </Button>
        </CardContent>
      </Card>

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

      <p className="text-xs text-muted">
        Dúvidas sobre redirect ou Coolify? Veja o menu{" "}
        <button
          type="button"
          className="text-primary underline-offset-2 hover:underline"
          onClick={() => setActiveView("guia")}
        >
          Guia
        </button>
        .
      </p>
    </div>
  );
}
