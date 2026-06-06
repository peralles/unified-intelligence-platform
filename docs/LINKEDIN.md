# LinkedIn — Integração MCP

Guia para configurar e usar a integração LinkedIn no Integrator.

## Visão geral

A integração usa a API oficial do LinkedIn (OAuth 2.0 Authorization Code flow) com os escopos:
- `openid profile email` — perfil do usuário
- `w_member_social` — publicar, comentar, curtir e excluir posts

**8 tools MCP expostas:** `get_linkedin_profile`, `get_linkedin_my_posts`, `share_linkedin_post`, `share_linkedin_article`, `delete_linkedin_post`, `comment_linkedin_post`, `like_linkedin_post`, `unlike_linkedin_post`.

## Configuração (passo a passo)

### 1. Criar app no LinkedIn Developer Portal

1. Acesse [https://www.linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Clique em **Create app**
3. Preencha o nome, associe a uma Company Page (obrigatório)
4. Salve o app

### 2. Adicionar produtos (escopos)

Na aba **Products** do app, adicione:
- **Sign In with LinkedIn using OpenID Connect** — fornece `openid profile email`
- **Share on LinkedIn** — fornece `w_member_social`

> A aprovação de "Sign In with LinkedIn" é imediata. "Share on LinkedIn" também costuma ser automático para apps sem revisão especial.

### 3. Configurar o Redirect URI

Na aba **Auth** → **OAuth 2.0 settings** → **Authorized redirect URLs for your app**, adicione:

```
https://mcp.peralles.com/admin/oauth/linkedin/callback
```

Substitua pelo seu domínio público se diferente. Em desenvolvimento local:
```
http://127.0.0.1:17320/admin/oauth/linkedin/callback
```

Se usar proxy (Coolify), o redirect URI usa o valor de `INTEGRATOR_OAUTH_PUBLIC_BASE_URL`.

### 4. Copiar credenciais

Na aba **Auth**, copie:
- **Client ID** → `INTEGRATOR_LINKEDIN_CLIENT_ID`
- **Client Secret** → `INTEGRATOR_LINKEDIN_CLIENT_SECRET`

### 5. Definir variáveis de ambiente

**Coolify / Docker:**
```env
INTEGRATOR_LINKEDIN_CLIENT_ID=seu_client_id_aqui
INTEGRATOR_LINKEDIN_CLIENT_SECRET=seu_client_secret_aqui
```

**Local (`.env`):**
```env
INTEGRATOR_LINKEDIN_CLIENT_ID=seu_client_id_aqui
INTEGRATOR_LINKEDIN_CLIENT_SECRET=seu_client_secret_aqui
```

### 6. Conectar conta

No console admin (`/admin` → menu **LinkedIn**):

1. Defina o ID da conta (ex: `pessoal` ou `trabalho`)
2. Clique em **Conectar via LinkedIn**
3. Autorize no navegador
4. Você será redirecionado de volta ao admin com a conta conectada

## Tokens

- **Access token:** validade de 60 dias; renovado automaticamente via refresh token
- **Refresh token:** validade de 365 dias; ao expirar, reconecte no admin
- **Armazenamento:** `data/tokens/linkedin_{account_id}.json` (gitignored, volume persistente)

## Ferramentas MCP

| Tool | Descrição | Confirm? |
|------|-----------|----------|
| `get_linkedin_profile` | Perfil do usuário autenticado | Não |
| `get_linkedin_my_posts` | Lista postagens recentes | Não |
| `share_linkedin_post` | Publica texto (até 3000 chars) | **Sim** |
| `share_linkedin_article` | Compartilha link/artigo | **Sim** |
| `delete_linkedin_post` | Remove postagem pelo URN | **Sim** |
| `comment_linkedin_post` | Comenta em postagem | **Sim** |
| `like_linkedin_post` | Reage (curtida) a postagem | **Sim** |
| `unlike_linkedin_post` | Remove curtida | **Sim** |

> Tools com **Confirm=Sim** exigem `confirm: true` nos argumentos. O agente deve confirmar a ação com o usuário antes de executar.

## Exemplos de uso (via agente)

```
"Publique no LinkedIn: 'Lançamos nosso novo produto! Acesse example.com'"
→ share_linkedin_post com confirm=true após validação

"Quais foram meus últimos posts no LinkedIn?"
→ get_linkedin_my_posts

"Delete meu último post no LinkedIn (URN: urn:li:ugcPost:123456)"
→ delete_linkedin_post com confirm=true
```

## Diagnóstico

| Sintoma | Causa provável | Solução |
|---------|----------------|---------|
| "LinkedIn não configurado" | Env vars não definidas | Defina `INTEGRATOR_LINKEDIN_CLIENT_ID` e `INTEGRATOR_LINKEDIN_CLIENT_SECRET` |
| "Token LinkedIn não encontrado" | Conta não conectada | Conecte via admin `/admin` → LinkedIn |
| Erro 403 da API | Escopo insuficiente | Verifique se "Share on LinkedIn" está aprovado no app |
| Redirect URI inválido | URL não cadastrada no app | Adicione o redirect URI correto na aba Auth do app LinkedIn |
| "Sessão OAuth expirada" | State TTL expirou (>10min) | Reinicie o fluxo de conexão |

## Desabilitar LinkedIn

Para desabilitar todas as tools LinkedIn sem remover a integração:

```env
INTEGRATOR_LINKEDIN_ENABLED=false
```

As tools desaparecem do MCP sem necessidade de reiniciar (apenas `/reload-mcp` no agente).
