from __future__ import annotations

import argparse
import json
import sys

from integrator.config import settings
from integrator.whatsapp.bridge_client import run_bridge_command
from integrator.whatsapp.errors import WhatsAppApiError, WhatsAppNotConnectedError
from integrator.whatsapp.logging_whatsapp import LOGGER
from integrator.whatsapp.session import WhatsAppSession
from integrator.whatsapp.session_store import (
    has_persisted_session,
    local_status_snapshot,
    remove_session_data,
    session_path,
)


def _print_local_status() -> None:
    snap = local_status_snapshot()
    print("WhatsApp (neonize)\n")
    print(f"  Habilitado:   {'sim' if snap['enabled'] else 'não (INTEGRATOR_WHATSAPP_ENABLED=false)'}")
    print(f"  Sessão:       {snap['session_dir']}")
    if snap["has_session_db"]:
        print(f"  Artefato:     neonize.db ({snap['session_db_bytes']} bytes)")
        print("  Situação:     sessão local encontrada (use --live para estado em tempo real)")
    else:
        print("  Artefato:     nenhum (não pareado)")
        print("  Situação:     aguardando pareamento")
    print(f"  Truncagem:    {snap['max_message_chars']} chars/msg nas tools MCP")


def _print_live_status(data: dict) -> None:
    state = data.get("state", "unknown")
    print("\n  Estado live:")
    print(f"    Estado:     {state}")
    print(f"    Logado:     {'sim' if data.get('logged_in') else 'não'}")
    print(f"    Conectado:  {'sim' if data.get('connected') else 'não'}")
    if data.get("push_name"):
        print(f"    Nome:       {data['push_name']}")
    if data.get("error"):
        print(f"    Erro:       {data['error']}")


def _cmd_status(args: argparse.Namespace) -> int:
    settings.ensure_data_dirs()
    _print_local_status()

    if not settings.whatsapp_enabled:
        print("\nPara expor tools no MCP: INTEGRATOR_WHATSAPP_ENABLED=true")
        return 0

    if args.live:
        try:
            data = run_bridge_command("status")
            _print_live_status(data)
        except (WhatsAppApiError, WhatsAppNotConnectedError) as exc:
            LOGGER.warning("whatsapp status live FAIL | %s", exc)
            print(f"\n  Live: falhou — {exc}", file=sys.stderr)
            return 1
    elif not has_persisted_session():
        print("\nPróximo passo: integrator whatsapp pair")
        return 0
    else:
        print("\n  Dica: integrator whatsapp status --live  (consulta o worker neonize)")

    if has_persisted_session() and not args.live:
        print("  Reconfigurar: integrator whatsapp pair")
        print("  Remover sessão: integrator whatsapp remove")
    return 0


def _cmd_configure(_: argparse.Namespace) -> int:
    settings.ensure_data_dirs()
    snap = local_status_snapshot()
    print("Configuração WhatsApp\n")
    print("  Variáveis (prefixo INTEGRATOR_):")
    print(f"    WHATSAPP_ENABLED=false          # desliga tools no MCP (padrão: {settings.whatsapp_enabled})")
    print(f"    WHATSAPP_SESSION_DIR=…          # padrão: {snap['session_dir']}")
    print(f"    WHATSAPP_MAX_MESSAGE_CHARS=…    # padrão: {settings.whatsapp_max_message_chars}")
    print("\n  Arquivos:")
    print(f"    Sessão:   {session_path()}")
    print("    Bridge:   bridges/whatsapp-neonize/ (venv isolado, protobuf 7.x)")
    print("\n  Comandos:")
    print("    integrator whatsapp status [--live]")
    print("    integrator whatsapp pair        # QR no terminal (primeira vez ou reconfigurar)")
    print("    integrator whatsapp remove      # apagar sessão local")
    print("    integrator whatsapp disconnect  # encerra worker em memória (MCP serve)")
    print("\n  Hermes: mesmo MCP stdio; /reload-mcp após mudanças.")
    print("  Documentação: docs/WHATSAPP.md")
    if not has_persisted_session():
        print("\n  Próximo passo: integrator whatsapp pair")
    return 0


def _cmd_pair(args: argparse.Namespace) -> int:
    settings.ensure_data_dirs()
    if not settings.whatsapp_enabled:
        print(
            "WhatsApp desabilitado. Defina INTEGRATOR_WHATSAPP_ENABLED=true e tente novamente.",
            file=sys.stderr,
        )
        return 1
    print("Pareamento WhatsApp — escaneie o QR no aplicativo (Dispositivos conectados).\n")
    LOGGER.info("whatsapp pair start | timeout=%.0fs", args.timeout)
    try:
        data = run_bridge_command("pair", {"timeout_s": args.timeout})
    except (WhatsAppApiError, WhatsAppNotConnectedError) as exc:
        LOGGER.warning("whatsapp pair FAIL | %s", exc)
        print(str(exc), file=sys.stderr)
        return 1
    WhatsAppSession.reset()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    if data.get("logged_in"):
        LOGGER.info("whatsapp pair OK")
        print("\nOK — sessão pareada. No Hermes: nova conversa ou /reload-mcp.")
        return 0
    print("\nPareamento incompleto. Tente novamente.", file=sys.stderr)
    return 1


def _cmd_remove(args: argparse.Namespace) -> int:
    settings.ensure_data_dirs()
    if not has_persisted_session() and not args.force:
        print("Nenhuma sessão WhatsApp local para remover.")
        print("Use --force para limpar o diretório mesmo assim.")
        return 0
    if not args.yes:
        answer = input(
            f"Remover sessão em {session_path()}? [s/N] "
        ).strip().lower()
        if answer not in ("s", "sim", "y", "yes"):
            print("Cancelado.")
            return 0
    WhatsAppSession.reset()
    try:
        run_bridge_command("shutdown")
    except (WhatsAppApiError, WhatsAppNotConnectedError):
        pass
    removed = remove_session_data()
    LOGGER.info("whatsapp remove | removed=%s", removed)
    if removed:
        print("Removido:")
        for name in removed:
            print(f"  • {name}")
    else:
        print("Diretório de sessão já estava vazio.")
    print("\nPara usar de novo: integrator whatsapp pair")
    return 0


def _cmd_disconnect(_: argparse.Namespace) -> int:
    """Encerra worker/singleton sem apagar sessão no disco."""
    WhatsAppSession.reset()
    print("Worker WhatsApp em memória encerrado (se estava ativo).")
    print("Sessão no disco mantida. Use 'integrator whatsapp status --live' para reconectar.")
    return 0


def add_whatsapp_subparser(sub: argparse._SubParsersAction) -> None:
    wa = sub.add_parser(
        "whatsapp",
        help="WhatsApp local (neonize): parear, status, remover sessão",
    )
    wa_sub = wa.add_subparsers(dest="whatsapp_action", metavar="ação", required=True)

    p_status = wa_sub.add_parser("status", help="Situação da sessão (rápido; --live consulta worker)")
    p_status.add_argument(
        "--live",
        action="store_true",
        help="Sobe o worker neonize e mostra estado conectado/logado em tempo real",
    )
    p_status.set_defaults(func=_cmd_status)

    wa_sub.add_parser("configure", help="Mostrar variáveis e caminhos").set_defaults(
        func=_cmd_configure
    )

    p_pair = wa_sub.add_parser("pair", help="Parear ou reconfigurar via QR no terminal")
    p_pair.add_argument(
        "--timeout",
        type=float,
        default=120.0,
        help="Segundos aguardando QR (padrão 120)",
    )
    p_pair.set_defaults(func=_cmd_pair)

    p_remove = wa_sub.add_parser(
        "remove",
        help="Apagar sessão local (como logout; não desinstala o bridge)",
    )
    p_remove.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Não pedir confirmação",
    )
    p_remove.add_argument(
        "--force",
        action="store_true",
        help="Limpar diretório mesmo sem neonize.db",
    )
    p_remove.set_defaults(func=_cmd_remove)

    wa_sub.add_parser(
        "disconnect",
        help="Encerrar worker em memória (MCP) sem apagar sessão",
    ).set_defaults(func=_cmd_disconnect)
