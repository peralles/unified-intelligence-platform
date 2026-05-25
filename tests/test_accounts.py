import pytest

from integrator.accounts.registry import (
    AccountNotFoundError,
    add_account,
    get_default_account_id,
    list_account_ids,
    remove_account,
    resolve_account_id,
    set_default_account,
    validate_account_id,
)
from integrator.config import settings
from integrator.security.policy import enrich_tool_schema


@pytest.fixture
def registry_env(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    (tmp_path / "data" / "tokens").mkdir(parents=True)
    return tmp_path


def test_validate_account_id():
    assert validate_account_id("Pessoal") == "pessoal"
    with pytest.raises(ValueError):
        validate_account_id("")


def test_add_and_list_accounts(registry_env):
    add_account("pessoal", label="Pessoal")
    add_account("profissional", label="Trabalho")
    assert list_account_ids() == ["pessoal", "profissional"]
    assert get_default_account_id() == "pessoal"


def test_set_default_and_resolve(registry_env):
    add_account("pessoal")
    add_account("profissional")
    set_default_account("profissional")
    assert resolve_account_id(None) == "profissional"
    assert resolve_account_id("pessoal") == "pessoal"


def test_remove_account(registry_env):
    add_account("pessoal")
    token = settings.token_path_for("pessoal")
    token.write_text("{}", encoding="utf-8")
    remove_account("pessoal")
    assert "pessoal" not in list_account_ids()
    assert not token.exists()


def test_resolve_without_accounts_fails(registry_env):
    with pytest.raises(AccountNotFoundError):
        resolve_account_id(None)


def test_schema_includes_account_enum(registry_env):
    add_account("pessoal")
    add_account("profissional")
    meta = enrich_tool_schema(
        {
            "name": "search_gmail",
            "description": "Search",
            "input_schema": {"type": "object", "properties": {}},
        }
    )
    assert meta["input_schema"]["properties"]["account"]["enum"] == [
        "pessoal",
        "profissional",
    ]


def test_legacy_google_json_migrates_to_default(registry_env):
    legacy = registry_env / "data" / "tokens" / "google.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text('{"token": "legacy"}', encoding="utf-8")
    from integrator.accounts.registry import list_accounts

    accounts = list_accounts()
    assert len(accounts) == 1
    assert accounts[0].id == "default"
    assert settings.token_path_for("default").is_file()
