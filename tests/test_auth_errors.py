import pytest

from integrator.auth.google_oauth import GoogleAuthError, load_google_credentials
from integrator.config import settings


def test_load_credentials_fails_without_token(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "credentials_file", tmp_path / "credentials.json")
    monkeypatch.setattr(settings, "token_file", tmp_path / "data/tokens/google.json")
    (tmp_path / "credentials.json").write_text('{"installed":{}}')
    (tmp_path / "data/tokens").mkdir(parents=True)

    with pytest.raises(GoogleAuthError, match="Token não encontrado"):
        load_google_credentials(interactive=False)
