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


settings = Settings()
