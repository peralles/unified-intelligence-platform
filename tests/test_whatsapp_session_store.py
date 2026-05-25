from __future__ import annotations

import pytest

from integrator.config import settings
from integrator.whatsapp.session_store import (
    has_persisted_session,
    local_status_snapshot,
    remove_session_data,
)


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "whatsapp_session_dir", tmp_path / "wa")
    return tmp_path


@pytest.fixture
def default_session_paths(tmp_path, monkeypatch):
    """Simula produção: whatsapp_session_dir opcional não definido."""
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(settings, "whatsapp_session_dir", None)
    return tmp_path


def test_whatsapp_session_path_when_dir_unset(default_session_paths) -> None:
    from integrator.whatsapp.session_store import session_store_path

    assert settings.whatsapp_session_dir is None
    path = settings.whatsapp_session_path
    assert path == default_session_paths / "data" / "whatsapp"
    assert session_store_path().name == "integrator"


def test_resolve_session_dir_default(default_session_paths) -> None:
    from integrator.whatsapp.bridge_client import resolve_session_dir

    assert settings.whatsapp_session_dir is None
    assert resolve_session_dir() == settings.whatsapp_session_path


def test_local_status_without_db(isolated_settings) -> None:
    wa_dir = settings.whatsapp_session_dir
    assert wa_dir is not None
    wa_dir.mkdir(parents=True)
    snap = local_status_snapshot()
    assert snap["enabled"] is True
    assert snap["has_session_db"] is False
    assert not has_persisted_session()


def test_remove_session_clears_db(isolated_settings) -> None:
    wa_dir = settings.whatsapp_session_dir
    assert wa_dir is not None
    wa_dir.mkdir(parents=True)
    from integrator.whatsapp.session_store import WHATSAPP_CLIENT_NAME

    store = wa_dir / WHATSAPP_CLIENT_NAME
    store.write_bytes(b"x" * 10)
    assert has_persisted_session()
    removed = remove_session_data()
    assert WHATSAPP_CLIENT_NAME in removed
    assert not has_persisted_session()
