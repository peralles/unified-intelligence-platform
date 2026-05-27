from __future__ import annotations

from unittest.mock import MagicMock, patch

from integrator.providers.google_calendar_extra import invoke_calendar_extra_tool


@patch("integrator.providers.google_calendar_extra._calendar_service")
def test_list_calendar_events_range(mock_svc_fn: MagicMock) -> None:
    service = MagicMock()
    mock_svc_fn.return_value = service
    service.events.return_value.list.return_value.execute.return_value = {
        "items": [
            {
                "id": "ev1",
                "summary": "Reunião",
                "start": {"dateTime": "2026-05-27T10:00:00Z"},
                "end": {"dateTime": "2026-05-27T11:00:00Z"},
                "status": "confirmed",
            }
        ]
    }
    result = invoke_calendar_extra_tool(
        "list_calendar_events_range",
        "pessoal",
        {
            "time_min": "2026-05-27T00:00:00Z",
            "time_max": "2026-05-28T00:00:00Z",
        },
    )
    assert result["count"] == 1
    assert result["events"][0]["summary"] == "Reunião"
