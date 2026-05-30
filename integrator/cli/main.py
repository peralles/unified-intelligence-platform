"""
CLI bootstrap do integrador LangChain → Hermes.

Operação diária: console web em /admin (via serve-http ou service).
"""

from __future__ import annotations

import argparse
import sys

from integrator.config import settings
from integrator.mcp.http_server import run_http_server
from integrator.mcp.server import main as run_mcp_server
from integrator.service.macos import (
    SERVICE_LABEL,
    MacServiceError,
    DEFAULT_PORT,
    disable_service,
    enable_service,
    install_service,
    require_macos,
    service_status,
    uninstall_service,
)

EPILOG = """
Operação (recomendado):
  ./setup.sh admin                      # http://127.0.0.1:17320/admin
  integrator service install            # macOS: serviço + admin persistente

Bootstrap / runtime:
  integrator init                       # 1ª config (./setup.sh)
  integrator serve                      # MCP stdio (Hermes spawn)
  integrator serve-http                 # MCP SSE + console /admin
"""


def _cmd_serve(_: argparse.Namespace) -> int:
    run_mcp_server()
    return 0


def _cmd_serve_http(args: argparse.Namespace) -> int:
    run_http_server(host=args.host, port=args.port)
    return 0


def _cmd_service(args: argparse.Namespace) -> int:
    try:
        require_macos()
    except MacServiceError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    port = args.port or settings.service_port

    try:
        if args.service_action == "install":
            path = install_service(port=port, start=not getattr(args, "no_start", False))
            print(f"Instalado: {path}")
            if not args.no_start:
                print(f"SSE:  http://{settings.service_host}:{port}/sse")
                print(f"MCP:  http://{settings.service_host}:{port}/mcp")
                print(f"Admin: http://{settings.service_host}:{port}/admin")
            else:
                print("Iniciar: integrator service start")
            return 0

        if args.service_action in ("start", "enable"):
            enable_service()
            print(f"Serviço ativo ({SERVICE_LABEL})")
            print(f"SSE:   http://{settings.service_host}:{port}/sse")
            print(f"Admin: http://{settings.service_host}:{port}/admin")
            return 0

        if args.service_action in ("stop", "disable"):
            disable_service()
            print("Serviço desativado (plist mantido).")
            print("Reativar: integrator service start")
            return 0

        if args.service_action == "uninstall":
            uninstall_service()
            print("Serviço desinstalado (plist removido).")
            return 0

        if args.service_action == "status":
            info = service_status(port=port)
            print("Serviço macOS — LangChain Integrator\n")
            for key, value in info.items():
                print(f"  {key}: {value}")
            if info["plist_exists"] and not info["loaded"]:
                print("\nPlist existe mas não está carregado. Rode: integrator service start")
            return 0

    except MacServiceError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

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

    p_svc = sub.add_parser(
        "service",
        help="macOS: instalar/ativar/desativar serviço LaunchAgent",
    )
    svc_sub = p_svc.add_subparsers(dest="service_action", metavar="ação")

    p_inst = svc_sub.add_parser("install", help="Instalar plist e ativar")
    p_inst.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Porta HTTP (padrão {DEFAULT_PORT})",
    )
    p_inst.add_argument(
        "--no-start",
        action="store_true",
        help="Só grava o plist, sem iniciar",
    )
    p_inst.set_defaults(func=_cmd_service, service_action="install")

    for action, help_text in (
        ("start", "Ativar/iniciar serviço"),
        ("enable", "Alias de start"),
        ("stop", "Desativar serviço (mantém plist)"),
        ("disable", "Alias de stop"),
        ("status", "Estado do serviço"),
        ("uninstall", "Desinstalar (remove plist)"),
    ):
        p = svc_sub.add_parser(action, help=help_text)
        p.add_argument("--port", type=int, default=None)
        p.set_defaults(func=_cmd_service, service_action=action)

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
            print("  integrator service install   # macOS\n")
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
