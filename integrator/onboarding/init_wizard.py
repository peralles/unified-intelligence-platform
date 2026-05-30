from __future__ import annotations

import shutil
import subprocess
import sys
import time
import webbrowser
from integrator.accounts.registry import list_accounts
from integrator.auth.google_oauth import GoogleAuthError, run_interactive_login
from integrator.cli.ux import print_ready_message, step
from integrator.onboarding.preflight import repo_deps_ok, run_uv_sync
from integrator.setup.status import is_configured
from integrator.hermes.config_merge import (
    DEFAULT_SERVER_NAME,
    get_mcp_server_entry,
)
from integrator.hermes.discovery import discover_hermes
from integrator.onboarding.google_cloud import (
    credentials_ready,
    run_google_credentials_wizard,
)
from integrator.onboarding.links import HERMES_INSTALL


def _step_dependencies(*, verbose: bool, auto_yes: bool) -> int:
    if repo_deps_ok():
        if verbose:
            print("  Dependências: OK")
        return 0
    if auto_yes:
        return run_uv_sync(verbose=verbose)
    try:
        answer = input("\n  Instalar dependências do projeto agora? [S/n] ").strip().lower()
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    if answer in ("", "s", "sim", "y", "yes"):
        return run_uv_sync(verbose=verbose)
    print("  Rode depois: uv sync --all-extras")
    return 1


def _step_google(*, interactive: bool, auto_yes: bool) -> int:
    try:
        run_google_credentials_wizard(interactive=interactive, auto_yes=auto_yes)
        return 0
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130
    except TimeoutError as exc:
        print(f"\n  {exc}", file=sys.stderr)
        return 1


def _step_login(*, account_id: str, verbose: bool) -> int:
    accounts = list_accounts()
    if accounts and all(a.has_token for a in accounts):
        if verbose:
            print(f"  Conta(s) já autorizada(s): {', '.join(a.id for a in accounts)}")
        return 0

    aid = account_id
    if not accounts:
        aid = account_id or "pessoal"
        print(f"\n  Vamos autorizar sua conta Google (id: {aid}).")
    else:
        without = [a for a in accounts if not a.has_token]
        if without:
            aid = without[0].id
        elif account_id:
            aid = account_id

    print("  Abrindo o navegador para você autorizar Gmail e Agenda…")
    try:
        run_interactive_login(aid)
        print("  Conta Google conectada.")
        return 0
    except GoogleAuthError as exc:
        from integrator.cli.ux import friendly_google_auth_error

        print(friendly_google_auth_error(str(exc)), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCancelado.")
        return 130


def _wait_for_hermes_binary(*, interactive: bool, auto_yes: bool, timeout: float = 600) -> bool:
    if shutil.which("hermes"):
        return True
    print("\n  O agente Hermes ainda não está instalado.")
    print("  Abrindo instruções de instalação…")
    try:
        webbrowser.open(HERMES_INSTALL, new=2)
    except Exception:
        print(f"  Veja: {HERMES_INSTALL}")

    if auto_yes:
        return False

    print("  Instale o Hermes e volte aqui.")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if shutil.which("hermes"):
            print("  Hermes detectado.")
            return True
        if interactive:
            try:
                input("  Pressione Enter quando o Hermes estiver instalado (Ctrl+C cancela)… ")
            except KeyboardInterrupt:
                print()
                raise
            if shutil.which("hermes"):
                return True
        time.sleep(2)

    return bool(shutil.which("hermes"))


def _step_hermes(*, interactive: bool, auto_yes: bool, verbose: bool) -> int:
    install = discover_hermes()
    server_name = DEFAULT_SERVER_NAME
    existing = get_mcp_server_entry(install.config_path, server_name)

    if existing and not auto_yes:
        if verbose:
            print(f"  MCP '{server_name}' já configurado em {install.config_path}")
        return 0

    if not install.binary:
        try:
            if not _wait_for_hermes_binary(interactive=interactive, auto_yes=auto_yes):
                print(
                    "\n  Aviso: Hermes não encontrado. MCP gravado; instale o Hermes depois.",
                    file=sys.stderr,
                )
        except KeyboardInterrupt:
            print("\nCancelado.")
            return 130
        install = discover_hermes()

    from integrator.clients.mcp_setup import setup_mcp_clients

    result = setup_mcp_clients(mode="stdio", server_name=server_name, yes=True)
    if not result.get("ok"):
        print(f"Erro ao configurar MCP: {result.get('error')}", file=sys.stderr)
        return 1

    for host, info in (result.get("hosts") or {}).items():
        if info.get("ok") and info.get("message"):
            print(f"  {host}: {info['message']}")
        elif verbose and info.get("error"):
            print(f"  {host}: {info['error']}")

    if install.binary and auto_yes:
        if verbose:
            print(f"  Testando conexão MCP Hermes ({server_name})…")
        try:
            subprocess.run(
                [str(install.binary), "mcp", "test", server_name],
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            if verbose:
                print("  Teste MCP opcional falhou (pode testar depois no Hermes).")

    return 0


def run_init_wizard(
    *,
    auto_yes: bool = False,
    verbose: bool = False,
    account: str | None = None,
) -> int:
    """Wizard de configuração inicial."""
    interactive = not auto_yes
    total = 4

    print("\n  Configuração do integrador Gmail + Agenda para o Hermes")
    print("  Este assistente guia cada passo no navegador quando necessário.")

    step(1, total, "Preparar o projeto")
    code = _step_dependencies(verbose=verbose, auto_yes=auto_yes)
    if code != 0:
        return code

    step(2, total, "Conectar Google (Gmail + Agenda)")
    if not credentials_ready():
        code = _step_google(interactive=interactive, auto_yes=auto_yes)
        if code != 0:
            return code
    elif verbose:
        print("  Credenciais Google: já configuradas")

    step(3, total, "Autorizar sua conta")
    code = _step_login(account_id=account or "pessoal", verbose=verbose)
    if code != 0:
        return code

    step(4, total, "Ligar ao Hermes")
    code = _step_hermes(interactive=interactive, auto_yes=auto_yes, verbose=verbose)
    if code != 0:
        return code

    print_ready_message(verbose=verbose)
    return 0 if is_configured() else 1
