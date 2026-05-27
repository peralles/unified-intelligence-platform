# Contexto ativo

Última atualização: continual-learning (Hermes stdio, schema MCP, plano WhatsApp).

## Estado

- MVP: MCP stdio, 12 Google + 12 Gmail extra + 36 WhatsApp (lote 5: vote poll, join link, user info, labels/drafts Gmail), Fase 2
- CLI WhatsApp: `status` (rápido + `--live`), `configure`, `pair`, `remove`, `disconnect`; checklist em AGENTS.md
- Entrada amigável: `./setup.sh` + `Makefile` (delegam à CLI)
- Auto-config Hermes: `integrator init` / `integrator hermes setup` (stdio padrão)
- Correção MCP: schemas sem `$ref` órfão; log `tool OK` em sucesso (`integrator.tools`)

## Pendências

- Validação manual com Google OAuth real (`credentials.json` + `integrator login`)
- Confirmar integração ponta a ponta com Hermes após `git pull` + `/reload-mcp` ou conversa nova

## Próximos passos (planejado)

- Validação manual WhatsApp: `integrator whatsapp pair` + tools no Hermes
- CI GitHub Actions (não existe no repo)
- Novos providers OAuth no padrão `ToolProvider`

## Hermes (operacional)

- **stdio:** Hermes inicia `integrator serve` por conversa; serviço macOS não é obrigatório
- **Reload:** só após mudar código/config do integrador ou YAML do Hermes; conversa nova costuma bastar
- Reload lento/travando UI: checar confirmação `mcp_reload_confirm`, logs em `~/.hermes/logs/`

## Bloqueios

- Nenhum bloqueio técnico no código — depende de credenciais Google locais do operador
