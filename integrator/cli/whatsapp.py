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
from integrator.whatsapp.watch_daemon import (
    WatchDaemonError,
    disable_watch_service,
    install_watch_service,
    run_watch_foreground,
    uninstall_watch_service,
    watch_service_status,
)


def _print_local_status() -> None:
    snap = local_status_snapshot()
    print("WhatsApp (neonize)\n")
    print(f"  Habilitado:   {'sim' if snap['enabled'] else 'não (INTEGRATOR_WHATSAPP_ENABLED=false)'}")
    print(f"  Sessão:       {snap['session_dir']}")
    if snap["has_session_db"]:
        store = snap.get("session_store_file", "integrator")
        print(f"  Artefato:     {store} ({snap['session_db_bytes']} bytes)")
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
            data = run_bridge_command("status", {"live": True, "wait_s": 25})
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
    print("\n  Transcrição automática (Apple Silicon):")
    print("    WHATSAPP_AUTO_TRANSCRIBE=true   # habilita auto-transcrição no MCP serve")
    print(f"    WHATSAPP_TRANSCRIBE_MODEL=…     # padrão: {settings.whatsapp_transcribe_model}")
    print("    WHATSAPP_TRANSCRIBE_LANGUAGE=pt # idioma (vazio=auto-detect)")
    print("    WHATSAPP_TRANSCRIBE_PREFIX=…    # prefixo da resposta (padrão: 🎙️ )")
    print("    WHATSAPP_TRANSCRIBE_ONLY_INCOMING=true  # ignorar audios enviados por você")
    print("\n  Arquivos:")
    print(f"    Sessão:   {session_path()}")
    print("    Bridge:   bridges/whatsapp-neonize/ (venv isolado, protobuf 7.x)")
    print("\n  Comandos:")
    print("    integrator whatsapp status [--live]")
    print("    integrator whatsapp pair               # QR no terminal (primeira vez ou reconfigurar)")
    print("    integrator whatsapp remove             # apagar sessão local")
    print("    integrator whatsapp disconnect         # encerra worker em memória (MCP serve)")
    print("    integrator whatsapp watch              # daemon de transcrição autônomo (sem Hermes)")
    print("    integrator whatsapp watch-service install  # instalar como LaunchAgent macOS")
    print("\n  Hermes: mesmo MCP stdio; /reload-mcp após mudanças.")
    print("  Documentação: docs/WHATSAPP.md")
    if not has_persisted_session():
        print("\n  Próximo passo: integrator whatsapp pair")
    return 0


def _cmd_pair(args: argparse.Namespace) -> int:
    settings.ensure_data_dirs()
    if getattr(args, "fresh", False):
        removed = remove_session_data()
        if removed:
            print("Sessão local anterior removida:", ", ".join(removed))
        print()
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
        outcome = str(data.get("pairing_outcome", "linked"))
        LOGGER.info("whatsapp pair OK | outcome=%s", outcome)
        if outcome == "restored":
            print(
                "\nAviso: credencial restaurada do disco (log «Successfully authenticated»), "
                "não um novo QR nesta execução."
            )
            print(
                "Se o aparelho NÃO aparece em WhatsApp → Aparelhos conectados, limpe e pareie de novo:"
            )
            print("  integrator whatsapp remove")
            print("  integrator whatsapp pair --fresh")
            return 0
        print("\nOK — dispositivo vinculado (pareamento com QR). No Hermes: nova conversa ou /reload-mcp.")
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


def _cmd_watch(args: argparse.Namespace) -> int:
    """Start the watch daemon in the foreground (auto-transcribes all incoming audio)."""
    if not settings.whatsapp_enabled:
        print(
            "WhatsApp desabilitado. Defina INTEGRATOR_WHATSAPP_ENABLED=true.",
            file=sys.stderr,
        )
        return 1
    if not has_persisted_session():
        print(
            "Nenhuma sessão WhatsApp. Pareie primeiro: integrator whatsapp pair",
            file=sys.stderr,
        )
        return 1

    model = getattr(args, "model", None) or None
    language = getattr(args, "language", None) or None
    _display_model = model or settings.whatsapp_transcribe_model
    _display_lang = language or settings.whatsapp_transcribe_language or "auto-detect"

    print("Transcrição automática de áudios WhatsApp\n")
    print(f"  Modelo:   {_display_model}")
    print(f"  Idioma:   {_display_lang}")
    print(f"  Prefixo:  {settings.whatsapp_transcribe_prefix}")
    print()
    print("Aguardando mensagens de áudio — Ctrl+C para parar.\n")

    try:
        exit_code = run_watch_foreground(model=model, language=language)
    except WatchDaemonError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nEncerrado.")
        return 0
    return exit_code if exit_code is not None else 0


def _cmd_watch_service(args: argparse.Namespace) -> int:
    """Manage the macOS LaunchAgent for the watch daemon."""
    import sys as _sys

    action = args.watch_service_action

    if action == "install":
        model = getattr(args, "model", None) or None
        language = getattr(args, "language", None) or None
        no_start = getattr(args, "no_start", False)
        try:
            path = install_watch_service(
                model=model, language=language, start=not no_start
            )
            print(f"Instalado: {path}")
            svc = watch_service_status()
            print(f"  Modelo:  {svc['model']}")
            print(f"  Idioma:  {svc['language']}")
            print(f"  Logs:    {svc['logs']}")
            if not no_start:
                print("\nServiço iniciado. Para parar:")
                print("  integrator whatsapp watch-service stop")
            else:
                print("\nPara iniciar: integrator whatsapp watch-service start")
        except WatchDaemonError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        return 0

    if action in ("start", "enable"):
        try:
            from integrator.whatsapp.watch_daemon import enable_watch_service

            enable_watch_service()
            print("Serviço de transcrição ativado.")
        except WatchDaemonError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        return 0

    if action in ("stop", "disable"):
        try:
            disable_watch_service()
            print("Serviço de transcrição desativado (plist mantido).")
            print("Reativar: integrator whatsapp watch-service start")
        except WatchDaemonError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        return 0

    if action == "uninstall":
        try:
            uninstall_watch_service()
            print("Serviço de transcrição desinstalado.")
        except WatchDaemonError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        return 0

    if action == "status":
        try:
            info = watch_service_status()
        except WatchDaemonError as exc:
            print(f"Erro: {exc}", file=sys.stderr)
            return 1
        print("Serviço de transcrição WhatsApp (LaunchAgent)\n")
        for key, value in info.items():
            print(f"  {key}: {value}")
        if _sys.platform == "darwin":
            if info["plist_exists"] and not info["loaded"]:
                print(
                    "\nPlist existe mas não carregado. Rode: "
                    "integrator whatsapp watch-service start"
                )
            elif not info["plist_exists"]:
                print(
                    "\nNão instalado. Rode: "
                    "integrator whatsapp watch-service install"
                )
        return 0

    print(f"Ação desconhecida: {action}", file=sys.stderr)
    return 1


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
    p_pair.add_argument(
        "--fresh",
        action="store_true",
        help="Apagar sessão local antes de parear (use se o celular não lista o dispositivo)",
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

    p_watch = wa_sub.add_parser(
        "watch",
        help="Daemon de transcrição autônomo: transcreve áudios recebidos sem Hermes",
    )
    p_watch.add_argument(
        "--model",
        metavar="MODEL",
        default=None,
        help=(
            "Modelo mlx-whisper (ex: mlx-community/whisper-large-v3-turbo-q4). "
            f"Padrão: {settings.whatsapp_transcribe_model}"
        ),
    )
    p_watch.add_argument(
        "--language",
        metavar="LANG",
        default=None,
        help="Código de idioma (ex: pt, en). Padrão: auto-detect.",
    )
    p_watch.set_defaults(func=_cmd_watch)

    # watch-service: macOS LaunchAgent management
    p_ws = wa_sub.add_parser(
        "watch-service",
        help="macOS: instalar/gerenciar LaunchAgent do daemon de transcrição",
    )
    ws_sub = p_ws.add_subparsers(
        dest="watch_service_action", metavar="ação", required=True
    )

    _ws_model_args = dict(
        dest="model",
        metavar="MODEL",
        default=None,
        help="Modelo mlx-whisper para a transcrição.",
    )
    _ws_lang_args = dict(
        dest="language",
        metavar="LANG",
        default=None,
        help="Código de idioma (ex: pt). Padrão: auto-detect.",
    )

    p_ws_install = ws_sub.add_parser("install", help="Instalar plist e iniciar serviço")
    p_ws_install.add_argument("--model", **_ws_model_args)
    p_ws_install.add_argument("--language", **_ws_lang_args)
    p_ws_install.add_argument(
        "--no-start",
        action="store_true",
        help="Só instala o plist, sem iniciar",
    )
    p_ws_install.set_defaults(func=_cmd_watch_service, watch_service_action="install")

    for _action, _help in (
        ("start", "Iniciar/reativar serviço"),
        ("enable", "Alias de start"),
        ("stop", "Parar serviço (mantém plist)"),
        ("disable", "Alias de stop"),
        ("status", "Estado do serviço de transcrição"),
        ("uninstall", "Remover plist e parar serviço"),
    ):
        _p = ws_sub.add_parser(_action, help=_help)
        _p.set_defaults(func=_cmd_watch_service, watch_service_action=_action)
