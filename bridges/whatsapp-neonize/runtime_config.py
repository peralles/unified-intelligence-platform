"""Hot-reload runtime config (shared file with integrator admin UI)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


def default_runtime_path() -> Path:
    explicit = os.environ.get("INTEGRATOR_ADMIN_RUNTIME_FILE", "").strip()
    if explicit:
        return Path(explicit).expanduser()
    session = os.environ.get("INTEGRATOR_WHATSAPP_SESSION_DIR", "").strip()
    if session:
        return Path(session).resolve().parent / "admin" / "runtime.json"
    return Path("data/admin/runtime.json")


def normalize_phone_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _split_jid(chat_id: str) -> tuple[str, str]:
    if "@" in chat_id:
        user, server = chat_id.rsplit("@", 1)
        return user, server
    return chat_id, "s.whatsapp.net"


class RuntimeConfig:
    """Reads data/admin/runtime.json; reloads when mtime changes."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_runtime_path()
        self._mtime: float = 0.0
        self._data: dict[str, Any] = {}
        self._ignore_set: set[str] = set()
        self.reload(force=True)

    def reload(self, *, force: bool = False) -> None:
        path = self.path
        if not path.is_file():
            self._data = {}
            self._ignore_set = set()
            self._mtime = 0.0
            return
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return
        if not force and mtime == self._mtime:
            return
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(raw, dict):
            return
        self._data = raw
        self._mtime = mtime
        wa = raw.get("whatsapp") if isinstance(raw.get("whatsapp"), dict) else {}
        numbers = wa.get("transcribe_ignore_numbers") or []
        self._ignore_set = {
            normalize_phone_digits(str(n))
            for n in numbers
            if normalize_phone_digits(str(n))
        }

    def whatsapp_section(self) -> dict[str, Any]:
        self.reload()
        section = self._data.get("whatsapp")
        return dict(section) if isinstance(section, dict) else {}

    def ignore_numbers(self) -> set[str]:
        self.reload()
        return set(self._ignore_set)

    def bool_override(self, key: str, default: bool) -> bool:
        value = self.whatsapp_section().get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")

    def str_override(self, key: str, default: str | None) -> str | None:
        value = self.whatsapp_section().get(key)
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    def is_chat_ignored(
        self,
        chat_id: str,
        sender_id: str,
        *,
        extra_digits: str | None = None,
    ) -> bool:
        self.reload()
        if not self._ignore_set:
            return False
        candidates: set[str] = set()
        for jid in (chat_id, sender_id):
            user, server = _split_jid(jid)
            if user:
                candidates.add(normalize_phone_digits(user))
            if server == "s.whatsapp.net" and user.isdigit():
                candidates.add(normalize_phone_digits(user))
        if extra_digits:
            candidates.add(normalize_phone_digits(extra_digits))
        candidates.discard("")
        for cand in candidates:
            if cand in self._ignore_set:
                return True
            for ign in self._ignore_set:
                if len(cand) >= 8 and len(ign) >= 8 and (
                    cand.endswith(ign) or ign.endswith(cand)
                ):
                    return True
        return False
