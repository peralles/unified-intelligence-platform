# CLI — `integrator`

> **Operadores:** use o [console admin](ADMIN.md) em `http://127.0.0.1:17320/admin` (`./setup.sh admin`).

A CLI expõe apenas **bootstrap** e **runtime** do integrador. Google, WhatsApp, Hermes, logs e configuração ficam no admin web.

## Comandos

| Comando | Descrição |
|---------|-----------|
| `integrator init` | Assistente guiado: deps, Google OAuth, login, Hermes MCP |
| `integrator serve` | Servidor MCP stdio (Hermes inicia o processo) |
| `integrator serve-http` | Servidor HTTP/SSE local + console `/admin` |
| `integrator service …` | **macOS:** LaunchAgent (instalar/ativar/desativar) |

## Aliases legados

| Entrada antiga | Comportamento |
|----------------|---------------|
| `integrator-auth` | Aponta para o admin → Google |
| `integrator-serve` | Equivalente a `integrator serve` |

## Exemplos

```bash
./setup.sh                    # init interativo
integrator init -y            # init não interativo
integrator service install    # macOS: serviço persistente + admin
integrator serve-http         # foreground SSE + admin
open http://127.0.0.1:17320/admin
```

Ver também: [ADMIN.md](ADMIN.md), [WHATSAPP.md](WHATSAPP.md).
