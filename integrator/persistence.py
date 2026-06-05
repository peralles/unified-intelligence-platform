"""Detect whether the integrator data directory survives container redeploys."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from integrator.config import is_container, settings
from integrator.logging_setup import get_logger

logger = get_logger("persistence")

_MARKER_DIR = ".integrator"
_MARKER_FILE = "volume_marker.json"
_PROBE_FILE = ".write_probe"

PersistenceStatus = Literal["ok", "warn", "error"]


@dataclass(frozen=True)
class PersistenceReport:
    status: PersistenceStatus
    data_path: str
    writable: bool
    mounted: bool
    docker_mode: bool
    volume_id: str | None
    message: str
    hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def data_dir() -> Path:
    return settings.root_dir / "data"


def check_data_persistence(*, refresh_marker: bool = False) -> PersistenceReport:
    """Return persistence health; optionally update the volume marker file."""
    path = data_dir()
    docker_mode = is_container()
    writable = _probe_writable(path)
    mounted = _is_mount(path) if path.exists() else False
    marker = _read_marker(path) if writable else None
    volume_id = str(marker["volume_id"]) if marker and marker.get("volume_id") else None

    if refresh_marker and writable:
        volume_id = _touch_marker(path, existing=marker)

    if not writable:
        return PersistenceReport(
            status="error",
            data_path=str(path),
            writable=False,
            mounted=mounted,
            docker_mode=docker_mode,
            volume_id=volume_id,
            message="Diretório de dados não gravável.",
            hint="Monte um volume persistente em /app/data (Coolify → Storages).",
        )

    if docker_mode and not mounted:
        return PersistenceReport(
            status="warn",
            data_path=str(path),
            writable=True,
            mounted=False,
            docker_mode=True,
            volume_id=volume_id,
            message=(
                "/app/data não parece ser um volume Docker — cada redeploy pode apagar "
                "sessão WhatsApp e tokens Google."
            ),
            hint="Coolify: Storages → tipo persistent → mount path /app/data. Ver docs/COOLIFY.md.",
        )

    return PersistenceReport(
        status="ok",
        data_path=str(path),
        writable=True,
        mounted=mounted,
        docker_mode=docker_mode,
        volume_id=volume_id,
        message="Persistência de dados OK.",
        hint=None,
    )


def ensure_volume_marker() -> PersistenceReport:
    """Startup hook: probe writes and refresh marker; log warnings."""
    report = check_data_persistence(refresh_marker=True)
    if report.status == "warn":
        logger.warning("data persistence | %s | %s", report.message, report.hint)
    elif report.status == "error":
        logger.error("data persistence | %s | %s", report.message, report.hint)
    else:
        logger.info(
            "data persistence ok | path=%s | volume_id=%s | mounted=%s",
            report.data_path,
            report.volume_id,
            report.mounted,
        )
    return report


def _probe_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_dir = path / _MARKER_DIR
        probe_dir.mkdir(parents=True, exist_ok=True)
        probe = probe_dir / _PROBE_FILE
        token = f"{os.getpid()}-{time.time_ns()}"
        probe.write_text(token, encoding="utf-8")
        ok = probe.read_text(encoding="utf-8") == token
        probe.unlink(missing_ok=True)
        return ok
    except OSError as exc:
        logger.warning("data dir not writable | path=%s | err=%s", path, exc)
        return False


def _is_mount(path: Path) -> bool:
    try:
        return os.path.ismount(path.resolve())
    except OSError:
        return False


def _marker_path(path: Path) -> Path:
    return path / _MARKER_DIR / _MARKER_FILE


def _read_marker(path: Path) -> dict[str, Any] | None:
    marker_path = _marker_path(path)
    if not marker_path.is_file():
        return None
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _touch_marker(path: Path, existing: dict[str, Any] | None) -> str:
    marker_path = _marker_path(path)
    marker_path.parent.mkdir(parents=True, exist_ok=True)
    now = time.time()
    if existing and existing.get("volume_id"):
        volume_id = str(existing["volume_id"])
        payload = {
            "volume_id": volume_id,
            "created_at": existing.get("created_at", now),
            "last_seen_at": now,
        }
    else:
        volume_id = str(uuid.uuid4())
        payload = {
            "volume_id": volume_id,
            "created_at": now,
            "last_seen_at": now,
        }
    marker_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return volume_id
