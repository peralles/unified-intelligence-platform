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
    audit_log_file: Path | None = None

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

    @property
    def token_path(self) -> Path:
        if self.token_file:
            return self.token_file
        return self.root_dir / "data" / "tokens" / "google.json"

    def ensure_data_dirs(self) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.credentials_path.parent.mkdir(parents=True, exist_ok=True)
        if self.audit_log_enabled:
            self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)


settings = Settings()
