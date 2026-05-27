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
        before_timestamp: int | None = None,
        after_timestamp: int | None = None,
        from_me: bool | None = None,
    ) -> list[dict[str, Any]]:
        self.ensure_background_connection()
        max_c = max_chars if max_chars is not None else settings.whatsapp_max_message_chars
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "limit": limit,
            "max_chars": max_c,
        }
        if before_timestamp is not None:
            payload["before_timestamp"] = before_timestamp
        if after_timestamp is not None:
            payload["after_timestamp"] = after_timestamp
        if from_me is not None:
            payload["from_me"] = from_me
        result = self._bridge.call("get_messages", payload)
        return list(result or [])

    def request_chat_history(
        self,
        *,
        chat_id: str,
        count: int = 50,
        wait_s: float = 25.0,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "request_chat_history",
            {"chat_id": chat_id, "count": count, "wait_s": wait_s},
        )

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

    def reply_text(
        self,
        *,
        chat_id: str,
        reply_to_message_id: str,
        text: str,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "reply_text",
            {
                "chat_id": chat_id,
                "reply_to_message_id": reply_to_message_id,
                "text": text,
            },
        )

    def send_image(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_image",
            {
                "file_path": file_path,
                "chat_id": chat_id,
                "number": number,
                "caption": caption,
            },
        )

    def send_document(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
        caption: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_document",
            {
                "file_path": file_path,
                "chat_id": chat_id,
                "number": number,
                "caption": caption,
                "filename": filename,
            },
        )

    def send_audio(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
        voice_note: bool = False,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_audio",
            {
                "file_path": file_path,
                "chat_id": chat_id,
                "number": number,
                "voice_note": voice_note,
            },
        )

    def forward_message(
        self,
        *,
        source_chat_id: str,
        message_id: str,
        target_chat_id: str | None = None,
        target_number: str | None = None,
        include_prefix: bool = True,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "forward_message",
            {
                "source_chat_id": source_chat_id,
                "message_id": message_id,
                "target_chat_id": target_chat_id,
                "target_number": target_number,
                "include_prefix": include_prefix,
            },
        )

    def set_chat_muted(
        self,
        *,
        chat_id: str,
        mute_hours: int | None = 8,
        unmute: bool = False,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        payload: dict[str, Any] = {"chat_id": chat_id, "unmute": unmute}
        if mute_hours is not None:
            payload["mute_hours"] = mute_hours
        return self._bridge.call("set_chat_muted", payload)

    def send_video(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
        caption: str | None = None,
        view_once: bool = False,
        gif_playback: bool = False,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_video",
            {
                "file_path": file_path,
                "chat_id": chat_id,
                "number": number,
                "caption": caption,
                "view_once": view_once,
                "gif_playback": gif_playback,
            },
        )

    def send_sticker(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_sticker",
            {
                "file_path": file_path,
                "chat_id": chat_id,
                "number": number,
            },
        )

    def send_contact(
        self,
        *,
        contact_name: str,
        contact_number: str,
        chat_id: str | None = None,
        number: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_contact",
            {
                "contact_name": contact_name,
                "contact_number": contact_number,
                "chat_id": chat_id,
                "number": number,
            },
        )

    def list_joined_groups(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.ensure_background_connection()
        result = self._bridge.call("list_joined_groups", {"limit": limit})
        return list(result or [])

    def get_profile_picture(self, *, chat_id: str) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call("get_profile_picture", {"chat_id": chat_id})

    def send_chat_presence(
        self,
        *,
        chat_id: str,
        composing: bool = True,
        media: str = "text",
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_chat_presence",
            {"chat_id": chat_id, "composing": composing, "media": media},
        )

    def send_poll(
        self,
        *,
        question: str,
        options: list[str],
        chat_id: str | None = None,
        number: str | None = None,
        allow_multiple: bool = False,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_poll",
            {
                "question": question,
                "options": options,
                "chat_id": chat_id,
                "number": number,
                "allow_multiple": allow_multiple,
            },
        )

    def send_album(
        self,
        *,
        file_paths: list[str],
        chat_id: str | None = None,
        number: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "send_album",
            {
                "file_paths": file_paths,
                "chat_id": chat_id,
                "number": number,
                "caption": caption,
            },
        )

    def get_blocklist(self) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call("get_blocklist", {})

    def update_blocklist(
        self,
        *,
        chat_id: str | None = None,
        number: str | None = None,
        block: bool = True,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "update_blocklist",
            {"chat_id": chat_id, "number": number, "block": block},
        )

    def get_group_invite_link(
        self,
        *,
        chat_id: str,
        revoke: bool = False,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "get_group_invite_link",
            {"chat_id": chat_id, "revoke": revoke},
        )

    def leave_group(self, *, chat_id: str) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call("leave_group", {"chat_id": chat_id})

    def join_group_link(self, *, invite_link: str) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call("join_group_link", {"invite_link": invite_link})

    def vote_poll(
        self,
        *,
        chat_id: str,
        poll_message_id: str,
        selected_options: list[str],
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "vote_poll",
            {
                "chat_id": chat_id,
                "poll_message_id": poll_message_id,
                "selected_options": selected_options,
            },
        )

    def get_user_info(
        self,
        *,
        chat_ids: list[str] | None = None,
        chat_id: str | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        payload: dict[str, Any] = {}
        if chat_ids is not None:
            payload["chat_ids"] = chat_ids
        if chat_id is not None:
            payload["chat_id"] = chat_id
        return self._bridge.call("get_user_info", payload)

    def search_messages(
        self,
        *,
        query: str,
        chat_id: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        self.ensure_background_connection()
        result = self._bridge.call(
            "search_messages",
            {"query": query, "chat_id": chat_id, "limit": limit},
        )
        return list(result or [])

    def get_group_info(self, *, chat_id: str) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call("get_group_info", {"chat_id": chat_id})

    def edit_text(
        self,
        *,
        chat_id: str,
        message_id: str,
        text: str,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "edit_text",
            {"chat_id": chat_id, "message_id": message_id, "text": text},
        )

    def set_chat_archived(self, *, chat_id: str, archived: bool) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "set_chat_archived",
            {"chat_id": chat_id, "archived": archived},
        )

    def set_chat_pinned(self, *, chat_id: str, pinned: bool) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "set_chat_pinned",
            {"chat_id": chat_id, "pinned": pinned},
        )

    def react_message(
        self,
        *,
        chat_id: str,
        message_id: str,
        emoji: str,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "react_message",
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "emoji": emoji,
            },
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

    def delete_messages(
        self,
        *,
        chat_id: str,
        message_ids: list[str],
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        return self._bridge.call(
            "delete_messages",
            {"chat_id": chat_id, "message_ids": message_ids},
        )

    def delete_messages_for_me(
        self,
        *,
        chat_id: str,
        message_ids: list[str] | None = None,
        before_timestamp: int | None = None,
        after_timestamp: int | None = None,
        from_me: bool | None = None,
        delete_media: bool = False,
        entries: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.ensure_background_connection()
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "delete_media": delete_media,
        }
        if message_ids is not None:
            payload["message_ids"] = message_ids
        if before_timestamp is not None:
            payload["before_timestamp"] = before_timestamp
        if after_timestamp is not None:
            payload["after_timestamp"] = after_timestamp
        if from_me is not None:
            payload["from_me"] = from_me
        if entries is not None:
            payload["entries"] = entries
        return self._bridge.call("delete_messages_for_me", payload)

    def shutdown(self) -> None:
        if self._started:
            try:
                self._bridge.call("shutdown")
            except Exception as exc:
                LOGGER.debug("session shutdown worker: %s", exc)
        self._bridge.close()
        self._started = False
