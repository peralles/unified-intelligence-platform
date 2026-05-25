from __future__ import annotations

import argparse
import sys

from integrator.auth.google_oauth import GoogleAuthError, run_interactive_login
from integrator.config import GOOGLE_SCOPES, settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="OAuth Google unificado (Gmail + Calendar) para o integrador Hermes."
    )
    parser.parse_args()

    print("Escopos:", ", ".join(GOOGLE_SCOPES))
    print("Credenciais:", settings.credentials_path)
    print("Token (saída):", settings.token_path)
    print("\nAbrindo navegador para autorização Google...\n")

    try:
        token_path = run_interactive_login()
    except GoogleAuthError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(130)

    print(f"OK — token salvo em {token_path}")
    print("Inicie o servidor MCP: python -m integrator.cli.serve")


if __name__ == "__main__":
    main()
