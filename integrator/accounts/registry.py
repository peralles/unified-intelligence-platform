from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from integrator.config import settings

ACCOUNT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")
REGISTRY_VERSION = 1


class AccountNotFoundError(Exception):
    """Conta não registrada."""


@dataclass(frozen=True)
class AccountInfo:
    id: str
    label: str
    email: str | None = None

    @property
    def token_path(self) -> Path:
        return settings.token_path_for(self.id)

    @property
    def has_token(self) -> bool:
        return self.token_path.is_file()


def _registry_path() -> Path:
    return settings.root_dir / "data" / "accounts.yaml"


def _empty_registry() -> dict[str, Any]:
    return {"version": REGISTRY_VERSION, "default_account": None, "accounts": {}}


def _load_raw() -> dict[str, Any]:
    path = _registry_path()
    if not path.is_file():
        _migrate_legacy_token()
        if not path.is_file():
            return _empty_registry()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return _empty_registry()
    data.setdefault("version", REGISTRY_VERSION)
    data.setdefault("accounts", {})
    return data


def _save_raw(data: dict[str, Any]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _migrate_legacy_token() -> None:
    """Migra data/tokens/google.json para conta 'default'."""
    legacy = settings.root_dir / "data" / "tokens" / "google.json"
    if not legacy.is_file():
        return
    default_token = settings.token_path_for("default")
    if not default_token.exists():
        default_token.parent.mkdir(parents=True, exist_ok=True)
        default_token.write_bytes(legacy.read_bytes())
    data = _empty_registry()
    data["accounts"]["default"] = {"label": "Conta padrão (migrada)", "email": None}
    data["default_account"] = "default"
    _save_raw(data)


def validate_account_id(account_id: str) -> str:
    aid = account_id.strip().lower()
    if not ACCOUNT_ID_PATTERN.match(aid):
        raise ValueError(
            "ID da conta inválido. Use letras minúsculas, números, _ ou - (ex: pessoal, profissional)."
        )
    return aid


def list_accounts() -> list[AccountInfo]:
    data = _load_raw()
    accounts = data.get("accounts") or {}
    return [
        AccountInfo(
            id=aid,
            label=(info or {}).get("label") or aid,
            email=(info or {}).get("email"),
        )
        for aid, info in sorted(accounts.items())
    ]


def list_account_ids() -> list[str]:
    return [a.id for a in list_accounts()]


def get_account(account_id: str) -> AccountInfo:
    aid = validate_account_id(account_id)
    data = _load_raw()
    info = (data.get("accounts") or {}).get(aid)
    if not info:
        raise AccountNotFoundError(
            f"Conta '{aid}' não existe. Cadastre com: integrator login {aid}"
        )
    return AccountInfo(
        id=aid,
        label=info.get("label") or aid,
        email=info.get("email"),
    )


def add_account(account_id: str, *, label: str | None = None, email: str | None = None) -> AccountInfo:
    aid = validate_account_id(account_id)
    data = _load_raw()
    accounts = data.setdefault("accounts", {})
    accounts[aid] = {
        "label": label or aid,
        "email": email,
    }
    if not data.get("default_account"):
        data["default_account"] = aid
    _save_raw(data)
    settings.token_path_for(aid).parent.mkdir(parents=True, exist_ok=True)
    invalidate_metadata_cache_only()
    return get_account(aid)


def invalidate_metadata_cache_only() -> None:
    from integrator.providers.google_tools import invalidate_metadata_cache

    invalidate_metadata_cache()


def update_account_email(account_id: str, email: str) -> None:
    aid = validate_account_id(account_id)
    data = _load_raw()
    if aid not in (data.get("accounts") or {}):
        raise AccountNotFoundError(f"Conta '{aid}' não existe.")
    data["accounts"][aid]["email"] = email
    _save_raw(data)


def set_default_account(account_id: str) -> AccountInfo:
    account = get_account(account_id)
    data = _load_raw()
    data["default_account"] = account.id
    _save_raw(data)
    return account


def get_default_account_id() -> str | None:
    data = _load_raw()
    default = data.get("default_account")
    if default and default in (data.get("accounts") or {}):
        return default
    accounts = list_account_ids()
    return accounts[0] if accounts else None


def remove_account(account_id: str) -> None:
    aid = validate_account_id(account_id)
    data = _load_raw()
    accounts = data.get("accounts") or {}
    if aid not in accounts:
        raise AccountNotFoundError(f"Conta '{aid}' não existe.")
    del accounts[aid]
    token = settings.token_path_for(aid)
    if token.is_file():
        token.unlink()
    if data.get("default_account") == aid:
        data["default_account"] = next(iter(accounts), None)
    _save_raw(data)
    _invalidate_caches(aid)


def _invalidate_caches(account_id: str) -> None:
    from integrator.providers.google_tools import invalidate_metadata_cache
    from integrator.providers.tool_cache import invalidate_live_tools

    invalidate_live_tools(account_id)
    invalidate_metadata_cache()


def resolve_account_id(explicit: str | None = None) -> str:
    if explicit:
        return get_account(explicit).id
    default = get_default_account_id()
    if default:
        return default
    raise AccountNotFoundError(
        "Nenhuma conta configurada. Execute: integrator login pessoal"
    )
