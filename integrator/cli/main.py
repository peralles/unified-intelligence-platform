"""
CLI bootstrap do integrador LangChain → Hermes.

Operação diária: console web em /admin (serve-http ou deploy Coolify).
"""

from __future__ import annotations

import argparse
import sys

from integrator.config import settings
from integrator.mcp.http_server import run_http_server
from integrator.mcp.server import main as run_mcp_server

EPILOG = """
Operação (recomendado):
  https://<seu-dominio>/admin          # Coolify / serve-http
  ./setup.sh admin                     # local: serve-http

Bootstrap / runtime:
  integrator init                      # 1ª config (./setup.sh)
  integrator serve                     # MCP stdio (Hermes spawn)
  integrator serve-http                # MCP SSE + console /admin
"""


def _cmd_serve(_: argparse.Namespace) -> int:
    run_mcp_server()
    return 0


def _cmd_serve_http(args: argparse.Namespace) -> int:
    run_http_server(host=args.host, port=args.port)
    return 0


def _cmd_init(args: argparse.Namespace) -> int:
    from integrator.onboarding.init_wizard import run_init_wizard

    return run_init_wizard(
        auto_yes=args.yes,
        verbose=args.verbose,
        account=args.account,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="integrator",
        description="Integrador local Gmail + Google Calendar (LangChain) para o Hermes.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Mostrar caminhos e detalhes técnicos",
    )
    sub = parser.add_subparsers(dest="command", metavar="comando")

    p_init = sub.add_parser(
        "init",
        help="Assistente guiado: Google + Hermes em um fluxo",
    )
    p_init.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Sem perguntas; executar o que faltar automaticamente",
    )
    p_init.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Mostrar detalhes técnicos",
    )
    p_init.add_argument(
        "--account",
        metavar="ID",
        default=None,
        help="ID da conta no passo de login (padrão: pessoal)",
    )
    p_init.set_defaults(func=_cmd_init)

    sub.add_parser("serve", help="Subir servidor MCP (stdio)").set_defaults(
        func=_cmd_serve
    )

    p_http = sub.add_parser(
        "serve-http",
        help="Servidor MCP HTTP/SSE + console /admin",
    )
    p_http.add_argument("--host", default=settings.service_host)
    p_http.add_argument("--port", type=int, default=settings.service_port)
    p_http.set_defaults(func=_cmd_serve_http)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    argv = list(argv) if argv is not None else None
    args = parser.parse_args(argv)
    global_verbose = bool(
        getattr(args, "verbose", False)
        or (argv and ("-v" in argv or "--verbose" in argv))
    )
    if not hasattr(args, "verbose"):
        args.verbose = global_verbose
    elif global_verbose:
        args.verbose = True
    if not args.command:
        from integrator.cli.admin_hint import admin_console_url
        from integrator.cli.ux import is_configured

        if not is_configured():
            print("Integrador Gmail + Agenda para o Hermes\n")
            print("Para começar (recomendado):\n")
            print("  ./setup.sh\n")
            print("  integrator init\n")
            print(f"\nOperação diária: {admin_console_url()}\n")
            print("  integrator serve-http   # local\n")
        else:
            print(f"Console admin: {admin_console_url()}\n")
        parser.print_help()
        sys.exit(0)
    if args.command != "serve":
        from integrator.logging_setup import setup_logging

        setup_logging()
    sys.exit(args.func(args))


def main_login() -> None:
    """Alias legado: integrator-auth → admin console."""
    from integrator.cli.admin_hint import admin_console_url

    print(f"Login Google: {admin_console_url()} → Google", file=sys.stderr)
    raise SystemExit(2)


def main_serve() -> None:
    """Alias legado: integrator-serve → integrator serve."""
    main(["serve"])
