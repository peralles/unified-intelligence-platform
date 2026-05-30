"""
JSON-line RPC worker for neonize (isolated venv with protobuf 7.x).

Protocol: one JSON object per line on stdin/stdout.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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

from runtime_config import RuntimeConfig


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


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes")


def _is_group_chat_id(chat_id: str) -> bool:
    """WhatsApp group JIDs contain @g.us (private chats use @s.whatsapp.net)."""
    return "@g.us" in chat_id


def _wa_message_is_audio(wa_msg: Any) -> bool:
    """Voice/audio detection for MessageEv (URL is often empty until download)."""
    if wa_msg is None:
        return False
    try:
        if wa_msg.HasField("audioMessage"):
            return True
    except (AttributeError, ValueError):
        pass
    doc = getattr(wa_msg, "documentMessage", None)
    if doc and str(getattr(doc, "mimetype", "")).startswith("audio/"):
        return True
    return False


def _split_chat_jid(chat_id: str) -> tuple[str, str]:
    if "@" in chat_id:
        user, server = chat_id.rsplit("@", 1)
        return user, server
    return chat_id, "s.whatsapp.net"


def _looks_like_opaque_id(name: str, chat_id: str) -> bool:
    user, _ = _split_chat_jid(chat_id)
    label = name.strip()
    if not label:
        return True
    if label == user:
        return True
    return label.isdigit() and len(label) >= 10


def _format_phone_digits(digits: str) -> str:
    cleaned = "".join(ch for ch in digits if ch.isdigit())
    if not cleaned:
        return ""
    try:
        import phonenumbers

        parsed = phonenumbers.parse(f"+{cleaned}", None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(
                parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL
            )
    except Exception:
        pass
    return f"+{cleaned}"


def _phone_from_chat_id(chat_id: str) -> str | None:
    user, server = _split_chat_jid(chat_id)
    if server == "s.whatsapp.net" and user.isdigit():
        return _format_phone_digits(user)
    return None


@dataclass
class ChatEntry:
    chat_id: str
    name: str
    unread_count: int = 0
    last_message_preview: str = ""
    last_timestamp: int = 0
    is_group: bool = False


def _build_display_name(entry: ChatEntry, *, phone: str | None) -> str:
    name = (entry.name or "").strip()
    if entry.is_group:
        return name or "Grupo sem nome"
    if phone:
        if name and not _looks_like_opaque_id(name, entry.chat_id):
            return f"{name} ({phone})"
        return phone
    if name and not _looks_like_opaque_id(name, entry.chat_id):
        return name
    if entry.chat_id.endswith("@lid"):
        return "Contato privado (número oculto pelo WhatsApp)"
    user, _ = _split_chat_jid(entry.chat_id)
    return user or entry.chat_id


@dataclass
class StoredMessage:
    message_id: str
    chat_id: str
    sender_id: str
    text: str
    timestamp: int
    from_me: bool
    raw_proto_b64: str = ""
    is_audio: bool = False


class AudioTranscriber:
    """Local Whisper transcription via mlx-whisper (Apple Silicon)."""

    def __init__(self, model_id: str, language: str | None = None) -> None:
        self.model_id = model_id
        self.language = language or None
        self._ready = False
        self._error: str | None = None

    def _ensure_ready(self) -> None:
        if self._ready:
            return
        try:
            import mlx_whisper  # noqa: F401
            self._ready = True
        except ImportError as exc:
            self._error = (
                f"mlx-whisper não instalado no venv do bridge. "
                f"Execute: cd bridges/whatsapp-neonize && uv add mlx-whisper  ({exc})"
            )
            raise RuntimeError(self._error) from exc

    def transcribe(self, audio_path: str) -> str:
        self._ensure_ready()
        import mlx_whisper

        result = mlx_whisper.transcribe(
            audio_path,
            path_or_hf_repo=self.model_id,
            language=self.language,
            verbose=False,
            fp16=True,
        )
        return (result.get("text") or "").strip()


@dataclass
class SessionState:
    state: str = "disconnected"  # disconnected | qr | connected
    push_name: str = ""
    last_error: str = ""
    pair_status: str = ""
    qr_displayed: bool = False
    qr_png_base64: str = ""
    qr_updated_at: float = 0.0
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
        self._cache_store: Any = None
        if os.environ.get("INTEGRATOR_WHATSAPP_PERSIST_CACHE", "true").lower() in (
            "1",
            "true",
            "yes",
        ):
            from cache_store import MessageCacheStore

            self._cache_store = MessageCacheStore(session_dir / "message_cache.db")
            self._hydrate_cache_from_store()

        # Auto-transcription config (from env — set before process start)
        self._auto_transcribe: bool = os.environ.get(
            "INTEGRATOR_WHATSAPP_AUTO_TRANSCRIBE", ""
        ).lower() in ("1", "true", "yes")
        self._transcribe_model: str = os.environ.get(
            "INTEGRATOR_WHATSAPP_TRANSCRIBE_MODEL",
            "mlx-community/whisper-large-v3-turbo",
        )
        self._transcribe_language: str | None = (
            os.environ.get("INTEGRATOR_WHATSAPP_TRANSCRIBE_LANGUAGE") or None
        )
        self._transcribe_prefix: str = os.environ.get(
            "INTEGRATOR_WHATSAPP_TRANSCRIBE_PREFIX", "🎙️ "
        )
        self._transcribe_only_incoming: bool = _env_bool(
            "INTEGRATOR_WHATSAPP_TRANSCRIBE_ONLY_INCOMING",
            default=False,
        )
        self._transcribe_private_only: bool = _env_bool(
            "INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY",
            default=True,
        )
        self._runtime = RuntimeConfig()
        self._transcriber: AudioTranscriber | None = None
        self._transcribe_pool: ThreadPoolExecutor | None = None
        if self._auto_transcribe:
            self._transcriber = AudioTranscriber(
                self._transcribe_model, self._transcribe_language
            )
            self._transcribe_pool = ThreadPoolExecutor(
                max_workers=2, thread_name_prefix="wa-transcribe"
            )

        self._register_handlers()

    def _effective_auto_transcribe(self) -> bool:
        return self._runtime.bool_override("auto_transcribe", self._auto_transcribe)

    def _effective_only_incoming(self) -> bool:
        return self._runtime.bool_override(
            "transcribe_only_incoming", self._transcribe_only_incoming
        )

    def _effective_private_only(self) -> bool:
        return self._runtime.bool_override(
            "transcribe_private_only", self._transcribe_private_only
        )

    def _effective_transcribe_prefix(self) -> str:
        return (
            self._runtime.str_override("transcribe_prefix", self._transcribe_prefix)
            or self._transcribe_prefix
        )

    def _ensure_transcribe_pool(self) -> None:
        if not self._effective_auto_transcribe():
            return
        if self._transcribe_pool is not None:
            return
        self._transcriber = AudioTranscriber(
            self._transcribe_model, self._transcribe_language
        )
        self._transcribe_pool = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="wa-transcribe"
        )

    def _transcribe_is_ignored(self, chat_id: str, sender_id: str) -> bool:
        extra: str | None = None
        for jid in (chat_id, sender_id):
            if jid.endswith("@lid"):
                phone = self._resolve_lid_phone(jid)
                if phone:
                    extra = phone
                    break
        if self._runtime.is_chat_ignored(chat_id, sender_id, extra_digits=extra):
            logging.debug("[transcribe] skip ignored number | chat=%s", chat_id)
            return True
        return False

    def _max_cached_per_chat(self) -> int:
        return int(os.environ.get("INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT", "5000"))

    def _hydrate_cache_from_store(self) -> None:
        if self._cache_store is None:
            return
        max_c = self._max_cached_per_chat()
        buckets = self._cache_store.load_into_buckets(max_per_chat=max_c)
        with self.state.lock:
            for chat_id, rows in buckets.items():
                bucket = self.state.messages.setdefault(chat_id, [])
                known = {m.message_id for m in bucket}
                for row in rows:
                    if row.message_id in known:
                        continue
                    bucket.append(
                        StoredMessage(
                            message_id=row.message_id,
                            chat_id=row.chat_id,
                            sender_id=row.sender_id,
                            text=row.text,
                            timestamp=row.timestamp,
                            from_me=row.from_me,
                            raw_proto_b64=row.raw_proto_b64,
                            is_audio=row.is_audio,
                        )
                    )
                bucket.sort(key=lambda m: m.timestamp)
                if len(bucket) > max_c:
                    self.state.messages[chat_id] = bucket[-max_c:]

    def _persist_cached_message(self, msg: StoredMessage) -> None:
        if self._cache_store is None:
            return
        try:
            self._cache_store.upsert(msg)
            self._cache_store.prune_chat(msg.chat_id, keep=self._max_cached_per_chat())
        except Exception as exc:
            logging.getLogger("whatsapp.cache").warning("cache persist failed: %s", exc)

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
            png_b64 = ""
            try:
                import base64
                import io

                import segno

                buf = io.BytesIO()
                segno.make_qr(qr_data).save(buf, kind="png", scale=8, border=2)
                png_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            except Exception:
                png_b64 = ""
            with self.state.lock:
                if png_b64:
                    self.state.qr_png_base64 = png_b64
                    self.state.qr_updated_at = time.time()
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
        user, _ = _split_chat_jid(chat_jid_str)
        return user or chat_jid_str

    def _resolve_lid_phone(self, chat_id: str) -> str | None:
        _, server = _split_chat_jid(chat_id)
        if server != "lid" or not self.client.is_logged_in:
            return None
        try:
            pn_jid = self.client.get_pn_from_lid(self._jid_from_chat_id(chat_id))
            return _phone_from_chat_id(Jid2String(pn_jid))
        except Exception:
            return None

    def _chat_phone(self, entry: ChatEntry) -> str | None:
        phone = _phone_from_chat_id(entry.chat_id)
        if phone is not None:
            return phone
        if entry.chat_id.endswith("@lid") and (
            _looks_like_opaque_id(entry.name, entry.chat_id) or not entry.name.strip()
        ):
            return self._resolve_lid_phone(entry.chat_id)
        return None

    def _chat_to_dict(self, entry: ChatEntry) -> dict[str, Any]:
        phone = self._chat_phone(entry)
        return {
            "chat_id": entry.chat_id,
            "name": entry.name,
            "display_name": _build_display_name(entry, phone=phone),
            "phone": phone,
            "unread_count": entry.unread_count,
            "last_message_preview": entry.last_message_preview,
            "last_timestamp": entry.last_timestamp,
            "is_group": entry.is_group,
        }

    def _chat_display_for_id(self, chat_id: str) -> str:
        with self.state.lock:
            entry = self.state.chats.get(chat_id)
        if entry is None:
            phone = _phone_from_chat_id(chat_id)
            if phone:
                return phone
            if chat_id.endswith("@lid"):
                phone = self._resolve_lid_phone(chat_id)
                if phone:
                    return phone
                return "Contato privado (número oculto pelo WhatsApp)"
            user, _ = _split_chat_jid(chat_id)
            return user or chat_id
        return self._chat_to_dict(entry)["display_name"]

    def _ingest_neonize_message(self, evt: NeonizeMessage) -> None:
        try:
            info = evt.Info
            source = info.MessageSource
            chat_id = Jid2String(source.Chat)
            sender_id = Jid2String(source.Sender)
            text = extract_text(evt.Message) or ""
            preview = text[:200]
            ts = int(info.Timestamp or time.time())
            raw_b64 = base64.b64encode(evt.SerializeToString()).decode("ascii")
            wa_msg = evt.Message
            is_audio = _wa_message_is_audio(wa_msg)
            msg = StoredMessage(
                message_id=info.ID,
                chat_id=chat_id,
                sender_id=sender_id,
                text=text,
                timestamp=ts,
                from_me=bool(source.IsFromMe),
                raw_proto_b64=raw_b64,
                is_audio=is_audio,
            )
        except Exception:
            return

        with self.state.lock:
            bucket = self.state.messages.setdefault(chat_id, [])
            if not any(m.message_id == msg.message_id for m in bucket):
                bucket.append(msg)
                bucket.sort(key=lambda m: m.timestamp)
                max_cached = int(
                    os.environ.get("INTEGRATOR_WHATSAPP_MAX_CACHED_MESSAGES_PER_CHAT", "5000")
                )
                max_cached = self._max_cached_per_chat()
                if len(bucket) > max_cached:
                    self.state.messages[chat_id] = bucket[-max_cached:]
            self._persist_cached_message(msg)

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

        # Auto-transcribe audio (private chats by default; sent + received unless ONLY_INCOMING)
        is_group = bool(source.IsGroup) or _is_group_chat_id(chat_id)
        self._ensure_transcribe_pool()
        if (
            self._effective_auto_transcribe()
            and msg.is_audio
            and self._transcribe_pool is not None
            and not (self._effective_only_incoming() and msg.from_me)
            and not (self._effective_private_only() and is_group)
            and not self._transcribe_is_ignored(chat_id, sender_id)
        ):
            self._transcribe_pool.submit(
                self._do_transcribe_and_reply, evt, self.client
            )

    def _do_transcribe_and_reply(self, evt: NeonizeMessage, client: Any) -> None:
        """Download audio, transcribe with mlx-whisper, reply in the same chat."""
        if self._transcriber is None:
            return
        info = evt.Info
        source = info.MessageSource
        chat_id = Jid2String(source.Chat)
        sender_id = Jid2String(source.Sender)
        if self._transcribe_is_ignored(chat_id, sender_id):
            return
        if self._effective_private_only() and (
            bool(source.IsGroup) or _is_group_chat_id(chat_id)
        ):
            logging.debug("[transcribe] skip group chat | chat=%s", chat_id)
            return
        tmp_path: str | None = None
        try:
            audio_bytes: bytes = client.download_any(evt.Message)
        except Exception as exc:
            logging.error("[transcribe] download failed | chat=%s | %s", chat_id, exc)
            return
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as fh:
                fh.write(audio_bytes)
                tmp_path = fh.name
            text = self._transcriber.transcribe(tmp_path)
        except Exception as exc:
            logging.error("[transcribe] transcription failed | chat=%s | %s", chat_id, exc)
            return
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        if not text:
            return
        reply = f"{self._effective_transcribe_prefix()}{text}"
        try:
            chat_jid = self._jid_from_chat_id(chat_id)
            client.send_message(chat_jid, reply)
            logging.info("[transcribe] OK | chat=%s | chars=%d", chat_id, len(text))
        except Exception as exc:
            logging.error("[transcribe] send reply failed | chat=%s | %s", chat_id, exc)

    def _transcribe_stored_audio(self, *, chat_id: str, message_id: str) -> str:
        """On-demand transcription for a cached audio message (RPC call)."""
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        if self._transcribe_private_only and _is_group_chat_id(chat_id):
            raise WorkerError(
                "Transcrição desabilitada para grupos (@g.us). "
                "Use chat privado ou defina INTEGRATOR_WHATSAPP_TRANSCRIBE_PRIVATE_ONLY=false."
            )
        stored = self._lookup_stored_message(chat_id, message_id)
        if not stored.raw_proto_b64:
            raise WorkerError(
                f"Mensagem {message_id} não tem metadados para download. "
                "Receba o áudio novamente ou sincronize o histórico do chat."
            )
        neonize_msg = self._load_quoted_neonize_message(stored)
        if not (stored.is_audio or _wa_message_is_audio(neonize_msg.Message)):
            raise WorkerError(
                f"Mensagem {message_id} não é um áudio. "
                "Use transcribe_whatsapp_audio apenas em mensagens de voz/áudio."
            )
        transcriber = AudioTranscriber(self._transcribe_model, self._transcribe_language)
        tmp_path: str | None = None
        try:
            audio_bytes: bytes = self.client.download_any(neonize_msg.Message)
        except Exception as exc:
            raise WorkerError(f"Falha ao baixar áudio: {exc}") from exc
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as fh:
                fh.write(audio_bytes)
                tmp_path = fh.name
            text = transcriber.transcribe(tmp_path)
        except RuntimeError:
            raise
        except Exception as exc:
            raise WorkerError(f"Falha na transcrição: {exc}") from exc
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        return text

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

    def _reset_pair_state(self) -> None:
        with self.state.lock:
            self.state.state = "qr"
            self.state.pair_status = ""
            self.state.qr_displayed = False
            self.state.qr_png_base64 = ""
            self.state.qr_updated_at = 0.0

    def pair_start(self) -> dict[str, Any]:
        """Non-blocking pair: start connect thread; poll with pair_poll."""
        if not self._pairing:
            self._pairing = True
            self._reset_pair_state()
            thread = threading.Thread(target=self.client.connect, daemon=True)
            thread.start()
        return self.pair_poll()

    def pair_poll(self) -> dict[str, Any]:
        if self.client.is_logged_in:
            self._wait_session_ready(5.0)
            result = self.status(live=True, wait_s=3.0)
            result["pairing_outcome"] = self._pairing_outcome()
            result["pairing"] = False
            with self.state.lock:
                result["qr_png_base64"] = self.state.qr_png_base64 or None
            self._pairing = False
            return result
        result = self.status(live=False)
        with self.state.lock:
            result["qr_png_base64"] = self.state.qr_png_base64 or None
            result["qr_updated_at"] = self.state.qr_updated_at or None
        result["pairing"] = self._pairing
        return result

    def pair_stop(self) -> dict[str, Any]:
        self._pairing = False
        return self.status(live=False)

    def pair(self, timeout_s: float = 120.0) -> dict[str, Any]:
        self._pairing = True
        try:
            self._reset_pair_state()
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
            return [self._chat_to_dict(c) for c in items]

    def find_chats(self, *, query: str, limit: int = 20) -> list[dict[str, Any]]:
        q = query.strip().lower()
        if not q:
            return []
        with self.state.lock:
            matches = []
            for c in self.state.chats.values():
                payload = self._chat_to_dict(c)
                hay = (
                    f"{c.name} {c.chat_id} {payload.get('display_name', '')} "
                    f"{payload.get('phone', '') or ''}"
                ).lower()
                if q in hay:
                    matches.append(c)
            matches.sort(key=lambda c: c.last_timestamp, reverse=True)
            return [self._chat_to_dict(c) for c in matches[:limit]]

    def get_messages(
        self,
        *,
        chat_id: str,
        limit: int = 30,
        max_chars: int = 800,
        before_timestamp: int | None = None,
        after_timestamp: int | None = None,
        from_me: bool | None = None,
    ) -> list[dict[str, Any]]:
        with self.state.lock:
            bucket = list(self.state.messages.get(chat_id, []))
        if before_timestamp is not None:
            bucket = [m for m in bucket if m.timestamp < before_timestamp]
        if after_timestamp is not None:
            bucket = [m for m in bucket if m.timestamp > after_timestamp]
        if from_me is not None:
            bucket = [m for m in bucket if m.from_me is from_me]
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
                    "chat_display_name": self._chat_display_for_id(m.chat_id),
                    "sender_id": m.sender_id,
                    "text": text,
                    "timestamp": m.timestamp,
                    "from_me": m.from_me,
                }
            )
        return out

    def _lookup_stored_message(self, chat_id: str, message_id: str) -> StoredMessage:
        with self.state.lock:
            for m in self.state.messages.get(chat_id, []):
                if m.message_id == message_id:
                    return m
        raise WorkerError(
            f"Mensagem {message_id} não está em cache. "
            "Use get_whatsapp_messages ou sync_whatsapp_chat_history."
        )

    def _load_quoted_neonize_message(self, stored: StoredMessage) -> NeonizeMessage:
        if not stored.raw_proto_b64:
            raise WorkerError(
                "Mensagem sem metadados para reply/reação. "
                "Receba-a de novo ou sincronize o histórico do chat."
            )
        quoted = NeonizeMessage()
        quoted.ParseFromString(base64.b64decode(stored.raw_proto_b64))
        return quoted

    def _resolve_dest_jid(
        self,
        *,
        chat_id: str | None,
        number: str | None,
    ) -> Any:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        if chat_id:
            return self._jid_from_chat_id(chat_id)
        if number:
            digits = "".join(ch for ch in number if ch.isdigit())
            if not digits:
                raise WorkerError("Número inválido.")
            return build_jid(digits)
        raise WorkerError("Informe chat_id ou number.")

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

    @staticmethod
    def _sender_index_token(chat_jid: Any, sender_jid: Any) -> str:
        """Index token for delete-for-me mutations (see neonize issue #106)."""
        sender_str = Jid2String(sender_jid)
        if "@g.us" not in Jid2String(chat_jid) and chat_jid.User == sender_jid.User:
            return "0"
        return sender_str

    def _delete_one_for_me(
        self,
        *,
        chat_id: str,
        message_id: str,
        sender_id: str,
        from_me: bool,
        timestamp: int,
        delete_media: bool = False,
    ) -> None:
        from neonize.proto import Neonize_pb2 as neonize_proto
        from neonize.proto.waSyncAction import WAWebProtobufSyncAction_pb2 as sync_action

        chat_jid = self._jid_from_chat_id(chat_id)
        sender_jid = self._jid_from_chat_id(sender_id)
        target_jid = Jid2String(chat_jid)
        sender_token = self._sender_index_token(chat_jid, sender_jid)
        is_from_me = "1" if from_me else "0"
        ts = int(timestamp)
        if ts < 10_000_000_000:
            ts *= 1000

        mutation = neonize_proto.MutationInfo(
            Index=["0", target_jid, message_id, is_from_me, sender_token],
            Version=2,
            Value=sync_action.SyncActionValue(
                deleteMessageForMeAction=sync_action.DeleteMessageForMeAction(
                    deleteMedia=delete_media,
                    messageTimestamp=ts,
                ),
            ),
        )
        patch = neonize_proto.PatchInfo(
            Timestamp=int(time.time()),
            Type=neonize_proto.PatchInfo.REGULAR_HIGH,
            Mutations=[mutation],
        )
        self.client.send_app_state(patch)

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
        """Remove messages from this linked device only (including others' messages)."""
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")

        targets: list[tuple[str, str, bool, int]] = []

        if entries:
            for raw in entries:
                if not isinstance(raw, dict):
                    continue
                mid = str(raw.get("message_id", "")).strip()
                sid = str(raw.get("sender_id", "")).strip()
                if not mid or not sid:
                    continue
                targets.append(
                    (
                        mid,
                        sid,
                        bool(raw.get("from_me", False)),
                        int(raw.get("timestamp") or time.time()),
                    )
                )

        with self.state.lock:
            by_id = {m.message_id: m for m in self.state.messages.get(chat_id, [])}

        if message_ids:
            for mid in message_ids:
                mid = str(mid).strip()
                if not mid or any(t[0] == mid for t in targets):
                    continue
                stored = by_id.get(mid)
                if stored is not None:
                    targets.append(
                        (stored.message_id, stored.sender_id, stored.from_me, stored.timestamp)
                    )
                else:
                    targets.append((mid, "", False, int(time.time())))

        if before_timestamp is not None or after_timestamp is not None or from_me is not None:
            with self.state.lock:
                bucket = list(self.state.messages.get(chat_id, []))
            for m in bucket:
                if before_timestamp is not None and m.timestamp >= before_timestamp:
                    continue
                if after_timestamp is not None and m.timestamp <= after_timestamp:
                    continue
                if from_me is not None and m.from_me is not from_me:
                    continue
                if not any(t[0] == m.message_id for t in targets):
                    targets.append(
                        (m.message_id, m.sender_id, m.from_me, m.timestamp)
                    )

        if not targets:
            raise WorkerError(
                "Nenhuma mensagem para apagar. Informe message_ids, entries ou filtros "
                "de timestamp com mensagens já em cache (use sync_whatsapp_chat_history)."
            )

        deleted: list[str] = []
        failed: list[dict[str, str]] = []

        for mid, sender_id, is_from_me, ts in targets:
            if not sender_id:
                failed.append(
                    {
                        "message_id": mid,
                        "error": (
                            "Metadados ausentes (sender_id). Use get_whatsapp_messages ou "
                            "passe entries com sender_id e from_me."
                        ),
                    }
                )
                continue
            try:
                self._delete_one_for_me(
                    chat_id=chat_id,
                    message_id=mid,
                    sender_id=sender_id,
                    from_me=is_from_me,
                    timestamp=ts,
                    delete_media=delete_media,
                )
            except Exception as exc:
                failed.append({"message_id": mid, "error": str(exc)})
                continue
            deleted.append(mid)
            with self.state.lock:
                bucket = self.state.messages.get(chat_id, [])
                self.state.messages[chat_id] = [
                    m for m in bucket if m.message_id != mid
                ]

        return {
            "chat_id": chat_id,
            "mode": "for_me",
            "deleted": deleted,
            "failed": failed,
            "deleted_count": len(deleted),
            "cache_remaining": len(self.state.messages.get(chat_id, [])),
        }

    def request_chat_history(
        self,
        *,
        chat_id: str,
        count: int = 50,
        wait_s: float = 25.0,
    ) -> dict[str, Any]:
        """Ask WhatsApp for older messages (fills in-memory cache via HistorySync/events)."""
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        with self.state.lock:
            before_count = len(self.state.messages.get(chat_id, []))
            bucket = list(self.state.messages.get(chat_id, []))
        if not bucket:
            return {
                "chat_id": chat_id,
                "requested": False,
                "cache_before": 0,
                "cache_after": 0,
                "added": 0,
                "hint": (
                    "Sem mensagens em cache para este chat. Após pair, aguarde HistorySync "
                    "ou envie/receba uma mensagem no chat antes de pedir histórico antigo."
                ),
            }
        oldest = min(bucket, key=lambda m: m.timestamp)
        from neonize.builder import build_history_sync_request
        from neonize.proto.Neonize_pb2 import MessageInfo

        chat_jid = self._jid_from_chat_id(chat_id)
        sender_jid = self._jid_from_chat_id(oldest.sender_id)
        info = MessageInfo(ID=oldest.message_id, Timestamp=oldest.timestamp)
        info.MessageSource.Chat.CopyFrom(chat_jid)
        info.MessageSource.Sender.CopyFrom(sender_jid)
        info.MessageSource.IsFromMe = oldest.from_me
        req = build_history_sync_request(info, count)
        try:
            self.client.send_message(chat_jid, req)
        except Exception as exc:
            raise WorkerError(f"Falha ao pedir histórico: {exc}") from exc

        deadline = time.time() + wait_s
        after_count = before_count
        while time.time() < deadline:
            time.sleep(0.5)
            with self.state.lock:
                after_count = len(self.state.messages.get(chat_id, []))
            if after_count > before_count:
                break

        return {
            "chat_id": chat_id,
            "requested": True,
            "cache_before": before_count,
            "cache_after": after_count,
            "added": max(0, after_count - before_count),
            "oldest_timestamp_used": oldest.timestamp,
        }

    def send_text(
        self,
        *,
        text: str,
        chat_id: str | None = None,
        number: str | None = None,
    ) -> dict[str, Any]:
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        resp = self.client.send_message(jid, text)
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
        }

    def reply_text(
        self,
        *,
        chat_id: str,
        reply_to_message_id: str,
        text: str,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        body = text.strip()
        if not body:
            raise WorkerError("Texto da resposta vazio.")
        stored = self._lookup_stored_message(chat_id, reply_to_message_id)
        quoted = self._load_quoted_neonize_message(stored)
        chat_jid = self._jid_from_chat_id(chat_id)
        resp = self.client.reply_message(body, quoted, to=chat_jid)
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": chat_id,
            "reply_to_message_id": reply_to_message_id,
        }

    def react_message(
        self,
        *,
        chat_id: str,
        message_id: str,
        emoji: str,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        reaction = emoji.strip()
        if not reaction:
            raise WorkerError("Emoji/reação vazio.")
        stored = self._lookup_stored_message(chat_id, message_id)
        chat_jid = self._jid_from_chat_id(chat_id)
        sender_jid = self._jid_from_chat_id(stored.sender_id)
        react_msg = self.client.build_reaction(
            chat_jid, sender_jid, message_id, reaction
        )
        self.client.send_message(chat_jid, react_msg)
        return {
            "chat_id": chat_id,
            "message_id": message_id,
            "emoji": reaction,
        }

    def send_image(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise WorkerError(f"Arquivo não encontrado: {path}")
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        img_msg = self.client.build_image_message(str(path), caption=caption or "")
        resp = self.client.send_message(jid, img_msg)
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
            "file": str(path),
        }

    def send_document(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
        caption: str | None = None,
        filename: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise WorkerError(f"Arquivo não encontrado: {path}")
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        resp = self.client.send_document(
            jid,
            str(path),
            caption=caption or "",
            filename=filename or path.name,
        )
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
            "file": str(path),
        }

    def send_audio(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
        voice_note: bool = False,
    ) -> dict[str, Any]:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise WorkerError(f"Arquivo não encontrado: {path}")
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        resp = self.client.send_audio(jid, str(path), ptt=voice_note)
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
            "file": str(path),
            "voice_note": voice_note,
        }

    def forward_message(
        self,
        *,
        source_chat_id: str,
        message_id: str,
        target_chat_id: str | None = None,
        target_number: str | None = None,
        include_prefix: bool = True,
    ) -> dict[str, Any]:
        stored = self._lookup_stored_message(source_chat_id, message_id)
        body = stored.text.strip()
        if not body:
            raise WorkerError(
                "Mensagem sem texto em cache. Encaminhamento de mídia pura ainda não suportado."
            )
        if include_prefix and not body.startswith("↪"):
            body = f"↪️ {body}"
        sent = self.send_text(
            text=body,
            chat_id=target_chat_id,
            number=target_number,
        )
        sent["forwarded_from"] = {
            "chat_id": source_chat_id,
            "message_id": message_id,
        }
        return sent

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
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise WorkerError(f"Arquivo não encontrado: {path}")
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        resp = self.client.send_video(
            jid,
            str(path),
            caption=caption or "",
            viewonce=view_once,
            gifplayback=gif_playback,
        )
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
            "file": str(path),
        }

    def send_sticker(
        self,
        *,
        file_path: str,
        chat_id: str | None = None,
        number: str | None = None,
    ) -> dict[str, Any]:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise WorkerError(f"Arquivo não encontrado: {path}")
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        resp = self.client.send_sticker(jid, str(path))
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
            "file": str(path),
        }

    def send_contact(
        self,
        *,
        contact_name: str,
        contact_number: str,
        chat_id: str | None = None,
        number: str | None = None,
    ) -> dict[str, Any]:
        name = contact_name.strip()
        digits = "".join(ch for ch in contact_number if ch.isdigit())
        if not name:
            raise WorkerError("contact_name é obrigatório.")
        if not digits:
            raise WorkerError("contact_number inválido.")
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        resp = self.client.send_contact(jid, name, digits)
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
            "contact_name": name,
            "contact_number": digits,
        }

    def list_joined_groups(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        groups = self.client.get_joined_groups()
        out: list[dict[str, Any]] = []
        for g in groups:
            jid = getattr(g, "JID", None)
            chat_id = Jid2String(jid) if jid is not None else ""
            if not chat_id:
                continue
            participants = getattr(g, "Participants", None)
            count = len(participants) if participants is not None else 0
            out.append(
                {
                    "chat_id": chat_id,
                    "name": str(getattr(g, "GroupName", "") or ""),
                    "participant_count": count,
                }
            )
            if len(out) >= limit:
                break
        return out

    def get_profile_picture(self, *, chat_id: str) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        jid = self._jid_from_chat_id(chat_id)
        info = self.client.get_profile_picture(jid)
        return {
            "chat_id": chat_id,
            "url": str(getattr(info, "URL", "") or ""),
            "picture_id": str(getattr(info, "ID", "") or ""),
            "type": str(getattr(info, "Type", "") or ""),
        }

    def send_chat_presence(
        self,
        *,
        chat_id: str,
        composing: bool = True,
        media: str = "text",
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        from neonize.utils.enum import ChatPresence, ChatPresenceMedia

        jid = self._jid_from_chat_id(chat_id)
        state = (
            ChatPresence.CHAT_PRESENCE_COMPOSING
            if composing
            else ChatPresence.CHAT_PRESENCE_PAUSED
        )
        presence_media = (
            ChatPresenceMedia.CHAT_PRESENCE_MEDIA_AUDIO
            if str(media).lower() in ("audio", "voice", "ptt")
            else ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT
        )
        self.client.send_chat_presence(jid, state, presence_media)
        return {
            "chat_id": chat_id,
            "composing": composing,
            "media": "audio" if presence_media == ChatPresenceMedia.CHAT_PRESENCE_MEDIA_AUDIO else "text",
        }

    def send_poll(
        self,
        *,
        question: str,
        options: list[str],
        chat_id: str | None = None,
        number: str | None = None,
        allow_multiple: bool = False,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        title = question.strip()
        opts = [str(o).strip() for o in options if str(o).strip()]
        if not title:
            raise WorkerError("question é obrigatória.")
        if len(opts) < 2:
            raise WorkerError("Informe pelo menos 2 options.")
        from neonize.utils.enum import VoteType

        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        vote_type = VoteType.MULTIPLE if allow_multiple else VoteType.SINGLE
        poll_msg = self.client.build_poll_vote_creation(title, opts, vote_type)
        resp = self.client.send_message(jid, poll_msg)
        return {
            "message_id": resp.ID,
            "timestamp": int(resp.Timestamp),
            "chat_id": Jid2String(jid),
            "question": title,
            "options": opts,
        }

    def send_album(
        self,
        *,
        file_paths: list[str],
        chat_id: str | None = None,
        number: str | None = None,
        caption: str | None = None,
    ) -> dict[str, Any]:
        if not file_paths:
            raise WorkerError("file_paths deve ser uma lista não vazia.")
        paths: list[str] = []
        for raw in file_paths:
            path = Path(str(raw)).expanduser().resolve()
            if not path.is_file():
                raise WorkerError(f"Arquivo não encontrado: {path}")
            paths.append(str(path))
        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        result = self.client.send_album(jid, paths, caption=caption or "")
        sent: list[dict[str, Any]] = []
        if isinstance(result, (list, tuple)):
            for item in result:
                if hasattr(item, "ID"):
                    sent.append(
                        {
                            "message_id": item.ID,
                            "timestamp": int(getattr(item, "Timestamp", 0)),
                        }
                    )
        return {
            "chat_id": Jid2String(jid),
            "files": paths,
            "sent": sent,
            "count": len(sent),
        }

    def get_blocklist(self) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        bl = self.client.get_blocklist()
        jids = getattr(bl, "JIDs", None) or []
        blocked: list[str] = []
        for entry in jids:
            blocked.append(Jid2String(entry))
        return {"blocked": blocked, "count": len(blocked)}

    def update_blocklist(
        self,
        *,
        chat_id: str | None = None,
        number: str | None = None,
        block: bool = True,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        from neonize.utils.enum import BlocklistAction

        jid = self._resolve_dest_jid(chat_id=chat_id, number=number)
        action = BlocklistAction.BLOCK if block else BlocklistAction.UNBLOCK
        self.client.update_blocklist(jid, action)
        return {
            "chat_id": Jid2String(jid),
            "blocked": block,
        }

    def get_group_invite_link(
        self,
        *,
        chat_id: str,
        revoke: bool = False,
    ) -> dict[str, Any]:
        if "@g.us" not in chat_id:
            raise WorkerError("chat_id deve ser um grupo (@g.us).")
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        jid = self._jid_from_chat_id(chat_id)
        link = self.client.get_group_invite_link(jid, revoke=revoke)
        return {"chat_id": chat_id, "invite_link": str(link), "revoked_previous": revoke}

    def leave_group(self, *, chat_id: str) -> dict[str, Any]:
        if "@g.us" not in chat_id:
            raise WorkerError("chat_id deve ser um grupo (@g.us).")
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        jid = self._jid_from_chat_id(chat_id)
        self.client.leave_group(jid)
        with self.state.lock:
            self.state.chats.pop(chat_id, None)
            self.state.messages.pop(chat_id, None)
        return {"chat_id": chat_id, "left": True}

    @staticmethod
    def _parse_group_invite_code(invite_link: str) -> str:
        link = invite_link.strip()
        if "chat.whatsapp.com/" in link:
            return link.rstrip("/").split("/")[-1].split("?")[0]
        return link

    def join_group_link(self, *, invite_link: str) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        code = self._parse_group_invite_code(invite_link)
        if not code:
            raise WorkerError("invite_link ou código inválido.")
        jid = self.client.join_group_with_link(code)
        chat_id = Jid2String(jid)
        return {"chat_id": chat_id, "invite_code": code}

    def preview_group_from_link(self, *, invite_link: str) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        code = self._parse_group_invite_code(invite_link)
        if not code:
            raise WorkerError("invite_link ou código inválido.")
        info = self.client.get_group_info_from_link(code)
        jid = getattr(info, "JID", None)
        chat_id = Jid2String(jid) if jid is not None else ""
        participants = getattr(info, "Participants", None)
        count = len(participants) if participants is not None else 0
        return {
            "invite_code": code,
            "chat_id": chat_id,
            "name": str(getattr(info, "GroupName", "") or ""),
            "participant_count": count,
        }

    def clear_chat_local_cache(self, *, chat_id: str) -> dict[str, Any]:
        removed = 0
        with self.state.lock:
            removed = len(self.state.messages.pop(chat_id, []))
            self.state.chats.pop(chat_id, None)
        if self._cache_store is not None:
            try:
                self._cache_store.delete_chat(chat_id)
            except Exception as exc:
                logging.getLogger("whatsapp.cache").warning(
                    "cache delete_chat failed: %s", exc
                )
        return {"chat_id": chat_id, "removed_from_cache": removed}

    def leave_group_and_purge(
        self,
        *,
        chat_id: str,
        delete_media: bool = False,
    ) -> dict[str, Any]:
        if "@g.us" not in chat_id:
            raise WorkerError("chat_id deve ser um grupo (@g.us).")
        purge_result: dict[str, Any] | None = None
        with self.state.lock:
            ids = [m.message_id for m in self.state.messages.get(chat_id, [])]
        if ids:
            purge_result = self.delete_messages_for_me(
                chat_id=chat_id,
                message_ids=ids,
                delete_media=delete_media,
            )
        left = self.leave_group(chat_id=chat_id)
        return {
            "chat_id": chat_id,
            "left": left.get("left", True),
            "purge": purge_result or {"deleted_count": 0, "deleted": []},
        }

    def vote_poll(
        self,
        *,
        chat_id: str,
        poll_message_id: str,
        selected_options: list[str],
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        opts = [str(o).strip() for o in selected_options if str(o).strip()]
        if not opts:
            raise WorkerError("selected_options deve ter pelo menos uma opção.")
        stored = self._lookup_stored_message(chat_id, poll_message_id)
        neonize_msg = self._load_quoted_neonize_message(stored)
        poll_info = neonize_msg.Info
        chat_jid = self._jid_from_chat_id(chat_id)
        vote_msg = self.client.build_poll_vote(poll_info, opts)
        resp = self.client.send_message(chat_jid, vote_msg)
        return {
            "message_id": resp.ID,
            "chat_id": chat_id,
            "poll_message_id": poll_message_id,
            "selected_options": opts,
        }

    def get_user_info(
        self,
        *,
        chat_ids: list[str] | None = None,
        chat_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        ids = list(chat_ids or [])
        if chat_id:
            ids.append(chat_id)
        ids = [c.strip() for c in ids if c and str(c).strip()]
        if not ids:
            raise WorkerError("Informe chat_id ou chat_ids.")
        jids = [self._jid_from_chat_id(c) for c in ids]
        entries = self.client.get_user_info(*jids)
        users: list[dict[str, Any]] = []
        for entry in entries:
            jid = getattr(entry, "JID", None)
            chat_id_str = Jid2String(jid) if jid is not None else ""
            ui = getattr(entry, "UserInfo", None)
            users.append(
                {
                    "chat_id": chat_id_str,
                    "verified_name": str(getattr(ui, "VerifiedName", "") or "") if ui else "",
                    "status": str(getattr(ui, "Status", "") or "") if ui else "",
                    "picture_id": str(getattr(ui, "PictureID", "") or "") if ui else "",
                }
            )
        return {"users": users, "count": len(users)}

    def set_chat_muted(
        self,
        *,
        chat_id: str,
        mute_hours: int | None = 8,
        unmute: bool = False,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        from datetime import timedelta

        jid = self._jid_from_chat_id(chat_id)
        if unmute:
            until = timedelta(seconds=0)
        else:
            hours = 8 if mute_hours is None else int(mute_hours)
            until = timedelta(hours=max(1, hours))
        self.client.put_muted_until(jid, until)
        return {
            "chat_id": chat_id,
            "muted": not unmute,
            "mute_hours": None if unmute else max(1, int(mute_hours or 8)),
        }

    def search_messages(
        self,
        *,
        query: str,
        chat_id: str | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        q = query.strip().lower()
        if not q:
            return []
        results: list[dict[str, Any]] = []
        with self.state.lock:
            chat_ids = [chat_id] if chat_id else list(self.state.messages.keys())
            for cid in chat_ids:
                if not cid:
                    continue
                for m in self.state.messages.get(cid, []):
                    if q in m.text.lower():
                        results.append(
                            {
                                "message_id": m.message_id,
                                "chat_id": m.chat_id,
                                "chat_display_name": self._chat_display_for_id(m.chat_id),
                                "sender_id": m.sender_id,
                                "text": m.text[:800],
                                "timestamp": m.timestamp,
                                "from_me": m.from_me,
                            }
                        )
        results.sort(key=lambda r: r["timestamp"], reverse=True)
        return results[:limit]

    def get_group_info(self, *, chat_id: str) -> dict[str, Any]:
        if "@g.us" not in chat_id:
            raise WorkerError("chat_id não é um grupo (@g.us).")
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        jid = self._jid_from_chat_id(chat_id)
        info = self.client.get_group_info(jid)
        name = getattr(info, "Name", None) or getattr(info, "name", "") or ""
        participants = getattr(info, "Participants", None) or getattr(info, "participants", [])
        count = len(participants) if participants is not None else 0
        return {
            "chat_id": chat_id,
            "name": str(name),
            "participant_count": count,
        }

    def edit_text(
        self,
        *,
        chat_id: str,
        message_id: str,
        text: str,
    ) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        body = text.strip()
        if not body:
            raise WorkerError("Texto vazio.")
        stored = self._lookup_stored_message(chat_id, message_id)
        if not stored.from_me:
            raise WorkerError("Só é possível editar mensagens enviadas por você.")
        from neonize.proto.waE2E.WAWebProtobufsE2E_pb2 import Message

        chat_jid = self._jid_from_chat_id(chat_id)
        new_msg = Message(conversation=body)
        resp = self.client.edit_message(chat_jid, message_id, new_msg)
        with self.state.lock:
            stored.text = body
        self._persist_cached_message(stored)
        return {
            "message_id": message_id,
            "chat_id": chat_id,
            "timestamp": int(resp.Timestamp),
        }

    def set_chat_archived(self, *, chat_id: str, archived: bool) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        jid = self._jid_from_chat_id(chat_id)
        self.client.put_archived(jid, archived)
        return {"chat_id": chat_id, "archived": archived}

    def set_chat_pinned(self, *, chat_id: str, pinned: bool) -> dict[str, Any]:
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        jid = self._jid_from_chat_id(chat_id)
        self.client.put_pinned(jid, pinned)
        return {"chat_id": chat_id, "pinned": pinned}

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

    def delete_messages(
        self,
        *,
        chat_id: str,
        message_ids: list[str],
    ) -> dict[str, Any]:
        """Revoke (delete for everyone) messages you sent. WhatsApp API limits apply."""
        if not self.client.is_logged_in:
            raise WorkerError("WhatsApp não conectado.")
        ids = [str(mid).strip() for mid in message_ids if str(mid).strip()]
        if not ids:
            raise WorkerError("Informe pelo menos um message_id.")

        chat_jid = self._jid_from_chat_id(chat_id)
        me = self.client.get_me()
        my_jid = me.JID if me and me.JID else chat_jid

        with self.state.lock:
            by_id = {m.message_id: m for m in self.state.messages.get(chat_id, [])}

        deleted: list[str] = []
        failed: list[dict[str, str]] = []

        for mid in ids:
            stored = by_id.get(mid)
            if stored is not None and not stored.from_me:
                failed.append(
                    {
                        "message_id": mid,
                        "error": (
                            "Só é possível apagar para todos mensagens enviadas por você. "
                            "Mensagens de terceiros exigem outro fluxo (não suportado aqui)."
                        ),
                    }
                )
                continue

            try:
                self.client.revoke_message(chat_jid, my_jid, mid)
            except Exception as exc:
                failed.append({"message_id": mid, "error": str(exc)})
                continue

            deleted.append(mid)
            with self.state.lock:
                bucket = self.state.messages.get(chat_id, [])
                self.state.messages[chat_id] = [
                    m for m in bucket if m.message_id != mid
                ]
                if stored:
                    entry = self.state.chats.get(chat_id)
                    if entry and entry.last_message_preview == stored.text[:200]:
                        entry.last_message_preview = ""

        return {
            "chat_id": chat_id,
            "deleted": deleted,
            "failed": failed,
            "deleted_count": len(deleted),
        }

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
        if method == "pair_start":
            return self.pair_start()
        if method == "pair_poll":
            return self.pair_poll()
        if method == "pair_stop":
            return self.pair_stop()
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
                before_timestamp=params.get("before_timestamp"),
                after_timestamp=params.get("after_timestamp"),
                from_me=params.get("from_me"),
            )
        if method == "request_chat_history":
            return self.request_chat_history(
                chat_id=str(params["chat_id"]),
                count=int(params.get("count", 50)),
                wait_s=float(params.get("wait_s", 25)),
            )
        if method == "send_text":
            return self.send_text(
                text=str(params["text"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
            )
        if method == "reply_text":
            return self.reply_text(
                chat_id=str(params["chat_id"]),
                reply_to_message_id=str(params["reply_to_message_id"]),
                text=str(params["text"]),
            )
        if method == "react_message":
            return self.react_message(
                chat_id=str(params["chat_id"]),
                message_id=str(params["message_id"]),
                emoji=str(params["emoji"]),
            )
        if method == "send_image":
            return self.send_image(
                file_path=str(params["file_path"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
                caption=params.get("caption"),
            )
        if method == "search_messages":
            return self.search_messages(
                query=str(params.get("query", "")),
                chat_id=params.get("chat_id"),
                limit=int(params.get("limit", 30)),
            )
        if method == "get_group_info":
            return self.get_group_info(chat_id=str(params["chat_id"]))
        if method == "edit_text":
            return self.edit_text(
                chat_id=str(params["chat_id"]),
                message_id=str(params["message_id"]),
                text=str(params["text"]),
            )
        if method == "set_chat_archived":
            return self.set_chat_archived(
                chat_id=str(params["chat_id"]),
                archived=bool(params.get("archived", True)),
            )
        if method == "set_chat_pinned":
            return self.set_chat_pinned(
                chat_id=str(params["chat_id"]),
                pinned=bool(params.get("pinned", True)),
            )
        if method == "mark_read":
            return self.mark_read(
                chat_id=str(params["chat_id"]),
                message_ids=params.get("message_ids"),
            )
        if method == "delete_messages":
            raw_ids = params.get("message_ids")
            if not isinstance(raw_ids, list):
                raise WorkerError("message_ids deve ser uma lista.")
            return self.delete_messages(
                chat_id=str(params["chat_id"]),
                message_ids=[str(i) for i in raw_ids],
            )
        if method == "delete_messages_for_me":
            raw_ids = params.get("message_ids")
            message_ids = (
                [str(i) for i in raw_ids] if isinstance(raw_ids, list) else None
            )
            raw_entries = params.get("entries")
            entries = raw_entries if isinstance(raw_entries, list) else None
            return self.delete_messages_for_me(
                chat_id=str(params["chat_id"]),
                message_ids=message_ids,
                before_timestamp=params.get("before_timestamp"),
                after_timestamp=params.get("after_timestamp"),
                from_me=params.get("from_me"),
                delete_media=bool(params.get("delete_media", False)),
                entries=entries,
            )
        if method == "send_document":
            return self.send_document(
                file_path=str(params["file_path"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
                caption=params.get("caption"),
                filename=params.get("filename"),
            )
        if method == "send_audio":
            return self.send_audio(
                file_path=str(params["file_path"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
                voice_note=bool(params.get("voice_note", False)),
            )
        if method == "forward_message":
            return self.forward_message(
                source_chat_id=str(params["source_chat_id"]),
                message_id=str(params["message_id"]),
                target_chat_id=params.get("target_chat_id"),
                target_number=params.get("target_number"),
                include_prefix=bool(params.get("include_prefix", True)),
            )
        if method == "set_chat_muted":
            return self.set_chat_muted(
                chat_id=str(params["chat_id"]),
                mute_hours=params.get("mute_hours"),
                unmute=bool(params.get("unmute", False)),
            )
        if method == "send_video":
            return self.send_video(
                file_path=str(params["file_path"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
                caption=params.get("caption"),
                view_once=bool(params.get("view_once", False)),
                gif_playback=bool(params.get("gif_playback", False)),
            )
        if method == "send_sticker":
            return self.send_sticker(
                file_path=str(params["file_path"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
            )
        if method == "send_contact":
            return self.send_contact(
                contact_name=str(params["contact_name"]),
                contact_number=str(params["contact_number"]),
                chat_id=params.get("chat_id"),
                number=params.get("number"),
            )
        if method == "list_joined_groups":
            return self.list_joined_groups(limit=int(params.get("limit", 50)))
        if method == "get_profile_picture":
            return self.get_profile_picture(chat_id=str(params["chat_id"]))
        if method == "send_chat_presence":
            return self.send_chat_presence(
                chat_id=str(params["chat_id"]),
                composing=bool(params.get("composing", True)),
                media=str(params.get("media", "text")),
            )
        if method == "send_poll":
            raw_opts = params.get("options")
            if not isinstance(raw_opts, list):
                raise WorkerError("options deve ser uma lista.")
            return self.send_poll(
                question=str(params["question"]),
                options=[str(o) for o in raw_opts],
                chat_id=params.get("chat_id"),
                number=params.get("number"),
                allow_multiple=bool(params.get("allow_multiple", False)),
            )
        if method == "send_album":
            raw_paths = params.get("file_paths")
            if not isinstance(raw_paths, list):
                raise WorkerError("file_paths deve ser uma lista.")
            return self.send_album(
                file_paths=[str(p) for p in raw_paths],
                chat_id=params.get("chat_id"),
                number=params.get("number"),
                caption=params.get("caption"),
            )
        if method == "get_blocklist":
            return self.get_blocklist()
        if method == "update_blocklist":
            return self.update_blocklist(
                chat_id=params.get("chat_id"),
                number=params.get("number"),
                block=bool(params.get("block", True)),
            )
        if method == "get_group_invite_link":
            return self.get_group_invite_link(
                chat_id=str(params["chat_id"]),
                revoke=bool(params.get("revoke", False)),
            )
        if method == "leave_group":
            return self.leave_group(chat_id=str(params["chat_id"]))
        if method == "join_group_link":
            return self.join_group_link(invite_link=str(params["invite_link"]))
        if method == "preview_group_from_link":
            return self.preview_group_from_link(invite_link=str(params["invite_link"]))
        if method == "clear_chat_local_cache":
            return self.clear_chat_local_cache(chat_id=str(params["chat_id"]))
        if method == "leave_group_and_purge":
            return self.leave_group_and_purge(
                chat_id=str(params["chat_id"]),
                delete_media=bool(params.get("delete_media", False)),
            )
        if method == "vote_poll":
            raw_opts = params.get("selected_options")
            if not isinstance(raw_opts, list):
                raise WorkerError("selected_options deve ser uma lista.")
            return self.vote_poll(
                chat_id=str(params["chat_id"]),
                poll_message_id=str(params["poll_message_id"]),
                selected_options=[str(o) for o in raw_opts],
            )
        if method == "get_user_info":
            raw_ids = params.get("chat_ids")
            chat_ids = [str(i) for i in raw_ids] if isinstance(raw_ids, list) else None
            return self.get_user_info(
                chat_ids=chat_ids,
                chat_id=params.get("chat_id"),
            )
        if method == "transcribe_audio":
            return {
                "text": self._transcribe_stored_audio(
                    chat_id=str(params["chat_id"]),
                    message_id=str(params["message_id"]),
                )
            }
        if method == "transcription_status":
            ignore = sorted(self._runtime.ignore_numbers())
            return {
                "auto_transcribe": self._effective_auto_transcribe(),
                "model": self._transcribe_model,
                "language": self._transcribe_language,
                "prefix": self._effective_transcribe_prefix(),
                "only_incoming": self._effective_only_incoming(),
                "private_only": self._effective_private_only(),
                "ignore_numbers": ignore,
                "ignore_count": len(ignore),
                "runtime_file": str(self._runtime.path),
                "transcriber_ready": (
                    self._transcriber._ready if self._transcriber else False
                ),
            }
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


def _acquire_lock(session_dir: Path) -> Any:
    """Acquire an exclusive fcntl lock so only one worker runs per session."""
    import fcntl

    lock_path = session_dir / "worker.lock"
    lock_file = open(str(lock_path), "w")
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        sys.stderr.write(
            "[integrator] Outro worker WhatsApp já está em execução para esta sessão.\n"
            f"Lockfile: {lock_path}\n"
            "Encerre integrator serve ou integrator whatsapp watch antes de iniciar outro.\n"
        )
        sys.stderr.flush()
        sys.exit(1)
    lock_file.write(str(os.getpid()))
    lock_file.flush()
    return lock_file


def _run_watch_mode(worker: NeonizeWorker) -> None:
    """Watch mode: connect and stay alive auto-transcribing; no stdin RPC loop."""
    import signal

    stop_event = threading.Event()

    def _handle_sig(*_: Any) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_sig)
    try:
        signal.signal(signal.SIGINT, _handle_sig)
    except OSError:
        pass

    worker.connect_background()
    status = worker.status(live=False)
    sys.stderr.write(
        f"[integrator-watch] iniciado | auto_transcribe={worker._auto_transcribe}"
        f" | model={worker._transcribe_model}"
        f" | state={status.get('state', '?')}\n"
    )
    sys.stderr.flush()

    while not stop_event.is_set():
        stop_event.wait(30)
        if stop_event.is_set():
            break
        try:
            st = worker.status(live=False)
            if st.get("state") != "connected":
                worker._ensure_connect_thread()
        except Exception:
            pass

    try:
        worker.shutdown()
    except Exception:
        pass
    sys.stderr.write("[integrator-watch] encerrado.\n")
    sys.stderr.flush()


def main() -> None:
    _redirect_library_stdout()
    _configure_library_logging()
    session_dir = Path(
        os.environ.get("INTEGRATOR_WHATSAPP_SESSION_DIR", "data/whatsapp")
    ).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)

    lock_file = _acquire_lock(session_dir)
    try:
        worker = NeonizeWorker(session_dir)

        watch_mode = os.environ.get(
            "INTEGRATOR_WHATSAPP_WATCH_MODE", ""
        ).lower() in ("1", "true", "yes")

        if watch_mode:
            _run_watch_mode(worker)
            return

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
    finally:
        try:
            lock_file.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
