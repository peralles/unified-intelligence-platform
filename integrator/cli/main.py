"""
CLI unificada do integrador LangChain → Hermes.

Uso rápido:
  integrator status
  integrator login pessoal
  integrator login profissional --label "Trabalho"
  integrator accounts
  integrator use profissional
  integrator serve
"""

from __future__ import annotations

import argparse
import sys

from integrator.accounts.registry import (
    AccountNotFoundError,
    get_default_account_id,
    list_accounts,
    remove_account,
    set_default_account,
    validate_account_id,
)
from integrator.auth.google_oauth import GoogleAuthError, run_interactive_login
from integrator.config import GOOGLE_SCOPES, settings
from integrator.mcp.http_server import run_http_server
from integrator.mcp.server import main as run_mcp_server
from integrator.providers.google_tools import list_all_tool_metadata
from integrator.service.macos import (
    SERVICE_LABEL,
    MacServiceError,
    DEFAULT_PORT,
    disable_service,
    enable_service,
    install_service,
    is_macos,
    require_macos,
    service_status,
    uninstall_service,
)

EPILOG = """
Exemplos:
  integrator login pessoal              # 1ª conta (Gmail + Calendar)
  integrator login profissional -l Trabalho
  integrator accounts                 # listar contas
  integrator use profissional           # conta padrão para o Hermes
  integrator status
  integrator serve                    # servidor MCP (stdio, Hermes spawn)
  integrator service install          # macOS: ativar como serviço
  integrator service disable          # macOS: parar serviço
  integrator service uninstall        # macOS: remover serviço
  integrator logs --failures          # últimas falhas (audit rotativo)
  integrator logs --tail              # tail do log da aplicação
"""


def _cmd_status(_: argparse.Namespace) -> int:
    print("Integrador LangChain → Hermes (Gmail + Google Calendar)\n")
    print("Escopos:", ", ".join(GOOGLE_SCOPES))
    print("OAuth client:", settings.credentials_path)
    print()

    accounts = list_accounts()
    if not accounts:
        print("Contas: nenhuma")
        print("\nPróximo passo: integrator login pessoal")
        return 0

    default_id = get_default_account_id()
    print("Contas:")
    for acc in accounts:
        star = "*" if acc.id == default_id else " "
        token = "OK" if acc.has_token else "sem token"
        email = acc.email or "—"
        print(f"  {star} {acc.id:<14} {token:<10} {email}")
    print(f"\nPadrão: {default_id or '—'}")
    print(f"Registro: {settings.root_dir / 'data/accounts.yaml'}")
    from integrator.logging_setup import app_log_path, error_log_path

    print(f"\nLogs (rotativos): {app_log_path().parent}")
    print(f"  app:    {app_log_path()}")
    print(f"  erros:  {error_log_path()}")
    print(f"  audit:  {settings.audit_log_path}")
    print("  Falhas recentes: integrator logs --failures")
    if is_macos():
        print("\nServiço macOS: integrator service status")
    return 0


def _cmd_login(args: argparse.Namespace) -> int:
    if not args.account:
        accounts = list_accounts()
        if len(accounts) == 1:
            account_id = accounts[0].id
            print(f"Reautenticando conta '{account_id}'...")
        elif len(accounts) > 1:
            print(
                "Várias contas existem. Informe qual conectar:",
                file=sys.stderr,
            )
            print("  integrator login pessoal", file=sys.stderr)
            print("  integrator login profissional", file=sys.stderr)
            return 2
        else:
            account_id = "pessoal"
            print(f"Primeira conta: usando id '{account_id}' (Gmail + Calendar).")
            print("Outra id? Ex: integrator login profissional\n")
    else:
        account_id = validate_account_id(args.account)

    try:
        token_path = run_interactive_login(account_id, label=args.label)
    except (GoogleAuthError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130

    acc = next((a for a in list_accounts() if a.id == account_id), None)
    email = f" ({acc.email})" if acc and acc.email else ""
    print(f"OK — conta '{account_id}'{email}")
    print(f"Token: {token_path}")
    print("Servidor MCP: integrator serve")
    return 0


def _cmd_accounts(args: argparse.Namespace) -> int:
    if args.set_default:
        try:
            set_default_account(args.set_default)
            print(f"Conta padrão: {args.set_default}")
        except (AccountNotFoundError, ValueError) as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        return 0

    accounts = list_accounts()
    if not accounts:
        print("Nenhuma conta. Crie com: integrator login pessoal")
        return 0

    default_id = get_default_account_id()
    for acc in accounts:
        tags = []
        if acc.id == default_id:
            tags.append("padrão")
        if acc.has_token:
            tags.append("token OK")
        else:
            tags.append("sem token")
        extra = f" — {acc.email}" if acc.email else ""
        tag_str = f" [{', '.join(tags)}]" if tags else ""
        print(f"  {acc.id}: {acc.label}{tag_str}{extra}")
    return 0


def _cmd_logout(args: argparse.Namespace) -> int:
    try:
        remove_account(args.account)
        print(f"Conta '{args.account}' removida (token apagado).")
    except (AccountNotFoundError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_tools(_: argparse.Namespace) -> int:
    meta = list_all_tool_metadata()
    print(f"Tools MCP ({len(meta)}) — Gmail + Calendar por conta:\n")
    for m in meta:
        print(f"  • {m['name']}")
    ids = [a.id for a in list_accounts()]
    if ids:
        print(f"\nContas: {', '.join(ids)} (parâmetro account nas tools)")
    else:
        print("\nNenhuma conta — rode: integrator login pessoal")
    return 0


def _cmd_logs(args: argparse.Namespace) -> int:
    from integrator.logging_setup import (
        app_log_path,
        error_log_path,
        list_log_files,
        read_audit_failures,
        tail_file,
    )

    if args.failures:
        rows = read_audit_failures(limit=args.lines)
        if not rows:
            print("Nenhuma falha registrada no audit (últimos arquivos rotativos).")
            return 0
        print(f"Últimas {len(rows)} falhas (audit.jsonl):\n")
        for row in rows:
            err = row.get("error", "?")
            tool = row.get("tool", "?")
            acc = row.get("account", "-")
            ts = row.get("ts", "?")
            ms = row.get("duration_ms", 0)
            blocked = "blocked" if row.get("blocked") else ""
            print(f"  {ts} | {tool} | account={acc} | {err} | {ms}ms {blocked}")
        print("\nDetalhes: tail -f", error_log_path())
        return 0

    if args.tail:
        path = error_log_path() if args.errors else app_log_path()
        lines = tail_file(path, lines=args.lines)
        if not lines:
            print(f"Arquivo vazio ou inexistente: {path}")
            return 0
        print(f"--- {path} (últimas {len(lines)} linhas) ---")
        for line in lines:
            print(line)
        return 0

    print("Logs do integrador (rotativos)\n")
    for path in list_log_files():
        size_kb = path.stat().st_size / 1024
        print(f"  {path} ({size_kb:.1f} KB)")
    failures = read_audit_failures(limit=5)
    print(f"\nFalhas recentes no audit: {len(failures)} (últimas 5 listadas)")
    for row in failures:
        print(f"  • {row.get('ts')} | {row.get('tool')} | {row.get('error')}")
    print("\nComandos:")
    print("  integrator logs --tail          # app")
    print("  integrator logs --tail --errors # só WARNING+")
    print("  integrator logs --failures      # falhas de tools")
    return 0


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
            else:
                print("Iniciar: integrator service start")
            return 0

        if args.service_action in ("start", "enable"):
            enable_service()
            print(f"Serviço ativo ({SERVICE_LABEL})")
            print(f"SSE: http://{settings.service_host}:{port}/sse")
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="integrator",
        description="Integrador local Gmail + Google Calendar (LangChain) para o Hermes.",
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="comando")

    sub.add_parser("status", help="Visão geral: contas, tokens, APIs").set_defaults(
        func=_cmd_status
    )

    p_login = sub.add_parser(
        "login",
        help="Conectar conta Google (Gmail + Calendar)",
    )
    p_login.add_argument(
        "account",
        nargs="?",
        help="ID da conta (ex: pessoal, profissional)",
    )
    p_login.add_argument(
        "-l",
        "--label",
        help="Nome amigável da conta",
    )
    p_login.set_defaults(func=_cmd_login)

    p_acc = sub.add_parser("accounts", help="Listar contas")
    p_acc.add_argument(
        "--default",
        dest="set_default",
        metavar="ID",
        help="Definir conta padrão",
    )
    p_acc.set_defaults(func=_cmd_accounts)

    p_use = sub.add_parser("use", help="Definir conta padrão (atalho)")
    p_use.add_argument("account", help="ID da conta")
    p_use.set_defaults(func=lambda ns: _cmd_accounts(
        argparse.Namespace(set_default=ns.account)
    ))

    p_out = sub.add_parser("logout", help="Remover conta e token")
    p_out.add_argument("account", help="ID da conta")
    p_out.set_defaults(func=_cmd_logout)

    sub.add_parser("tools", help="Listar tools expostas ao MCP").set_defaults(
        func=_cmd_tools
    )

    sub.add_parser("serve", help="Subir servidor MCP (stdio)").set_defaults(
        func=_cmd_serve
    )

    p_http = sub.add_parser(
        "serve-http",
        help="Servidor MCP HTTP/SSE (background / LaunchAgent)",
    )
    p_http.add_argument("--host", default=settings.service_host)
    p_http.add_argument("--port", type=int, default=settings.service_port)
    p_http.set_defaults(func=_cmd_serve_http)

    p_logs = sub.add_parser("logs", help="Logs rotativos e diagnóstico de falhas")
    p_logs.add_argument(
        "--tail",
        action="store_true",
        help="Exibir final do log da aplicação",
    )
    p_logs.add_argument(
        "--errors",
        action="store_true",
        help="Com --tail: usar errors.log em vez de integrator.log",
    )
    p_logs.add_argument(
        "--failures",
        action="store_true",
        help="Listar falhas de tools (audit.jsonl)",
    )
    p_logs.add_argument(
        "-n",
        "--lines",
        type=int,
        default=40,
        help="Linhas para --tail ou --failures (padrão 40)",
    )
    p_logs.set_defaults(func=_cmd_logs)

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
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(0)
    if args.command != "logs":
        from integrator.logging_setup import setup_logging

        setup_logging()
    sys.exit(args.func(args))


def main_login() -> None:
    """Alias legado: integrator-auth → integrator login."""
    main(["login"] + sys.argv[1:])


def main_serve() -> None:
    """Alias legado: integrator-serve → integrator serve."""
    main(["serve"])
