from __future__ import annotations

import argparse
import subprocess
import sys

from integrator.clients.mcp_setup import run_all_client_checks, setup_mcp_clients
from integrator.hermes.config_merge import DEFAULT_SERVER_NAME
from integrator.hermes.discovery import discover_hermes
from integrator.hermes.doctor import doctor_exit_code, format_report


def cmd_hermes_doctor(args: argparse.Namespace) -> int:
    install = discover_hermes()
    results = run_all_client_checks(server_name=args.name, mode=args.mode)
    print(format_report(results, install))
    return doctor_exit_code(results)


def cmd_hermes_setup(args: argparse.Namespace) -> int:
    mode = args.mode
    server_name = args.name

    result = setup_mcp_clients(
        mode=mode,
        server_name=server_name,
        yes=bool(args.yes),
        force=bool(args.force),
        dry_run=bool(args.dry_run),
    )

    if not result.get("ok"):
        install = discover_hermes()
        results = run_all_client_checks(server_name=server_name, mode=mode)
        print(format_report(results, install), file=sys.stderr)
        print(f"\nAbortado: {result.get('error', 'falha')}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("# dry-run — não gravado\n")
        hermes = result.get("hermes") or {}
        claude = result.get("claude_desktop") or {}
        if hermes.get("yaml"):
            print("--- Hermes ---")
            print(hermes["yaml"])
            print(f"Destino: {hermes.get('dest')}\n")
        if claude.get("json"):
            print("--- Claude Desktop ---")
            print(claude["json"])
            print(f"Destino: {claude.get('dest')}")
        return 0

    hosts = result.get("hosts") or {}
    for name, info in hosts.items():
        if info.get("ok"):
            print(f"  {name}: {info.get('message', 'OK')}")
        elif info.get("error"):
            print(f"  {name}: ERRO — {info['error']}", file=sys.stderr)

    for hint in result.get("restart_hints") or []:
        print(f"  → {hint}")

    if getattr(args, "verbose", False):
        print(f"\nModo: {mode}")
    else:
        print("  MCP configurado para Hermes e Claude Desktop.")

    from integrator.cli.ux import print_ready_message

    print_ready_message(verbose=getattr(args, "verbose", False))

    install = discover_hermes()
    if not args.skip_test and install.binary is not None:
        print(f"\nTestando MCP Hermes ({server_name})…")
        try:
            proc = subprocess.run(
                [str(install.binary), "mcp", "test", server_name],
                capture_output=False,
                text=True,
                timeout=120,
                check=False,
            )
            return proc.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"Teste MCP falhou: {exc}", file=sys.stderr)
            return 1

    return 0


def add_hermes_subparser(sub: argparse._SubParsersAction) -> None:
    p_hermes = sub.add_parser(
        "hermes",
        help="Detectar Hermes e configurar MCP automaticamente",
    )
    hermes_sub = p_hermes.add_subparsers(dest="hermes_command", metavar="ação")

    p_doctor = hermes_sub.add_parser(
        "doctor",
        help="Verificar pré-requisitos (integrador + Hermes)",
    )
    p_doctor.add_argument(
        "--name",
        default=DEFAULT_SERVER_NAME,
        help=f"Nome do servidor MCP (padrão {DEFAULT_SERVER_NAME})",
    )
    p_doctor.add_argument(
        "--mode",
        choices=("stdio", "sse"),
        default="stdio",
        help="Modo planejado para setup (sse valida serviço macOS)",
    )
    p_doctor.set_defaults(func=cmd_hermes_doctor)

    p_setup = hermes_sub.add_parser(
        "setup",
        help="Gravar MCP em Hermes (~/.hermes) e Claude Desktop",
    )
    p_setup.add_argument(
        "--mode",
        choices=("stdio", "sse"),
        default="stdio",
        help="stdio: Hermes spawna integrator serve; sse: URL do serviço",
    )
    p_setup.add_argument(
        "--name",
        default=DEFAULT_SERVER_NAME,
        help=f"Nome em mcp_servers (padrão {DEFAULT_SERVER_NAME})",
    )
    p_setup.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar YAML sem gravar",
    )
    p_setup.add_argument(
        "--yes",
        action="store_true",
        help="Substituir entrada existente sem perguntar",
    )
    p_setup.add_argument(
        "--force",
        action="store_true",
        help="Gravar mesmo com falhas críticas no doctor",
    )
    p_setup.add_argument(
        "--skip-test",
        action="store_true",
        help="Não executar hermes mcp test após gravar",
    )
    p_setup.set_defaults(func=cmd_hermes_setup)

    def _dispatch(ns: argparse.Namespace) -> int:
        if not getattr(ns, "hermes_command", None):
            return _hermes_no_action(ns, p_hermes, hermes_sub)
        return ns.func(ns)

    p_hermes.set_defaults(func=_dispatch)


def _hermes_no_action(
    ns: argparse.Namespace,
    parent: argparse.ArgumentParser,
    sub: argparse._SubParsersAction,
) -> int:
    if getattr(ns, "hermes_command", None):
        return ns.func(ns)
    parent.print_help()
    if sub.choices:
        print("\nAções:", ", ".join(sorted(sub.choices.keys())))
    return 0
