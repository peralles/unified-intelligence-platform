# Contexto ativo

Última atualização: seed inicial (documentação de agentes).

## Estado

- MVP implementado: MCP stdio, 12 tools Gmail/Calendar, multi-conta, Fase 2 (policy, confirm, audit)
- Branch de referência no plano: `cursor/langchain-hermes-integrator-86e5`

## Pendências

- Validação manual com Google OAuth real (`credentials.json` + `integrator login`)
- Confirmar integração ponta a ponta com Hermes (`config/hermes.example.yaml` → `~/.hermes/config.yaml`)

## Próximos passos (opcionais)

- CI GitHub Actions (não existe no repo hoje)
- Novos providers OAuth no padrão `ToolProvider`
- Reduzir scopes se política de menor privilégio for exigida (hoje: acesso completo Gmail + Calendar)

## Bloqueios

- Nenhum bloqueio técnico registrado no código — depende de credenciais Google locais do operador
