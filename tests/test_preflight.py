"""Tests for integrator.onboarding.preflight."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from integrator.onboarding.preflight import REPO_DEPS_TIMEOUT_SEC, repo_deps_ok


def test_repo_deps_ok_when_venv_exists(tmp_path) -> None:
    with patch("integrator.onboarding.preflight.settings") as mock_settings:
        mock_settings.root_dir = tmp_path
        (tmp_path / ".venv").mkdir()
        assert repo_deps_ok() is True


def test_repo_deps_ok_runs_uv_status_when_no_venv(tmp_path) -> None:
    with (
        patch("integrator.onboarding.preflight.settings") as mock_settings,
        patch("integrator.onboarding.preflight.shutil.which", return_value="/usr/bin/uv"),
        patch("integrator.onboarding.preflight.subprocess.run") as mock_run,
    ):
        mock_settings.root_dir = tmp_path
        mock_run.return_value = MagicMock(returncode=0)
        assert repo_deps_ok() is True
        mock_run.assert_called_once()
        assert mock_run.call_args.kwargs["timeout"] == REPO_DEPS_TIMEOUT_SEC
