from __future__ import annotations

from typing import Any

from integrator.auth.google_oauth import load_google_credentials
from langchain_google_community.calendar.utils import build_calendar_service

CALENDAR_EXTRA_TOOL_NAMES = frozenset({
    "list_calendar_events_range",
})


def list_calendar_extra_tool_metadata() -> list[dict[str, Any]]:
    return [
        {
            "name": "list_calendar_events_range",
            "description": (
                "Lista eventos do Google Calendar entre time_min e time_max (RFC3339, "
                "ex: 2026-05-01T00:00:00Z). calendar_id padrão: primary."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "time_min": {
                        "type": "string",
                        "description": "Início do intervalo (RFC3339).",
                    },
                    "time_max": {
                        "type": "string",
                        "description": "Fim do intervalo (RFC3339).",
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "ID do calendário (padrão primary).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de eventos (padrão 50).",
                    },
                },
                "required": ["time_min", "time_max"],
            },
        },
    ]


def _calendar_service(account_id: str):
    credentials = load_google_credentials(account_id=account_id, interactive=False)
    return build_calendar_service(credentials=credentials)


def invoke_calendar_extra_tool(
    name: str,
    account_id: str,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    args = arguments or {}
    service = _calendar_service(account_id)

    if name == "list_calendar_events_range":
        time_min = str(args.get("time_min", "")).strip()
        time_max = str(args.get("time_max", "")).strip()
        if not time_min or not time_max:
            raise ValueError("time_min e time_max são obrigatórios (RFC3339)")
        calendar_id = str(args.get("calendar_id") or "primary").strip()
        limit = int(args.get("limit", 50))
        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=min(max(limit, 1), 250),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events: list[dict[str, Any]] = []
        for ev in result.get("items", []):
            start = ev.get("start", {})
            end = ev.get("end", {})
            events.append(
                {
                    "id": ev.get("id"),
                    "summary": ev.get("summary", ""),
                    "start": start.get("dateTime") or start.get("date"),
                    "end": end.get("dateTime") or end.get("date"),
                    "status": ev.get("status"),
                    "html_link": ev.get("htmlLink"),
                }
            )
        return {
            "calendar_id": calendar_id,
            "time_min": time_min,
            "time_max": time_max,
            "events": events,
            "count": len(events),
        }

    raise KeyError(f"Tool Calendar extra desconhecida: {name}")
