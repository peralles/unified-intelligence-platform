"""SQLite persistence for WhatsApp message cache (survives worker restarts)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CacheRow:
    message_id: str
    chat_id: str
    sender_id: str
    text: str
    timestamp: int
    from_me: bool
    raw_proto_b64: str
    is_audio: bool = False


class MessageCacheStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                sender_id TEXT NOT NULL,
                text TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                from_me INTEGER NOT NULL,
                raw_proto_b64 TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (chat_id, message_id)
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_ts ON messages (chat_id, timestamp)"
        )
        cols = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "is_audio" not in cols:
            self._conn.execute(
                "ALTER TABLE messages ADD COLUMN is_audio INTEGER NOT NULL DEFAULT 0"
            )
        self._conn.commit()

    def upsert(self, msg: Any) -> None:
        self._conn.execute(
            """
            INSERT INTO messages (
                message_id, chat_id, sender_id, text, timestamp, from_me,
                raw_proto_b64, is_audio
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, message_id) DO UPDATE SET
                sender_id=excluded.sender_id,
                text=excluded.text,
                timestamp=excluded.timestamp,
                from_me=excluded.from_me,
                raw_proto_b64=excluded.raw_proto_b64,
                is_audio=excluded.is_audio
            """,
            (
                msg.message_id,
                msg.chat_id,
                msg.sender_id,
                msg.text,
                msg.timestamp,
                1 if msg.from_me else 0,
                msg.raw_proto_b64,
                1 if getattr(msg, "is_audio", False) else 0,
            ),
        )
        self._conn.commit()

    def load_into_buckets(
        self,
        *,
        max_per_chat: int,
    ) -> dict[str, list[CacheRow]]:
        cur = self._conn.execute(
            """
            SELECT message_id, chat_id, sender_id, text, timestamp, from_me,
                   raw_proto_b64, is_audio
            FROM messages
            ORDER BY chat_id, timestamp
            """
        )
        buckets: dict[str, list[CacheRow]] = {}
        for row in cur.fetchall():
            chat_id = row[1]
            bucket = buckets.setdefault(chat_id, [])
            bucket.append(
                CacheRow(
                    message_id=row[0],
                    chat_id=row[1],
                    sender_id=row[2],
                    text=row[3],
                    timestamp=int(row[4]),
                    from_me=bool(row[5]),
                    raw_proto_b64=row[6] or "",
                    is_audio=bool(row[7]) if len(row) > 7 else False,
                )
            )
            if len(bucket) > max_per_chat:
                buckets[chat_id] = bucket[-max_per_chat:]
        return buckets

    def delete_chat(self, chat_id: str) -> None:
        self._conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        self._conn.commit()

    def prune_chat(self, chat_id: str, *, keep: int) -> None:
        self._conn.execute(
            """
            DELETE FROM messages
            WHERE chat_id = ? AND message_id NOT IN (
                SELECT message_id FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            )
            """,
            (chat_id, chat_id, keep),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
