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
import { Input, Label } from "@/components/ui/input";
import { toast } from "@/api/client";
import { useApp } from "@/context/AppContext";
import {
  CheckCircle2,
  Circle,
  ExternalLink,
  Linkedin,
  RefreshCw,
  Trash2,
} from "lucide-react";

export function LinkedInView() {
  const { state, onLinkedInConnect, linkedInDisconnect, setActiveView, refreshAll } = useApp();
  const [accountId, setAccountId] = useState("default");
  const [busy, setBusy] = useState<string | null>(null);

  if (!state) return null;

  const li = state.linkedin || {};
  const accounts = li.accounts || [];
  const clientIdSet = !!li.client_id_set;
  const clientSecretSet = !!li.client_secret_set;
  const credentialsConfigured = clientIdSet && clientSecretSet;
  const hasConnectedAccount = accounts.some((a) => a.has_token && a.token_valid !== false);

  const oauthBase =
    state.deployment?.oauth_public_base_url?.replace(/\/$/, "") ||
    window.location.origin;
  const redirectUri = `${oauthBase}/admin/oauth/linkedin/callback`;

  async function run(key: string, fn: () => Promise<void>) {
    setBusy(key);
    try {
      await fn();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Operação falhou.", "err");
    } finally {
      setBusy(null);
    }
  }

  const steps = [
    {
      done: credentialsConfigured,
      label: "Definir INTEGRATOR_LINKEDIN_CLIENT_ID e INTEGRATOR_LINKEDIN_CLIENT_SECRET",
    },
    {
      done: hasConnectedAccount,
      label: "Conectar conta LinkedIn via OAuth",
    },
  ];

  function formatExpiry(expiresAt: number | null | undefined): string {
    if (!expiresAt) return "—";
    const d = new Date(expiresAt * 1000);
    return d.toLocaleDateString("pt-BR");
  }

  return (
    <div className="space-y-5">

      {/* Header card */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#0A66C2]/10 text-[#0A66C2]">
              <Linkedin className="h-5 w-5" />
            </div>
            <div>
              <CardTitle>LinkedIn</CardTitle>
              <CardDescription>
                Conecte sua conta para postar, comentar e gerenciar publicações via MCP.
              </CardDescription>
            </div>
          </div>
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
            Redirect OAuth configurado:{" "}
            <code className="rounded bg-secondary px-1 font-mono text-[11px]">{redirectUri}</code>
          </p>
        </CardContent>
      </Card>

      {/* Status summary */}
      <Card>
        <CardHeader>
          <CardTitle>Resumo</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-border bg-background/40 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-muted">App ID</p>
            <p className="mt-1">
              <Badge tone={clientIdSet ? "ok" : "warn"}>
                {clientIdSet ? "Configurado" : "Pendente"}
              </Badge>
            </p>
          </div>
          <div className="rounded-md border border-border bg-background/40 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-muted">Secret</p>
            <p className="mt-1">
              <Badge tone={clientSecretSet ? "ok" : "warn"}>
                {clientSecretSet ? "Configurado" : "Pendente"}
              </Badge>
            </p>
          </div>
          <div className="rounded-md border border-border bg-background/40 px-3 py-2">
            <p className="text-xs uppercase tracking-wide text-muted">Contas</p>
            <p className="mt-1 font-medium">{accounts.length} conectada(s)</p>
          </div>
        </CardContent>
      </Card>

      {/* Setup guide */}
      <Card>
        <CardHeader>
          <CardTitle>Configurar App LinkedIn</CardTitle>
          <CardDescription>
            Crie um app no LinkedIn Developer Portal e adicione as variáveis de ambiente.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <ol className="space-y-3 text-sm">
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">1</span>
              <span>
                Acesse o{" "}
                <a
                  href="https://www.linkedin.com/developers/apps"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                >
                  LinkedIn Developer Portal
                  <ExternalLink className="h-3 w-3" />
                </a>{" "}
                e crie um novo app.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">2</span>
              <span>
                Na aba <strong>Products</strong>, adicione:{" "}
                <strong>Sign In with LinkedIn using OpenID Connect</strong> e{" "}
                <strong>Share on LinkedIn</strong>.
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">3</span>
              <span>
                Na aba <strong>Auth</strong>, adicione o redirect URI:
                <code className="ml-1 rounded bg-secondary px-1.5 py-0.5 font-mono text-xs">
                  {redirectUri}
                </code>
              </span>
            </li>
            <li className="flex gap-3">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">4</span>
              <span>
                Copie o <strong>Client ID</strong> e o <strong>Client Secret</strong> e defina no ambiente (Coolify ou <code>.env</code>):
              </span>
            </li>
          </ol>
          <div className="rounded-md bg-secondary/40 p-3 font-mono text-xs leading-relaxed">
            <p>INTEGRATOR_LINKEDIN_CLIENT_ID=<span className="text-muted">seu_client_id</span></p>
            <p>INTEGRATOR_LINKEDIN_CLIENT_SECRET=<span className="text-muted">seu_client_secret</span></p>
          </div>
          <p className="text-xs text-muted">
            Após definir as variáveis, reinicie o container e clique em{" "}
            <strong>Atualizar</strong> para verificar o status.
          </p>
          <Button
            variant="secondary"
            loading={busy === "refresh"}
            onClick={() => run("refresh", refreshAll)}
          >
            <RefreshCw className="h-4 w-4" />
            Verificar configuração
          </Button>
        </CardContent>
      </Card>

      {/* Connect account */}
      <Card>
        <CardHeader>
          <CardTitle>Conectar conta LinkedIn</CardTitle>
          <CardDescription>
            Autorize o acesso à sua conta para que os agentes possam publicar no LinkedIn.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-xs space-y-2">
            <Label htmlFor="li-account-id">ID da conta (ex: pessoal, trabalho)</Label>
            <Input
              id="li-account-id"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              placeholder="default"
              disabled={!credentialsConfigured}
            />
          </div>
          {!credentialsConfigured ? (
            <p className="text-sm text-warning">
              Configure as variáveis de ambiente antes de conectar.
            </p>
          ) : null}
          <Button
            disabled={!credentialsConfigured}
            onClick={() => onLinkedInConnect(accountId)}
          >
            <ExternalLink className="h-4 w-4" />
            Conectar via LinkedIn
          </Button>
          <p className="text-xs text-muted">
            Escopos solicitados:{" "}
            <code className="font-mono">openid profile email w_member_social</code>
          </p>
        </CardContent>
      </Card>

      {/* Connected accounts */}
      <Card>
        <CardHeader>
          <CardTitle>Contas conectadas</CardTitle>
          <CardDescription>
            Cada conta permite que os agentes publiquem no LinkedIn em seu nome.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto rounded-md border border-border">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-secondary/30 text-left text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Conta</th>
                  <th className="px-4 py-3 font-medium">Perfil</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Expira</th>
                  <th className="px-4 py-3 font-medium" />
                </tr>
              </thead>
              <tbody>
                {!accounts.length ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-muted">
                      Nenhuma conta conectada ainda.
                    </td>
                  </tr>
                ) : (
                  accounts.map((a) => (
                    <tr key={a.id} className="border-b border-border/60 last:border-0">
                      <td className="px-4 py-3 font-medium">{a.id}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          {a.picture ? (
                            <img
                              src={a.picture}
                              alt={a.name || a.id}
                              className="h-6 w-6 rounded-full object-cover"
                            />
                          ) : (
                            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0A66C2]/10 text-[#0A66C2]">
                              <Linkedin className="h-3 w-3" />
                            </div>
                          )}
                          <div>
                            <p className="font-medium">{a.name || "—"}</p>
                            <p className="text-xs text-muted">{a.email || "—"}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone={a.token_valid !== false ? "ok" : "warn"}>
                          {a.token_valid !== false ? "ativo" : "expirado"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-muted">
                        {formatExpiry(a.expires_at)}
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="destructive"
                          size="sm"
                          loading={busy === `rm-${a.id}`}
                          onClick={() =>
                            run(`rm-${a.id}`, () => linkedInDisconnect(a.id))
                          }
                        >
                          <Trash2 className="h-3 w-3" />
                          Remover
                        </Button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Tools reference */}
      <Card>
        <CardHeader>
          <CardTitle>Ferramentas MCP disponíveis</CardTitle>
          <CardDescription>8 tools expostas aos agentes após conectar uma conta.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-2">
            {[
              { name: "get_linkedin_profile", desc: "Perfil do usuário autenticado" },
              { name: "get_linkedin_my_posts", desc: "Lista postagens próprias recentes" },
              { name: "share_linkedin_post", desc: "Publica texto no LinkedIn ✓" },
              { name: "share_linkedin_article", desc: "Compartilha link/artigo ✓" },
              { name: "delete_linkedin_post", desc: "Remove postagem própria ✓" },
              { name: "comment_linkedin_post", desc: "Comenta em postagem ✓" },
              { name: "like_linkedin_post", desc: "Reage (curtida) a postagem ✓" },
              { name: "unlike_linkedin_post", desc: "Remove curtida de postagem ✓" },
            ].map((tool) => (
              <div
                key={tool.name}
                className="rounded-md border border-border/60 bg-background/40 px-3 py-2"
              >
                <p className="font-mono text-xs font-medium">{tool.name}</p>
                <p className="mt-0.5 text-xs text-muted">{tool.desc}</p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-muted">
            ✓ Requer <code className="font-mono">confirm=true</code> — ação pública ou
            irreversível.
          </p>
        </CardContent>
      </Card>

      <p className="text-xs text-muted">
        Problemas com redirect URI ou Coolify? Veja o menu{" "}
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
