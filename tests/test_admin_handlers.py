"""Tests for admin handlers."""

from __future__ import annotations

from integrator.admin import handlers


def test_setup_status_shape() -> None:
    data = handlers.setup_status(mode="stdio")
    assert "configured" in data
    assert "checks" in data
    assert isinstance(data["checks"], list)


def test_list_google_accounts() -> None:
    data = handlers.list_google_accounts()
    assert "accounts" in data
    assert "default_account" in data


def test_list_tools_count() -> None:
    data = handlers.list_tools()
    assert data["count"] >= 60
    assert len(data["tools"]) == data["count"]


def test_mac_service_info() -> None:
    data = handlers.mac_service_info()
    assert "available" in data or "platform" in data
