from __future__ import annotations

import argparse
import subprocess
import sys

import yaml

from integrator.hermes.config_merge import (
    DEFAULT_SERVER_NAME,
    build_sse_server_config,
    build_stdio_server_config,
    get_mcp_server_entry,
    merge_mcp_server,
)
from integrator.hermes.discovery import discover_hermes
from integrator.hermes.doctor import (
    critical_failures,
    doctor_exit_code,
    format_report,
    run_checks,
)


def cmd_hermes_doctor(args: argparse.Namespace) -> int:
    install = discover_hermes()
    results = run_checks(server_name=args.name, mode=args.mode)
    print(format_report(results, install))
    return doctor_exit_code(results)


def cmd_hermes_setup(args: argparse.Namespace) -> int:
    install = discover_hermes()
    mode = args.mode
    server_name = args.name

    results = run_checks(server_name=server_name, mode=mode)
    crit = critical_failures(results)

    if crit and not args.force:
        print(format_report(results, install), file=sys.stderr)
        print(
            "\nAbortado: pré-requisitos críticos em falta. Use --force para gravar mesmo assim.",
            file=sys.stderr,
        )
        return 1

    if mode == "sse":
        from integrator.service.macos import require_macos

        try:
            require_macos()
        except Exception as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        block = build_sse_server_config()
    else:
        block = build_stdio_server_config()

    existing = get_mcp_server_entry(install.config_path, server_name)
    if existing and not args.yes:
        print(
            f"Servidor '{server_name}' já existe em {install.config_path}.",
            file=sys.stderr,
        )
        print("Use --yes para substituir.", file=sys.stderr)
        return 1

    payload = {"mcp_servers": {server_name: block}}

    if args.dry_run:
        print("# dry-run — não gravado\n")
        print(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
        print(f"Destino: {install.config_path}")
        return 0

    try:
        changed, msg = merge_mcp_server(
            install.config_path,
            server_name,
            block,
            overwrite=bool(args.yes or existing),
        )
    except (OSError, ValueError) as exc:
        print(f"Erro ao gravar config: {exc}", file=sys.stderr)
        return 1

    if not changed:
        print(msg, file=sys.stderr)
        return 1

    if getattr(args, "verbose", False):
        print(msg)
        print(f"\nModo: {mode}")
        if mode == "stdio":
            print("Hermes iniciará: uv run --directory <repo> integrator serve")
        else:
            print(f"SSE: {block['url']}")
    else:
        print("  Hermes configurado para usar Gmail e Agenda.")

    from integrator.cli.ux import print_ready_message

    print_ready_message(verbose=getattr(args, "verbose", False))

    if not args.skip_test and install.binary is not None:
        print(f"\nTestando MCP ({server_name})…")
        try:
            result = subprocess.run(
                [str(install.binary), "mcp", "test", server_name],
                capture_output=False,
                text=True,
                timeout=120,
                check=False,
            )
            return result.returncode
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
        help="Gravar entrada MCP em ~/.hermes/config.yaml",
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
