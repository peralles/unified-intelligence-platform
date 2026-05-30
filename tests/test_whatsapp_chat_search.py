from __future__ import annotations

import sys
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parents[1] / "bridges" / "whatsapp-neonize"
sys.path.insert(0, str(BRIDGE_DIR))

from chat_search import (  # noqa: E402
    chat_haystack,
    normalize_phone_digits,
    phone_digits_match,
)


def test_normalize_phone_digits() -> None:
    assert normalize_phone_digits("+55 (19) 99203-4333") == "5519992034333"


def test_phone_digits_match_formatted_vs_query() -> None:
    assert phone_digits_match("5519992034333", "+55 19 99203-4333")
    assert phone_digits_match("19992034333", "5519992034333")


def test_phone_digits_match_name_only_fails() -> None:
    assert not phone_digits_match("5519992034333", "Vivian")


def test_chat_haystack_includes_display_name() -> None:
    hay = chat_haystack(
        name="Vivian",
        chat_id="123@lid",
        display_name="Vivian (+55 19 99203-4333)",
        phone="+55 19 99203-4333",
    )
    assert "vivian" in hay
    assert "99203" in hay
