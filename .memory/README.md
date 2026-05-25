# Memória do projeto

Arquivos curtos para continuidade entre sessões de agentes. Não duplicar `docs/` inteiro — linkar.

## Arquivos

| Arquivo | Uso |
|---------|-----|
| `active.md` | Foco atual, pendências, bloqueios (vivo; máx. ~80 linhas) |
| `decisions.md` | Decisões de arquitetura estáveis (ADRs resumidos) |
| `patterns.md` | Padrões de código e MCP observáveis no repo |

## Quando atualizar

- **active.md** — ao mudar prioridades, concluir marcos ou descobrir bloqueios
- **decisions.md** — quando uma escolha técnica for definitiva (mover de `active.md` se aplicável)
- **patterns.md** — quando um padrão novo for adotado em vários arquivos

## O que não guardar aqui

- Secrets, tokens, `credentials.json`, conteúdo de `data/`
- Logs de sessão longos ou dumps de conversa
- Cópia integral de `docs/PLANO_LANGCHAIN_HERMES.md`
