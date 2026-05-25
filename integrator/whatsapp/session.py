from __future__ import annotations

import atexit
from pathlib import Path
from typing import Any

from integrator.config import settings
from integrator.whatsapp.bridge_client import WhatsAppBridgeClient, resolve_session_dir
from integrator.whatsapp.logging_whatsapp import LOGGER


class WhatsAppSession:
    """Singleton bridge client for MCP serve lifetime."""

    _instance: WhatsAppSession | None = None

    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self._bridge = WhatsAppBridgeClient(session_dir)
        self._started = False

    @classmethod
    def get(cls) -> WhatsAppSession:
        if cls._instance is None:
            cls._instance = WhatsAppSession(resolve_session_dir())
            atexit.register(cls._instance.shutdown)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance is not None:
            cls._instance.shutdown()
        cls._instance = None

    def ensure_background_connection(self) -> None:
        if not settings.whatsapp_enabled:
            return
        if self._started and self._bridge.is_worker_alive():
            return
        self._started = False
        LOGGER.debug("session connect_background")
        self._bridge.call("connect")
        self._started = True

    def status(self) -> dict[str, Any]:
        """Estado em tempo real (sobe connect no worker se ainda não iniciou)."""
        self.ensure_background_connection()
        return self._bridge.call("status", {"live": True, "wait_s": 25})

    def pair(self, *, timeout_s: float = 120.0) -> dict[str, Any]:
        return self._bridge.call("pair", {"timeout_s": timeout_s})

    def list_chats(self, *, limit: int = 30) -> list[dict[str, Any]]:
        self.ensure_background_connection()
        result = self._bridge.call("list_chats", {"limit": limit})
        return list(result or [])

    def find_chats(self, *, query: str, limit: int = 20) -> list[dict[str, Any]]:
        self.ensure_background_connection()
        result = self._bridge.call(
            "find_chats",
            {"query": query, "limit": limit},
        )
        return list(result or [])

    def get_messages(
        self,
        *,
        chat_id: str,
        limit: int = 30,
        max_chars: int | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_background_connection()
        max_c = max_chars if max_chars is not None else settings.whatsapp_max_message_chars
        result = self._bridge.call(
            "get_messages",
            {"chat_id": chat_id, "limit": limit, "max_chars": max_c},
        )
        return list(result or [])

    def send_text(
        self,
        *,
        text: str,
        chat_id: str | None = None,
        number: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_text",
            {"text": text, "chat_id": chat_id, "number": number},
        )

    def mark_read(
        self,
        *,
        chat_id: str,
        message_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "mark_read",
            {"chat_id": chat_id, "message_ids": message_ids},
        )

    def shutdown(self) -> None:
        if self._started:
            try:
                self._bridge.call("shutdown")
            except Exception as exc:
                LOGGER.debug("session shutdown worker: %s", exc)
        self._bridge.close()
        self._started = False
