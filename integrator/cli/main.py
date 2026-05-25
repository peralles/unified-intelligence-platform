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
from integrator.mcp.server import main as run_mcp_server
from integrator.providers.google_tools import list_all_tool_metadata

EPILOG = """
Exemplos:
  integrator login pessoal              # 1ª conta (Gmail + Calendar)
  integrator login profissional -l Trabalho
  integrator accounts                 # listar contas
  integrator use profissional           # conta padrão para o Hermes
  integrator status
  integrator serve                    # servidor MCP
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


def _cmd_serve(_: argparse.Namespace) -> int:
    run_mcp_server()
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

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(0)
    sys.exit(args.func(args))


def main_login() -> None:
    """Alias legado: integrator-auth → integrator login."""
    main(["login"] + sys.argv[1:])


def main_serve() -> None:
    """Alias legado: integrator-serve → integrator serve."""
    main(["serve"])
