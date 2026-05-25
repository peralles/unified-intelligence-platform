"""URLs abertas pelo wizard de configuração."""

from __future__ import annotations

from dataclasses import dataclass

UV_INSTALL = "https://docs.astral.sh/uv/getting-started/installation/"

HERMES_INSTALL = (
    "https://dev.to/emmanuelthecoder/"
    "hermes-the-self-improving-agent-you-can-actually-run-yourself-555l"
)

# Google Cloud Console — usuário escolhe o projeto na interface
GMAIL_API_LIBRARY = (
    "https://console.cloud.google.com/apis/library/gmail.googleapis.com"
)
CALENDAR_API_LIBRARY = (
    "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com"
)
OAUTH_CONSENT = "https://console.cloud.google.com/apis/credentials/consent"
OAUTH_CREATE_DESKTOP = (
    "https://console.cloud.google.com/apis/credentials/oauthclient"
    "?authuser=0"
)


@dataclass(frozen=True)
class GoogleSetupLink:
    title: str
    url: str
    instruction: str


GOOGLE_SETUP_STEPS: tuple[GoogleSetupLink, ...] = (
    GoogleSetupLink(
        "Ativar Gmail API",
        GMAIL_API_LIBRARY,
        "Clique em Ativar (ou Enable).",
    ),
    GoogleSetupLink(
        "Ativar Google Calendar API",
        CALENDAR_API_LIBRARY,
        "Clique em Ativar (ou Enable).",
    ),
    GoogleSetupLink(
        "Tela de consentimento OAuth",
        OAUTH_CONSENT,
        "Se pedido, configure o app como Interno ou Externo e salve.",
    ),
    GoogleSetupLink(
        "Criar credencial OAuth (Desktop)",
        OAUTH_CREATE_DESKTOP,
        "Tipo: Aplicativo para computador (Desktop). Baixe o JSON.",
    ),
)
