from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

pytest.importorskip("sqlite3")

# Import from bridge package (worker cwd)
import sys

BRIDGE = Path(__file__).resolve().parents[1] / "bridges" / "whatsapp-neonize"
sys.path.insert(0, str(BRIDGE))

from cache_store import MessageCacheStore  # noqa: E402


@dataclass
class _Msg:
    message_id: str
    chat_id: str
    sender_id: str
    text: str
    timestamp: int
    from_me: bool
    raw_proto_b64: str = ""


def test_cache_store_upsert_and_reload(tmp_path: Path) -> None:
    db = tmp_path / "message_cache.db"
    store = MessageCacheStore(db)
    msg = _Msg(
        message_id="m1",
        chat_id="5511@s.whatsapp.net",
        sender_id="5511@s.whatsapp.net",
        text="oi",
        timestamp=100,
        from_me=True,
    )
    store.upsert(msg)
    store.close()

    store2 = MessageCacheStore(db)
    buckets = store2.load_into_buckets(max_per_chat=10)
    store2.close()
    assert "5511@s.whatsapp.net" in buckets
    assert buckets["5511@s.whatsapp.net"][0].message_id == "m1"
    assert buckets["5511@s.whatsapp.net"][0].text == "oi"
