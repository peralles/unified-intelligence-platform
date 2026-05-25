import plistlib
import sys

import pytest

from integrator.config import settings
from integrator.service import macos


@pytest.fixture
def darwin_env(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(macos, "is_macos", lambda: True)
    monkeypatch.setattr(settings, "root_dir", tmp_path)
    monkeypatch.setattr(macos, "launch_agents_dir", lambda: tmp_path / "LaunchAgents")
    monkeypatch.setattr(macos, "resolve_uv", lambda: "/usr/local/bin/uv")
    return tmp_path


def test_write_plist_contents(darwin_env):
    path = macos.write_plist(port=17320)
    assert path.is_file()
    with path.open("rb") as fh:
        data = plistlib.load(fh)
    assert data["Label"] == macos.SERVICE_LABEL
    assert "integrator" in data["ProgramArguments"]
    assert "serve-http" in data["ProgramArguments"]
    assert data["KeepAlive"] is True
    assert data["RunAtLoad"] is True


def test_require_macos_raises_on_linux(monkeypatch):
    monkeypatch.setattr(macos, "is_macos", lambda: False)
    with pytest.raises(macos.MacServiceError, match="macOS"):
        macos.require_macos()


def test_service_status_structure(darwin_env):
    info = macos.service_status(port=17320)
    assert info["label"] == macos.SERVICE_LABEL
    assert "url_sse" in info
    assert info["port"] == 17320
