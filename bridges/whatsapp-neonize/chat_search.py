"""Chat search helpers (phone digit matching for find_chats)."""

from __future__ import annotations

import re


def normalize_phone_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def phone_digits_match(query_digits: str, *candidates: str | None) -> bool:
    """True when query digits match any candidate (full, suffix, or tail overlap)."""
    q = normalize_phone_digits(query_digits)
    if len(q) < 8:
        return False
    for raw in candidates:
        if not raw:
            continue
        d = normalize_phone_digits(raw)
        if not d:
            continue
        if q in d or d in q:
            return True
        tail = min(11, len(q), len(d))
        if tail >= 8 and (q[-tail:] == d[-tail:] or d.endswith(q[-tail:]) or q.endswith(d[-tail:])):
            return True
    return False


def chat_haystack(
    *,
    name: str,
    chat_id: str,
    display_name: str,
    phone: str | None,
) -> str:
    return f"{name} {chat_id} {display_name} {phone or ''}".lower()
