"""Whisper model id normalization for faster-whisper."""

from __future__ import annotations

_MODEL_PREFIXES = (
    "mlx-community/",
    "mobiuslabsgmbh/faster-whisper-",
    "Systran/faster-whisper-",
)


def resolve_model_id(model_id: str) -> str:
    """Normalize Hugging Face repo ids to faster-whisper short names."""
    mid = model_id.strip()
    for prefix in _MODEL_PREFIXES:
        if mid.startswith(prefix):
            mid = mid[len(prefix):]
            break
    return mid or "small"
