# Instruções para agentes

## Package Manager

- Use **uv**: `uv sync --all-extras`, `uv run integrator …`
- Python 3.11+ (pin 3.12 em `.python-version`)

## Comandos por arquivo

| Tarefa | Comando |
|--------|---------|
| Lint (arquivo) | `uv run ruff check integrator/caminho/arquivo.py` |
| Lint (pacote) | `uv run ruff check integrator tests` |
| Teste (arquivo) | `uv run pytest tests/test_arquivo.py -q --tb=short` |
| Validação completa | `./scripts/validate.sh` |

## Atribuição de commit

Commits de IA devem incluir:

```
Co-Authored-By: <nome do modelo> <noreply@anthropic.com>
```

## Convenções-chave

- Settings: prefixo env `INTEGRATOR_*` — ver `integrator/config.py`, `config/integrator.example.env`
- Account IDs: `^[a-z][a-z0-9_-]{0,31}$`; entrada normalizada com `.strip().lower()`
- Superfície MCP: **12 tools** fixas (Gmail + Calendar); testes e `validate.sh` assertam o total
- Confirmação: `send_gmail_message` e `delete_calendar_event` exigem `"confirm": true` nos args
- Erros MCP: prefixo `[integrator]` em `integrator/mcp/server.py`
- Nunca commitar `credentials/`, `data/`, `.env`; tokens fora do contexto do LLM
- Código em inglês; docs/CLI em português — seguir estilo existente no módulo tocado
- `from __future__ import annotations` nos módulos `integrator/`

## Arquivos críticos

| Área | Caminho |
|------|---------|
| MCP | `integrator/mcp/server.py` |
| Tools | `integrator/providers/google_tools.py` |
| Segurança | `integrator/security/policy.py` |
| Contas | `integrator/accounts/registry.py` |
| Config | `integrator/config.py` |

## Memória do projeto

- Ler `.memory/active.md` no início de tarefas amplas
- Decisões estáveis: `.memory/decisions.md`; padrões: `.memory/patterns.md`
- Ao concluir trabalho relevante: atualizar `active.md`; promover decisões estáveis para `decisions.md`
- Manutenção: `.memory/README.md`

## Referências

- Arquitetura: `docs/PLANO_LANGCHAIN_HERMES.md`
- CLI: `docs/CLI.md`
- Hermes: `config/hermes.example.yaml`
- Implantação: `docs/ATIVIDADES_IMPLANTACAO.md`
