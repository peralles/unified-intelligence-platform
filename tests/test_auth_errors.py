import pytest

from integrator.accounts.registry import add_account
from integrator.auth.google_oauth import GoogleAuthError, load_google_credentials
from integrator.config import settings


def test_load_credentials_fails_without_token(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "credentials_file", tmp_path / "credentials.json")
    (tmp_path / "credentials.json").write_text('{"installed":{}}')
    add_account("pessoal")

    with pytest.raises(GoogleAuthError, match="Token não encontrado"):
        load_google_credentials(account_id="pessoal", interactive=False)
