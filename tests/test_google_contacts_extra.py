from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from integrator.providers.google_contacts_extra import invoke_contacts_extra_tool
from integrator.providers.tools import CONTACTS_EXTRA_TOOL_COUNT
from integrator.security.policy import get_confirm_required_tools


def test_contacts_extra_tool_count() -> None:
    assert CONTACTS_EXTRA_TOOL_COUNT == 5


def test_contacts_mutations_require_confirm() -> None:
    confirm = get_confirm_required_tools()
    assert "create_google_contact" in confirm
    assert "update_google_contact" in confirm
    assert "delete_google_contact" in confirm
    assert "search_google_contacts" not in confirm


@patch("integrator.providers.google_contacts_extra._people_service")
def test_search_google_contacts_with_query(mock_svc_fn: MagicMock) -> None:
    service = MagicMock()
    mock_svc_fn.return_value = service
    service.people.return_value.searchContacts.return_value.execute.return_value = {
        "results": [
            {
                "person": {
                    "resourceName": "people/c1",
                    "etag": "etag1",
                    "names": [{"displayName": "Ana Silva"}],
                    "emailAddresses": [{"value": "ana@example.com"}],
                }
            }
        ]
    }
    result = invoke_contacts_extra_tool(
        "search_google_contacts",
        "pessoal",
        {"query": "Ana", "limit": 10},
    )
    assert result["count"] == 1
    assert result["contacts"][0]["display_name"] == "Ana Silva"
    service.people.return_value.searchContacts.assert_called_once()


@patch("integrator.providers.google_contacts_extra._people_service")
def test_search_google_contacts_list_recent(mock_svc_fn: MagicMock) -> None:
    service = MagicMock()
    mock_svc_fn.return_value = service
    service.people.return_value.connections.return_value.list.return_value.execute.return_value = {
        "connections": [
            {
                "resourceName": "people/c2",
                "etag": "etag2",
                "names": [{"displayName": "Bruno"}],
            }
        ]
    }
    result = invoke_contacts_extra_tool("search_google_contacts", "pessoal", {})
    assert result["count"] == 1
    service.people.return_value.connections.return_value.list.assert_called_once()


@patch("integrator.providers.google_contacts_extra._people_service")
def test_create_google_contact(mock_svc_fn: MagicMock) -> None:
    service = MagicMock()
    mock_svc_fn.return_value = service
    service.people.return_value.createContact.return_value.execute.return_value = {
        "resourceName": "people/c3",
        "etag": "etag3",
        "names": [{"givenName": "Carla", "displayName": "Carla"}],
        "emailAddresses": [{"value": "carla@example.com"}],
    }
    result = invoke_contacts_extra_tool(
        "create_google_contact",
        "pessoal",
        {"given_name": "Carla", "email": "carla@example.com"},
    )
    assert result["contact"]["resource_name"] == "people/c3"


@patch("integrator.providers.google_contacts_extra._people_service")
def test_delete_google_contact(mock_svc_fn: MagicMock) -> None:
    service = MagicMock()
    mock_svc_fn.return_value = service
    service.people.return_value.deleteContact.return_value.execute.return_value = None
    result = invoke_contacts_extra_tool(
        "delete_google_contact",
        "pessoal",
        {"resource_name": "people/c99"},
    )
    assert result["deleted"] is True


def test_create_google_contact_requires_fields() -> None:
    with patch("integrator.providers.google_contacts_extra._people_service"):
        with pytest.raises(ValueError, match="given_name"):
            invoke_contacts_extra_tool("create_google_contact", "pessoal", {})
