from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Full access scopes (decision: acesso completo)
GOOGLE_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/calendar",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTEGRATOR_",
        env_file=".env",
        extra="ignore",
    )

    root_dir: Path = Path(__file__).resolve().parent.parent
    credentials_file: Path | None = None
    token_file: Path | None = None

    # Fase 2 — política de tools (vazio = todas permitidas, exceto denylist)
    tool_allowlist: str | None = None
    tool_denylist: str | None = None
    confirm_required_tools: str | None = None

    # Fase 2 — auditoria
    audit_log_enabled: bool = True
    audit_log_success: bool = False
    audit_log_file: Path | None = None
    audit_log_max_bytes: int = 5_242_880
    audit_log_backup_count: int = 10

    # Logging rotativo (app + erros) — fila assíncrona, sem bloquear tools
    log_level: str = "INFO"
    log_dir: Path | None = None
    log_max_bytes: int = 5_242_880
    log_backup_count: int = 5
    log_console_enabled: bool = True
    log_tool_success: bool = False

    # Serviço macOS (LaunchAgent + HTTP/SSE)
    service_host: str = "127.0.0.1"
    service_port: int = 17320

    # WhatsApp (neonize worker em bridges/whatsapp-neonize)
    whatsapp_enabled: bool = True
    whatsapp_session_dir: Path | None = None
    whatsapp_max_message_chars: int = 800
    whatsapp_max_cached_messages_per_chat: int = 5000
    whatsapp_persist_cache: bool = True

    # WhatsApp auto-transcription (mlx-whisper, Apple Silicon)
    whatsapp_auto_transcribe: bool = False
    whatsapp_transcribe_model: str = "mlx-community/whisper-large-v3-turbo"
    whatsapp_transcribe_language: str | None = None
    whatsapp_transcribe_prefix: str = "🎙️ "
    whatsapp_transcribe_only_incoming: bool = True

    @property
    def audit_log_path(self) -> Path:
        if self.audit_log_file:
            return self.audit_log_file
        return self.root_dir / "data" / "logs" / "audit.jsonl"

    @property
    def credentials_path(self) -> Path:
        if self.credentials_file:
            return self.credentials_file
        return self.root_dir / "credentials" / "credentials.json"

    default_account: str | None = None

    @property
    def token_path(self) -> Path:
        """Token legado (única conta) — preferir token_path_for(account_id)."""
        if self.token_file:
            return self.token_file
        return self.token_path_for("default")

    def token_path_for(self, account_id: str) -> Path:
        if self.token_file and account_id in ("default", self.default_account or ""):
            return self.token_file
        safe_id = account_id.strip().lower()
        return self.root_dir / "data" / "tokens" / f"{safe_id}.json"

    @property
    def whatsapp_session_path(self) -> Path:
        if self.whatsapp_session_dir:
            return self.whatsapp_session_dir
        return self.root_dir / "data" / "whatsapp"

    def ensure_data_dirs(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        self.whatsapp_session_path.mkdir(parents=True, exist_ok=True)
        if self.audit_log_enabled:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
