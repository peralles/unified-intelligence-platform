"""Read/write integrator .env for admin UI (non-secret INTEGRATOR_* keys)."""

from __future__ import annotations

import os
import re
from pathlib import Path

from integrator.config import settings

_ENV_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def env_file_path() -> Path:
    return settings.root_dir / ".env"


def read_env_lines() -> list[str]:
    path = env_file_path()
    if not path.is_file():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def read_env_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in read_env_lines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_KEY.match(stripped)
        if match:
            out[match.group(1)] = match.group(2)
    return out


def env_file_writable() -> bool:
    """False when .env lives on a read-only layer (typical Docker/Coolify)."""
    path = env_file_path()
    if path.is_file():
        return os.access(path, os.W_OK)
    parent = path.parent
    return parent.exists() and os.access(parent, os.W_OK)


def upsert_env(updates: dict[str, str | None]) -> list[str]:
    """Set or remove keys in .env. None value removes the key.

    Returns env keys touched. Skips silently when .env is not writable (Docker).
    """
    if not updates:
        return []
    if not env_file_writable():
        return []
    path = env_file_path()
    lines = read_env_lines() if path.is_file() else []
    remaining = dict(updates)
    new_lines: list[str] = []
    seen: set[str] = set()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        match = _ENV_KEY.match(stripped)
        if not match:
            new_lines.append(line)
            continue
        key = match.group(1)
        if key not in remaining:
            new_lines.append(line)
            continue
        seen.add(key)
        value = remaining.pop(key)
        if value is not None:
            new_lines.append(f"{key}={value}")

    for key, value in remaining.items():
        if key in seen or value is None:
            continue
        new_lines.append(f"{key}={value}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""), encoding="utf-8")
    return list(updates.keys())


# Keys the admin UI may persist to .env (survive service restart).
PERSISTABLE_ENV: dict[str, str] = {
    "whatsapp_auto_transcribe": "INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE",
    "transcribe_private_only": "INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY",
    "transcribe_only_incoming": "INTEGRATOR_WHATSAPP_TRANSCRIBE_ONLY_INCOMING",
    "transcribe_model": "INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL",
    "transcribe_language": "INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE",
    "transcribe_prefix": "INTEGRATOR_WHATSAPP_TRANSCRIBE_PREFIX",
    "max_message_chars": "INTEGRATOR_WHATSAPP_MAX_MESSAGE_CHARS",
    "max_cached_messages_per_chat": "INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT",
    "allowlist": "INTEGRATOR_TOOL_ALLOWLIST",
    "denylist": "INTEGRATOR_TOOL_DENYLIST",
    "confirm_required_tools": "INTEGRATOR_CONFIRM_REQUIRED_TOOLS",
    "level": "INTEGRATOR_LOG_LEVEL",
    "audit_log_enabled": "INTEGRATOR_AUDIT_LOG_ENABLED",
    "audit_log_success": "INTEGRATOR_AUDIT_LOG_SUCCESS",
    "log_tool_success": "INTEGRATOR_LOG_TOOL_SUCCESS",
}


def bool_env(value: bool) -> str:
    return "true" if value else "false"
