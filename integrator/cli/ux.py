from __future__ import annotations

from integrator.config import settings
from integrator.setup.status import configuration_summary, is_configured

__all__ = [
    "configuration_summary",
    "friendly_google_auth_error",
    "is_configured",
    "print_ready_message",
    "step",
]


def step(number: int, total: int, title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  Passo {number}/{total}: {title}")
    print(f"{'=' * 60}")


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
        print('     "Liste meus chats do WhatsApp" (após parear no admin)')
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
            "Abra o admin: ./setup.sh admin\n"
            "(Ou rode integrator init no bootstrap.)"
        )
    if "Token não encontrado" in message or "integrator login" in message:
        return (
            "Sua conta Google ainda não foi autorizada.\n"
            "Abra o admin: ./setup.sh admin\n"
            "ou rode integrator init"
        )
    return message
