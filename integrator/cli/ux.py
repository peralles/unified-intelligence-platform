from __future__ import annotations

from integrator.accounts.registry import list_accounts
from integrator.config import settings
from integrator.onboarding.google_cloud import credentials_ready
from integrator.whatsapp.session_store import has_persisted_session


def step(number: int, total: int, title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  Passo {number}/{total}: {title}")
    print(f"{'=' * 60}")


def is_configured() -> bool:
    """True se credenciais Google e pelo menos uma conta com token existem."""
    if not credentials_ready():
        return False
    return any(a.has_token for a in list_accounts())


def configuration_summary() -> tuple[str, str | None]:
    """
    Returns:
        (status_label, next_step_command_or_none)
    """
    if not credentials_ready():
        return "incompleta", "./setup.sh"
    accounts = list_accounts()
    if not any(a.has_token for a in accounts):
        return "incompleta", "./setup.sh"
    if settings.whatsapp_enabled and not has_persisted_session():
        return "completa (Google)", "integrator whatsapp pair"
    return "completa", None


def print_ready_message(*, verbose: bool = False) -> None:
    print("\n" + "=" * 60)
    print("  Pronto! Gmail e Agenda estão ligados ao Hermes.")
    print("=" * 60)
    print("\n  1. Abra o Hermes e comece uma conversa nova")
    print("     (ou digite /reload-mcp se já estiver aberto)")
    print("  2. Se o Hermes pedir modelo de IA, configure com: hermes model")
    print("\n  No chat você pode pedir, por exemplo:")
    print('     "Quais e-mails não lidos tenho?" ou "O que tenho na agenda hoje?"')
    if settings.whatsapp_enabled:
        print('     "Liste meus chats do WhatsApp" (após: integrator whatsapp pair)')
    if verbose:
        print("\n  Detalhes técnicos:")
        print(f"    Credenciais: {settings.credentials_path}")
        print(f"    Contas: {settings.root_dir / 'data/accounts.yaml'}")
        from integrator.hermes.discovery import discover_hermes

        install = discover_hermes()
        print(f"    Hermes config: {install.config_path}")


def friendly_google_auth_error(message: str) -> str:
    if "OAuth não encontrado" in message or "credentials" in message.lower():
        return (
            "Falta configurar o acesso ao Google.\n"
            "Rode: integrator init\n"
            "(O assistente abre o navegador e configura tudo para você.)"
        )
    if "Token não encontrado" in message or "integrator login" in message:
        return (
            "Sua conta Google ainda não foi autorizada.\n"
            "Rode: integrator init\n"
            "ou: integrator login pessoal"
        )
    return message
