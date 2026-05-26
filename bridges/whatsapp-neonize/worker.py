"""
JSON-line RPC worker for neonize (isolated venv with protobuf 7.x).

Protocol: one JSON object per line on stdin/stdout.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# libmagic (python-magic) is optional at import time on dev machines without brew install.
try:
    import magic  # noqa: F401
except ImportError:
    from unittest.mock import MagicMock

    sys.modules["magic"] = MagicMock()

from neonize.client import NewClient
from neonize.events import (
    ConnectedEv,
    DisconnectedEv,
    HistorySyncEv,
    MessageEv,
    PairStatusEv,
)
from neonize.proto.Neonize_pb2 import Message as NeonizeMessage
from neonize.utils import Jid2String, build_jid, extract_text
from neonize.utils.enum import ReceiptType


class WorkerError(Exception):
    pass


_RPC_STDOUT: Any = None


class _LibraryStdout:
    """Keep neonize/whatsmeow off the JSON-RPC pipe (real stdout saved in _RPC_STDOUT)."""

    def write(self, data: str) -> int:
        if data:
            sys.stderr.write(data)
        return len(data)

    def flush(self) -> None:
        sys.stderr.flush()

    def isatty(self) -> bool:
        return sys.stderr.isatty()


def _redirect_library_stdout() -> None:
    global _RPC_STDOUT
    _RPC_STDOUT = sys.stdout
    sys.stdout = _LibraryStdout()  # type: ignore[assignment]


def _configure_library_logging() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s.%(msecs)03d [%(name)s %(levelname)s] - %(message)s")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)


@dataclass
class ChatEntry:
    chat_id: str
    name: str
    unread_count: int = 0
    last_message_preview: str = ""
    last_timestamp: int = 0
    is_group: bool = False


@dataclass
class StoredMessage:
    message_id: str
    chat_id: str
    sender_id: str
    text: str
    timestamp: int
    from_me: bool


@dataclass
class SessionState:
    state: str = "disconnected"  # disconnected | qr | connected
    push_name: str = ""
    last_error: str = ""
    pair_status: str = ""
    qr_displayed: bool = False
    chats: dict[str, ChatEntry] = field(default_factory=dict)
    messages: dict[str, list[StoredMessage]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)


class NeonizeWorker:
    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        os.chdir(self.session_dir)
        self.client_name = os.environ.get("INTEGRATOR_WHATSAPP_CLIENT_NAME", "integrator")
        self.client = NewClient(self.client_name, uuid=self.client_name)
        self.state = SessionState()
        self._connect_thread: threading.Thread | None = None
        self._pairing = False
        self._register_handlers()

    def _register_handlers(self) -> None:
        @self.client.event(ConnectedEv)
        def on_connected(client: NewClient, _evt: ConnectedEv) -> None:
            with self.state.lock:
                self.state.state = "connected"
            try:
                me = client.get_me()
                push = getattr(me, "Pushname", None) or getattr(me, "pushname", None)
                if push:
                    with self.state.lock:
                        self.state.push_name = str(push)
            except Exception:
                pass

        @self.client.event(DisconnectedEv)
        def on_disconnected(_client: NewClient, _evt: DisconnectedEv) -> None:
            with self.state.lock:
                if self.state.state != "qr":
                    self.state.state = "disconnected"

        @self.client.event(PairStatusEv)
        def on_pair_status(_client: NewClient, evt: PairStatusEv) -> None:
            with self.state.lock:
                self.state.pair_status = str(evt.Status or "")
                if evt.Status == "success":
                    self.state.state = "connected"
                elif evt.Status in ("timeout", "error"):
                    self.state.last_error = evt.Status

        @self.client.qr
        def on_qr(_client: NewClient, qr_data: bytes) -> None:
            with self.state.lock:
                self.state.state = "qr"
                if self._pairing:
                    self.state.qr_displayed = True
            if self._pairing:
                try:
                    import segno

                    segno.make_qr(qr_data).terminal(compact=True, out=sys.stderr)
                    sys.stderr.flush()
                except Exception:
                    sys.stderr.write(
                        "[integrator] Escaneie o QR no app WhatsApp "
                        "(Dispositivos conectados).\n"
                    )
                    sys.stderr.flush()

        @self.client.event(MessageEv)
        def on_message(_client: NewClient, evt: MessageEv) -> None:
            self._ingest_neonize_message(evt)

        @self.client.event(HistorySyncEv)
        def on_history_sync(_client: NewClient, evt: HistorySyncEv) -> None:
            data = getattr(evt, "Data", None)
            if data is None:
                return
            convos = getattr(data, "conversations", None)
            if convos:
                for conv in convos:
                    self._ingest_history_conversation(conv)

    def _chat_display_name(self, chat_jid_str: str, pushname: str) -> str:
        if pushname:
            return pushname
        user = chat_jid_str.split("@", 1)[0]
        return user or chat_jid_str

    def _ingest_neonize_message(self, evt: NeonizeMessage) -> None:
        try:
            info = evt.Info
            source = info.MessageSource
            chat_id = Jid2String(source.Chat)
            sender_id = Jid2String(source.Sender)
            text = extract_text(evt.Message) or ""
            preview = text[:200]
            ts = int(info.Timestamp or time.time())
            msg = StoredMessage(
                message_id=info.ID,
                chat_id=chat_id,
                sender_id=sender_id,
                text=text,
                timestamp=ts,
                from_me=bool(source.IsFromMe),
            )
        except Exception:
            return

        with self.state.lock:
            bucket = self.state.messages.setdefault(chat_id, [])
            if not any(m.message_id == msg.message_id for m in bucket):
                bucket.append(msg)
                bucket.sort(key=lambda m: m.timestamp)
                if len(bucket) > 500:
                    self.state.messages[chat_id] = bucket[-500:]

            entry = self.state.chats.get(chat_id)
            if entry is None:
                entry = ChatEntry(
                    chat_id=chat_id,
                    name=self._chat_display_name(chat_id, info.Pushname),
                    is_group=bool(source.IsGroup),
                )
                self.state.chats[chat_id] = entry
            if ts >= entry.last_timestamp:
                entry.last_timestamp = ts
                entry.last_message_preview = preview
            if not source.IsFromMe:
                entry.unread_count += 1

    def _ingest_history_conversation(self, conv: Any) -> None:
        try:
            chat_jid = getattr(conv, "ID", None) or getattr(conv, "id", None)
            if chat_jid is None:
                return
            if hasattr(chat_jid, "User"):
                chat_id = Jid2String(chat_jid)
            else:
                chat_id = str(chat_jid)
            name = (
                getattr(conv, "Name", None)
                or getattr(conv, "displayName", None)
                or chat_id
            )
            with self.state.lock:
                entry = self.state.chats.get(chat_id)
                if entry is None:
                    self.state.chats[chat_id] = ChatEntry(
                        chat_id=chat_id,
                        name=str(name),
                        is_group="@g.us" in chat_id,
                    )
            messages = getattr(conv, "messages", None) or getattr(conv, "Messages", None)
            if messages:
                for raw in messages:
                    if hasattr(raw, "Info"):
                        self._ingest_neonize_message(raw)
        except Exception:
            return

    def _ensure_connect_thread(self) -> None:
        if self._connect_thread and self._connect_thread.is_alive():
            return

        def _run() -> None:
            try:
                self.client.connect()
            except Exception as exc:
                with self.state.lock:
                    self.state.last_error = str(exc)
                    self.state.state = "disconnected"

        self._connect_thread = threading.Thread(
            target=_run,
            name="neonize-connect",
            daemon=True,
        )
        self._connect_thread.start()

    def connect_background(self) -> dict[str, Any]:
        if not self.client.is_logged_in:
            with self.state.lock:
                self.state.state = "qr"
        self._ensure_connect_thread()
        return self.status(live=True, wait_s=20.0)

    def _wait_session_ready(self, timeout_s: float) -> None:
        """Aguarda login + socket após pair (ex.: código 515 e reconnect do whatsmeow)."""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if self.client.is_logged_in and self.client.is_connected:
                with self.state.lock:
                    self.state.state = "connected"
                return
            time.sleep(0.25)

    def _pairing_outcome(self) -> str:
        """linked = QR/PairStatusEv nesta execução; restored = só credencial em disco."""
        with self.state.lock:
            if self.state.pair_status == "success" or self.state.qr_displayed:
                return "linked"
        return "restored"

    def pair(self, timeout_s: float = 120.0) -> dict[str, Any]:
        self._pairing = True
        try:
            with self.state.lock:
                self.state.state = "qr"
                self.state.pair_status = ""
                self.state.qr_displayed = False
            thread = threading.Thread(target=self.client.connect, daemon=True)
            thread.start()
            deadline = time.time() + timeout_s
            while time.time() < deadline:
                if self.client.is_logged_in:
                    self._wait_session_ready(min(45.0, timeout_s * 0.4))
                    result = self.status(live=True, wait_s=5.0)
                    result["pairing_outcome"] = self._pairing_outcome()
                    return result
                time.sleep(0.5)
            raise WorkerError(
                "Tempo esgotado aguardando pareamento. Escaneie o QR e tente novamente."
            )
        finally:
            self._pairing = False

    def status(self, *, live: bool = False, wait_s: float = 20.0) -> dict[str, Any]:
        if live:
            self._ensure_connect_thread()
            self._wait_session_ready(wait_s)
        logged_in = self.client.is_logged_in
        connected = self.client.is_connected
        with self.state.lock:
            state = self.state.state
            if logged_in:
                state = "connected"
            elif state != "qr":
                state = "disconnected" if not connected else state
            return {
                "state": state,
                "logged_in": logged_in,
                "connected": connected,
                "push_name": self.state.push_name,
                "error": self.state.last_error or None,
                "session_dir": str(self.session_dir),
            }

    def list_chats(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self.state.lock:
            items = sorted(
                self.state.chats.values(),
                key=lambda c: c.last_timestamp,
                reverse=True,
            )[:limit]
            return [
                {
                    "chat_id": c.chat_id,
                    "name": c.name,
                    "unread_count": c.unread_count,
                    "last_message_preview": c.last_message_preview,
                    "last_timestamp": c.last_timestamp,
                    "is_group": c.is_group,
                }
                for c in items
            ]

    def find_chats(self, *, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = query.strip().lower()
        if not q:
            return []
        with self.state.lock:
            matches = []
            for c in self.state.chats.values():
                hay = f"{c.name} {c.chat_id}".lower()
                if q in hay:
                    matches.append(c)
            matches.sort(key=lambda c: c.last_timestamp, reverse=True)
            return [
                {
                    "chat_id": c.chat_id,
                    "name": c.name,
                    "unread_count": c.unread_count,
                    "last_message_preview": c.last_message_preview,
                    "is_group": c.is_group,
                }
                for c in matches[:limit]
            ]

    def get_messages(
        self,
        *,
        chat_id: str,
        limit: int = 30,
        max_chars: int = 800,
    ) -> list[dict[str, Any]]:
        with self.state.lock:
            bucket = list(self.state.messages.get(chat_id, []))
        bucket.sort(key=lambda m: m.timestamp, reverse=True)
        out: list[dict[str, Any]] = []
        for m in bucket[:limit]:
            text = m.text
            if len(text) > max_chars:
                text = text[: max_chars - 3] + "..."
            out.append(
                {
                    "message_id": m.message_id,
                    "chat_id": m.chat_id,
                    "sender_id": m.sender_id,
                    "text": text,
                    "timestamp": m.timestamp,
                    "from_me": m.from_me,
                }
            )
        return out

    @staticmethod
    def _jid_from_chat_id(chat_id: str) -> Any:
        from neonize.proto.Neonize_pb2 import JID

        if "@" in chat_id:
            user, server = chat_id.split("@", 1)
        else:
            user, server = chat_id, "s.whatsapp.net"
        return JID(
            User=user,
            Server=server,
            Device=0,
            RawAgent=0,
            Integrator=0,
            IsEmpty=False,
        )

    def send_text(
        self,
        *,
        text: str,
        chat_id: str | None = None,
        number: str | None = None,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado. Rode pareamento antes.")
        if chat_id:
            jid = self._jid_from_chat_id(chat_id)
        elif number:
            digits = "".join(ch for ch in number if ch.isdigit())
            jid = build_jid(digits)
        else:
            raise WorkerError("Informe chat_id ou number.")

        resp = self.client.send_message(jid, text)
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
        }

    def mark_read(self, *, chat_id: str, message_ids: list[str] | None = None) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        from neonize.proto.Neonize_pb2 import JID

        parts = chat_id.split("@", 1)
        chat_jid = JID(
            User=parts[0],
            Server=parts[1] if len(parts) > 1 else "s.whatsapp.net",
            Device=0,
            RawAgent=0,
            Integrator=0,
            IsEmpty=False,
        )
        me = self.client.get_me()
        sender = me.JID if me and me.JID else chat_jid
        ids = message_ids or []
        if not ids:
            with self.state.lock:
                bucket = self.state.messages.get(chat_id, [])
                ids = [m.message_id for m in bucket[-5:] if not m.from_me]
        if not ids:
            return {"marked": 0}
        self.client.mark_read(*ids, chat=chat_jid, sender=sender, receipt=ReceiptType.READ)
        with self.state.lock:
            entry = self.state.chats.get(chat_id)
            if entry:
                entry.unread_count = 0
        return {"marked": len(ids)}

    def handle(self, method: str, params: dict[str, Any]) -> Any:
        if method == "ping":
            return {"pong": True}
        if method == "status":
            return self.status(
                live=bool(params.get("live")),
                wait_s=float(params.get("wait_s", 20)),
            )
        if method == "connect":
            return self.connect_background()
        if method == "pair":
            return self.pair(timeout_s=float(params.get("timeout_s", 120)))
        if method == "list_chats":
            return self.list_chats(limit=int(params.get("limit", 30)))
        if method == "find_chats":
            return self.find_chats(
                query=str(params.get("query", "")),
                limit=int(params.get("limit", 20)),
            )
        if method == "get_messages":
            return self.get_messages(
                chat_id=str(params["chat_id"]),
                limit=int(params.get("limit", 30)),
                max_chars=int(params.get("max_chars", 800)),
            )
        if method == "send_text":
            return self.send_text(
                text=str(params["text"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
            )
        if method == "mark_read":
            return self.mark_read(
                chat_id=str(params["chat_id"]),
                message_ids=params.get("message_ids"),
            )
        if method == "shutdown":
            return self.shutdown()
        raise WorkerError(f"Método desconhecido: {method}")

    def shutdown(self) -> dict[str, Any]:
        try:
            if self.client.is_connected:
                self.client.disconnect()
        except Exception:
            pass
        with self.state.lock:
            self.state.state = "disconnected"
        return {"shutdown": True}


def _read_request(line: str) -> dict[str, Any]:
    data = json.loads(line)
    if not isinstance(data, dict):
        raise WorkerError("Pedido JSON inválido")
    return data


def _write_response(obj: dict[str, Any]) -> None:
    if _RPC_STDOUT is None:
        raise WorkerError("RPC stdout não inicializado")
    _RPC_STDOUT.write(json.dumps(obj, ensure_ascii=False) + "\n")
    _RPC_STDOUT.flush()


def main() -> None:
    _redirect_library_stdout()
    _configure_library_logging()
    session_dir = Path(os.environ.get("INTEGRATOR_WHATSAPP_SESSION_DIR", "data/whatsapp"))
    worker = NeonizeWorker(session_dir.resolve())
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req_id = None
        try:
            req = _read_request(line)
            req_id = req.get("id")
            method = str(req.get("method", ""))
            params = req.get("params") or {}
            if not isinstance(params, dict):
                raise WorkerError("params deve ser objeto")
            result = worker.handle(method, params)
            _write_response({"id": req_id, "ok": True, "result": result})
        except WorkerError as exc:
            _write_response({"id": req_id, "ok": False, "error": str(exc)})
        except Exception as exc:
            _write_response(
                {
                    "id": req_id,
                    "ok": False,
                    "error": f"[integrator] {exc}",
                }
            )


if __name__ == "__main__":
    main()
