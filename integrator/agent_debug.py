"""Compact debug logging for agent sessions (stderr + optional local NDJSON file)."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

_SESSION_ID = "6cef0e"
_LOG = logging.getLogger("agent_debug")


def agent_debug_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
    *,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "sessionId": _SESSION_ID,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    _LOG.info("[agent-debug] %s", json.dumps(payload, default=str))
    debug_path = os.environ.get("INTEGRATOR_DEBUG_LOG")
    if not debug_path:
        return
    try:
        with open(debug_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except OSError:
        pass
