from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from integrator.admin.env_file import env_file_writable, upsert_env


def test_env_file_writable_false_on_read_only_file(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("INTEGRATOR_LOG_LEVEL=INFO\n", encoding="utf-8")
    env_path.chmod(0o444)
    with patch("integrator.admin.env_file.env_file_path", return_value=env_path):
        assert env_file_writable() is False
        keys = upsert_env({"INTEGRATOR_LOG_LEVEL": "DEBUG"})
        assert keys == []
        assert "DEBUG" not in env_path.read_text(encoding="utf-8")
    env_path.chmod(0o644)


def test_upsert_env_writes_when_writable(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    with patch("integrator.admin.env_file.env_file_path", return_value=env_path):
        assert env_file_writable() is True
        keys = upsert_env({"INTEGRATOR_LOG_LEVEL": "WARNING"})
        assert keys == ["INTEGRATOR_LOG_LEVEL"]
        assert "INTEGRATOR_LOG_LEVEL=WARNING" in env_path.read_text(encoding="utf-8")
