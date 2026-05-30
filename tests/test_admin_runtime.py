"""Admin runtime config tests."""

from __future__ import annotations

from pathlib import Path

from integrator.admin.runtime import RuntimeStore, normalize_phone_digits


def test_normalize_phone_digits() -> None:
    assert normalize_phone_digits("+55 (11) 98888-7777") == "5511988887777"


def test_parse_ignore_lines() -> None:
    store = RuntimeStore()
    numbers = store.parse_ignore_lines(
        "# comentário\n5511999999999\n+55 11 8888-7777\n\n5511888777777"
    )
    assert numbers == ["5511999999999", "551188887777", "5511888777777"]


def test_runtime_patch_and_effective(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "runtime.json"
    store = RuntimeStore(path)
    store.save({})
    updated = store.patch(
        {
            "whatsapp": {
                "auto_transcribe": True,
                "transcribe_ignore_numbers": ["5511999999999"],
            }
        }
    )
    eff = store.effective_whatsapp(updated)
    assert eff["auto_transcribe"] is True
    assert eff["transcribe_ignore_numbers"] == ["5511999999999"]
