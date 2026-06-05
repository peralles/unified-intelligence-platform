"""Structured ops events for neonize worker stderr (same event= format as integrator)."""

from __future__ import annotations

import logging
import re
from typing import Any

_MAX_FIELD_LEN = 240
_SAFE_KEY = re.compile(r"^[a-z][a-z0-9_]{0,31}$")


def redact_jid(jid: str | None) -> str:
    if not jid:
        return "-"
    if "@" not in jid:
        tail = jid[-4:] if len(jid) >= 4 else jid
        return f"***{tail}"
    user, server = jid.rsplit("@", 1)
    digits = re.sub(r"\D", "", user)
    if len(digits) >= 4:
        return f"***{digits[-4:]}@{server}"
    return f"***@{server}"


def truncate(value: Any, *, limit: int = _MAX_FIELD_LEN) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def format_fields(**fields: Any) -> str:
    parts: list[str] = []
    for key in sorted(fields):
        if not _SAFE_KEY.match(key):
            continue
        value = fields[key]
        if value is None:
            continue
        parts.append(f"{key}={truncate(value)}")
    return " | ".join(parts)


def log_event(
    event: str,
    *,
    level: int = logging.INFO,
    logger_name: str = "whatsapp",
    exc_info: bool | BaseException | None = False,
    **fields: Any,
) -> None:
    name = event.strip()
    if not name:
        raise ValueError("event name required")
    msg = f"event={name}"
    tail = format_fields(**fields)
    if tail:
        msg = f"{msg} | {tail}"
    logging.getLogger(logger_name).log(level, msg, exc_info=exc_info)
