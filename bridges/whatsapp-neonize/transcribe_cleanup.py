"""Post-process Whisper output (tail repetition / silence hallucinations)."""

from __future__ import annotations


def _normalize_token(word: str) -> str:
    return word.lower().rstrip(".,!?;:")


def trim_whisper_repetition(text: str, *, min_run: int = 4) -> str:
    """Drop trailing loops of the same word or short phrase (common Whisper artifact)."""
    text = (text or "").strip()
    if not text:
        return text

    words = text.split()
    if len(words) < min_run:
        return text

    last_norm = _normalize_token(words[-1])
    run = 1
    for i in range(len(words) - 2, -1, -1):
        if _normalize_token(words[i]) == last_norm:
            run += 1
        else:
            break
    if run >= min_run:
        trimmed = " ".join(words[: len(words) - run]).rstrip(" ,;:-")
        return trimmed.strip()

    max_phrase = min(5, len(words) // min_run)
    for phrase_len in range(2, max_phrase + 1):
        if len(words) < phrase_len * min_run:
            continue
        phrase_norm = [_normalize_token(w) for w in words[-phrase_len:]]
        run = 1
        pos = len(words) - phrase_len - 1
        while pos >= phrase_len - 1:
            chunk_norm = [_normalize_token(w) for w in words[pos - phrase_len + 1 : pos + 1]]
            if chunk_norm == phrase_norm:
                run += 1
                pos -= phrase_len
            else:
                break
        if run >= min_run:
            trimmed = " ".join(words[: len(words) - phrase_len * run]).rstrip(" ,;:-")
            return trimmed.strip()

    return text
