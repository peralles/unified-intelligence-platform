# Avaliação de qualidade e performance

**Data:** gerada por `scripts/validate.sh`  
**Branch:** `cursor/langchain-hermes-integrator-86e5`

## Resumo executivo

| Área | Status | Notas |
|------|--------|-------|
| Testes automatizados | OK | 31+ testes (unit + MCP + segurança + contas + performance) |
| Lint (ruff) | OK | `integrator/`, `tests/` |
| Segurança Fase 2 | OK | allowlist, confirm, auditoria sem PII, chmod 600 |
| Logging rotativo | OK | integrator.log, errors.log, audit.jsonl + `integrator logs` |
| Multi-conta | OK | `pessoal` / `profissional`, parâmetro `account` |
| Gmail + Calendar | OK | 12 tools LangChain por conta |
| CLI | OK | `integrator` unificada + serviço macOS |
| Performance local | OK | cache de metadata e tools por conta |

## Gate de qualidade

```bash
./scripts/validate.sh
```

Inclui: `uv sync`, `pytest`, smoke imports, benchmark leve de `list_tools`.

## Performance (caminhos sem Google API)

| Operação | Meta (CI) | Otimização |
|----------|-----------|------------|
| `list_all_tool_metadata()` (2ª chamada) | < 5 ms | Cache por conjunto de contas |
| `handle_list_tools` (MCP) | < 500 ms | Reutiliza metadata cache |
| `build_live_tools(account)` (2ª chamada) | 0 rebuild | Cache por `account_id` |
| Invocação com policy block | < 10 ms | Falha antes de OAuth/Google |

Caches invalidados em: `logout`, `login` (refresh token), `add_account`.

## Limitações conhecidas

1. **Primeira chamada** a uma tool faz OAuth load + build Gmail/Calendar API (~100–500 ms+).
2. **Serviço macOS** só em `darwin`; Linux use `integrator serve` ou systemd manual.
3. **Hermes stdio** vs **serviço SSE**: escolher um modo; não misturar configs.
4. Deprecation warning de `langchain-community` (dependência transitiva Google).

## Checklist manual (pós-deploy Mac)

- [ ] `integrator login pessoal` e `profissional`
- [ ] `integrator status` mostra tokens OK
- [ ] `integrator service install` + `curl localhost:17320/health`
- [ ] Hermes lista 12 tools
- [ ] Chamada `get_calendars_info` com `"account": "pessoal"`
- [ ] `send_gmail_message` sem `confirm` → erro esperado

## Critérios de aceite técnico

- [x] `pytest` verde
- [x] `ruff check` verde
- [x] Sem secrets em logs de auditoria
- [x] MCP erros com `isError: true`
- [x] Documentação CLI + Fase 2 + serviço macOS
