from __future__ import annotations

import sys
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parents[1] / "bridges" / "whatsapp-neonize"
sys.path.insert(0, str(BRIDGE_DIR))

from transcribe_cleanup import trim_whisper_repetition  # noqa: E402


def test_trim_single_word_tail_repetition() -> None:
    base = "Caso você conheça alguém também que fazia a"
    junk = " ".join(["slang"] * 40)
    raw = f"{base} {junk}"
    out = trim_whisper_repetition(raw)
    assert out == base
    assert "slang" not in out


def test_trim_phrase_tail_repetition() -> None:
    base = "Entrega em Santa Bárbara seria ótimo"
    junk = " ".join(["ok entendi"] * 6)
    out = trim_whisper_repetition(f"{base} {junk}")
    assert out == base


def test_short_text_unchanged() -> None:
    text = "slang slang slang"
    assert trim_whisper_repetition(text, min_run=4) == text


def test_normal_text_unchanged() -> None:
    text = "Então faz isso por gentileza porque a gente vê pela internet marcas boas."
    assert trim_whisper_repetition(text) == text
