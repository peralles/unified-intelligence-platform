from __future__ import annotations

import sys
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1] / "bridges" / "whatsapp-neonize"
sys.path.insert(0, str(BRIDGE))

from transcribe_model import resolve_model_id  # noqa: E402


def test_resolve_model_id_strips_hf_prefixes() -> None:
    assert resolve_model_id("mobiuslabsgmbh/faster-whisper-large-v3-turbo") == "large-v3-turbo"
    assert resolve_model_id("Systran/faster-whisper-small") == "small"
    assert resolve_model_id("mlx-community/whisper-large-v3-turbo") == "whisper-large-v3-turbo"
    assert resolve_model_id("small") == "small"
    assert resolve_model_id("  ") == "small"
