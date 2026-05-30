"""Runtime config persisted in data/admin/runtime.json (hot-reload by worker)."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from integrator.config import settings

RUNTIME_VERSION = 1


def normalize_phone_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def runtime_file_path() -> Path:
    return settings.admin_runtime_path


def default_runtime() -> dict[str, Any]:
    return {
        "version": RUNTIME_VERSION,
        "whatsapp": {
            "auto_transcribe": None,
            "transcribe_private_only": None,
            "transcribe_only_incoming": None,
            "transcribe_model": None,
            "transcribe_language": None,
            "transcribe_prefix": None,
            "transcribe_ignore_numbers": [],
            "max_message_chars": None,
            "max_cached_messages_per_chat": None,
        },
        "tools": {
            "allowlist": None,
            "denylist": None,
            "confirm_required_tools": None,
        },
        "logging": {
            "level": None,
            "audit_log_enabled": None,
            "audit_log_success": None,
            "log_tool_success": None,
        },
        "service": {
            "host": None,
            "port": None,
        },
    }


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


class RuntimeStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or runtime_file_path()

    def ensure_file(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self.save(default_runtime())
        return self.path

    def load(self) -> dict[str, Any]:
        self.ensure_file()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        merged = _deep_merge(default_runtime(), raw)
        merged["version"] = RUNTIME_VERSION
        return merged

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = _deep_merge(default_runtime(), data)
        payload["version"] = RUNTIME_VERSION
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def patch(self, patch: dict[str, Any]) -> dict[str, Any]:
        current = self.load()
        updated = _deep_merge(current, patch)
        self.save(updated)
        return updated

    def parse_ignore_lines(self, text: str) -> list[str]:
        numbers: list[str] = []
        seen: set[str] = set()
        for line in text.splitlines():
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            digits = normalize_phone_digits(line)
            if digits and digits not in seen:
                seen.add(digits)
                numbers.append(digits)
        return numbers

    def ignore_numbers_text(self, data: dict[str, Any] | None = None) -> str:
        payload = data if data is not None else self.load()
        wa = payload.get("whatsapp") if isinstance(payload.get("whatsapp"), dict) else {}
        numbers = wa.get("transcribe_ignore_numbers") or []
        return "\n".join(str(n) for n in numbers)

    def effective_whatsapp(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = data if data is not None else self.load()
        wa = payload.get("whatsapp") if isinstance(payload.get("whatsapp"), dict) else {}

        def _bool(key: str, default: bool) -> bool:
            val = wa.get(key)
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ("1", "true", "yes", "on")

        def _int(key: str, default: int) -> int:
            val = wa.get(key)
            if val is None:
                return default
            try:
                return int(val)
            except (TypeError, ValueError):
                return default

        def _str(key: str, default: str | None) -> str | None:
            val = wa.get(key)
            if val is None:
                return default
            text = str(val).strip()
            return text if text else default

        ignore = wa.get("transcribe_ignore_numbers") or []
        return {
            "enabled": settings.whatsapp_enabled,
            "auto_transcribe": _bool("auto_transcribe", settings.whatsapp_auto_transcribe),
            "transcribe_private_only": _bool(
                "transcribe_private_only", settings.whatsapp_transcribe_private_only
            ),
            "transcribe_only_incoming": _bool(
                "transcribe_only_incoming", settings.whatsapp_transcribe_only_incoming
            ),
            "transcribe_model": _str("transcribe_model", settings.whatsapp_transcribe_model),
            "transcribe_language": _str(
                "transcribe_language", settings.whatsapp_transcribe_language
            ),
            "transcribe_prefix": _str("transcribe_prefix", settings.whatsapp_transcribe_prefix),
            "transcribe_ignore_numbers": list(ignore),
            "max_message_chars": _int("max_message_chars", settings.whatsapp_max_message_chars),
            "max_cached_messages_per_chat": _int(
                "max_cached_messages_per_chat",
                settings.whatsapp_max_cached_messages_per_chat,
            ),
        }

    def effective_tools(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = data if data is not None else self.load()
        tools = payload.get("tools") if isinstance(payload.get("tools"), dict) else {}

        def _str(key: str, default: str | None) -> str | None:
            val = tools.get(key)
            if val is None:
                return default
            text = str(val).strip()
            return text if text else default

        return {
            "allowlist": _str("allowlist", settings.tool_allowlist),
            "denylist": _str("denylist", settings.tool_denylist),
            "confirm_required_tools": _str(
                "confirm_required_tools", settings.confirm_required_tools
            ),
        }

    def effective_logging(self, data: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = data if data is not None else self.load()
        log = payload.get("logging") if isinstance(payload.get("logging"), dict) else {}

        def _bool(key: str, default: bool) -> bool:
            val = log.get(key)
            if val is None:
                return default
            if isinstance(val, bool):
                return val
            return str(val).strip().lower() in ("1", "true", "yes", "on")

        def _str(key: str, default: str) -> str:
            val = log.get(key)
            if val is None:
                return default
            return str(val).strip() or default

        return {
            "level": _str("level", settings.log_level),
            "audit_log_enabled": _bool("audit_log_enabled", settings.audit_log_enabled),
            "audit_log_success": _bool("audit_log_success", settings.audit_log_success),
            "log_tool_success": _bool("log_tool_success", settings.log_tool_success),
        }
