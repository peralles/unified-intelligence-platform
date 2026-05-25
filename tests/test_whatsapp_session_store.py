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
    db = wa_dir / "neonize.db"
    db.write_bytes(b"x" * 10)
    assert has_persisted_session()
    removed = remove_session_data()
    assert "neonize.db" in removed
    assert not has_persisted_session()
