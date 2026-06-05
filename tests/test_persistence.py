from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from integrator.config import is_container, settings
from integrator.persistence import check_data_persistence, ensure_volume_marker


def test_local_dev_not_mounted_is_ok(tmp_path) -> None:
    with (
        patch("integrator.persistence.is_container", return_value=False),
        patch("integrator.persistence.settings") as mock_settings,
        patch("integrator.persistence.os.path.ismount", return_value=False),
    ):
        mock_settings.root_dir = tmp_path
        report = check_data_persistence(refresh_marker=True)

    assert report.status == "ok"
    assert report.writable is True
    assert report.mounted is False
    assert report.volume_id


def test_container_without_mount_warns(tmp_path) -> None:
    with (
        patch("integrator.persistence.is_container", return_value=True),
        patch("integrator.persistence.settings") as mock_settings,
        patch("integrator.persistence.os.path.ismount", return_value=False),
    ):
        mock_settings.root_dir = tmp_path
        report = check_data_persistence()

    assert report.status == "warn"
    assert report.docker_mode is True
    assert "redeploy" in report.message.lower()


def test_container_with_mount_ok(tmp_path) -> None:
    with (
        patch("integrator.persistence.is_container", return_value=True),
        patch("integrator.persistence.settings") as mock_settings,
        patch("integrator.persistence.os.path.ismount", return_value=True),
    ):
        mock_settings.root_dir = tmp_path
        report = check_data_persistence(refresh_marker=True)

    assert report.status == "ok"
    assert report.mounted is True


def test_not_writable_errors(tmp_path) -> None:
    data = tmp_path / "data"
    data.mkdir()

    with (
        patch("integrator.persistence.is_container", return_value=True),
        patch("integrator.persistence.settings") as mock_settings,
        patch("integrator.persistence._probe_writable", return_value=False),
        patch("integrator.persistence.os.path.ismount", return_value=False),
    ):
        mock_settings.root_dir = tmp_path
        report = check_data_persistence()

    assert report.status == "error"
    assert report.writable is False


def test_marker_stable_across_refresh(tmp_path) -> None:
    with (
        patch("integrator.persistence.is_container", return_value=False),
        patch("integrator.persistence.settings") as mock_settings,
    ):
        mock_settings.root_dir = tmp_path
        first = check_data_persistence(refresh_marker=True)
        second = check_data_persistence(refresh_marker=True)

    assert first.volume_id == second.volume_id


def test_ensure_volume_marker_returns_report(tmp_path) -> None:
    with (
        patch("integrator.persistence.is_container", return_value=False),
        patch("integrator.persistence.settings") as mock_settings,
    ):
        mock_settings.root_dir = tmp_path
        report = ensure_volume_marker()

    assert report.status == "ok"
    marker = tmp_path / "data" / ".integrator" / "volume_marker.json"
    assert marker.is_file()


def test_is_container_matches_dockerenv() -> None:
    expected = Path("/.dockerenv").is_file()
    assert is_container() is expected


def test_health_endpoint_includes_persistence(monkeypatch) -> None:
    monkeypatch.setattr(settings, "admin_username", None)
    monkeypatch.setattr(settings, "admin_password", None)
    from starlette.testclient import TestClient

    from integrator.mcp.http_server import create_starlette_app

    client = TestClient(create_starlette_app(), raise_server_exceptions=True)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "persistence" in body
    assert body["persistence"]["status"] in {"ok", "warn", "error"}
