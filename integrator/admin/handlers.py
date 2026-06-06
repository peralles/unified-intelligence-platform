"""Admin API business logic — shared by routes; replaces most CLI for operators."""

from __future__ import annotations

import json
import threading
import webbrowser
from typing import Any
from integrator.accounts.registry import (
    AccountNotFoundError,
    get_default_account_id,
    list_accounts,
    remove_account,
    set_default_account,
    validate_account_id,
)
from integrator.auth.google_oauth import run_interactive_login
from integrator.onboarding.preflight import repo_deps_ok, run_uv_sync
from integrator.setup.status import configuration_summary, is_configured
from integrator.config import settings
from integrator.clients.claude_desktop import discover_claude_desktop
from integrator.clients.mcp_setup import run_all_client_checks, setup_mcp_clients
from integrator.hermes.config_merge import DEFAULT_SERVER_NAME
from integrator.hermes.discovery import discover_hermes
from integrator.hermes.doctor import CheckResult, critical_failures
from integrator.logging_setup import get_logger, read_audit_failures
from integrator.ops_log import log_event
from integrator.onboarding.google_cloud import (
    credentials_ready,
    open_google_setup_sequence,
    validate_credentials_file,
)
from integrator.onboarding.links import GOOGLE_SETUP_STEPS, HERMES_INSTALL, UV_INSTALL
from integrator.providers.tools import list_all_tool_metadata
from integrator.whatsapp.session import WhatsAppSession
from integrator.whatsapp.session_store import (
    has_persisted_session,
    local_status_snapshot,
    remove_session_data,
)

logger = get_logger("admin")

_sync_lock = threading.Lock()
_sync_job: dict[str, Any] | None = None

_login_lock = threading.Lock()
_login_job: dict[str, Any] | None = None


def _check_to_dict(r: CheckResult) -> dict[str, Any]:
    return {
        "id": r.id,
        "label": r.label,
        "status": r.status.value,
        "detail": r.detail,
        "hint": r.hint,
    }


def setup_status(*, mode: str = "sse") -> dict[str, Any]:
    install = discover_hermes()
    claude = discover_claude_desktop()
    checks = run_all_client_checks(server_name=DEFAULT_SERVER_NAME, mode=mode)
    label, next_step = configuration_summary()
    return {
        "configured": is_configured(),
        "configuration_label": label,
        "next_step": next_step,
        "credentials_ready": credentials_ready(),
        "deps_ok": repo_deps_ok(),
        "hermes": {
            "binary": str(install.binary) if install.binary else None,
            "config_path": str(install.config_path),
        },
        "claude_desktop": {
            "config_path": str(claude.config_path),
            "app_found": claude.app_found,
        },
        "checks": [_check_to_dict(c) for c in checks],
        "critical_failures": len(critical_failures(checks)),
        "links": {
            "uv_install": UV_INSTALL,
            "hermes_install": HERMES_INSTALL,
            "google_steps": [
                {"title": s.title, "url": s.url, "instruction": s.instruction}
                for s in GOOGLE_SETUP_STEPS
            ],
        },
    }


def start_sync_deps(*, verbose: bool = False) -> dict[str, Any]:
    global _sync_job
    with _sync_lock:
        if _sync_job and _sync_job.get("status") == "running":
            return {"ok": True, "job": dict(_sync_job)}

        def _run() -> None:
            global _sync_job
            code = run_uv_sync(verbose=verbose)
            with _sync_lock:
                _sync_job = {
                    "status": "ok" if code == 0 else "error",
                    "exit_code": code,
                }

        _sync_job = {"status": "running", "exit_code": None}
        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True, "job": dict(_sync_job)}


def sync_deps_status() -> dict[str, Any]:
    with _sync_lock:
        job = dict(_sync_job) if _sync_job else {"status": "idle"}
    job["deps_ok"] = repo_deps_ok()
    return job


def open_google_cloud_steps() -> dict[str, Any]:
    open_google_setup_sequence(interactive=False)
    return {"ok": True, "steps": len(GOOGLE_SETUP_STEPS)}


def save_credentials_json(content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"JSON inválido: {exc}"}
    settings.ensure_data_dirs()
    dest = settings.credentials_path
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.exception("admin credentials write failed path=%s", dest)
        return {
            "ok": False,
            "error": (
                "Não foi possível gravar o JSON OAuth no servidor. "
                "Verifique se o volume /app/data está gravável."
                f" ({exc})"
            ),
        }
    try:
        validate_credentials_file(dest)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        return {"ok": False, "error": str(exc)}
    log_event(logger, "admin.credentials.saved", path=str(dest))
    return {"ok": True, "path": str(dest)}


def list_google_accounts() -> dict[str, Any]:
    default_id = get_default_account_id()
    accounts = []
    for acc in list_accounts():
        accounts.append(
            {
                "id": acc.id,
                "label": acc.label,
                "email": acc.email,
                "has_token": acc.has_token,
                "is_default": acc.id == default_id,
            }
        )
    return {
        "default_account": default_id,
        "accounts": accounts,
        "credentials_path": str(settings.credentials_path),
    }


def start_google_login(*, account_id: str, label: str | None = None) -> dict[str, Any]:
    global _login_job
    try:
        aid = validate_account_id(account_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    with _login_lock:
        if _login_job and _login_job.get("status") == "running":
            return {"ok": False, "error": "Login já em andamento", "job": dict(_login_job)}

        def _run() -> None:
            global _login_job
            try:
                path = run_interactive_login(aid, label=label)
                acc = next((a for a in list_accounts() if a.id == aid), None)
                with _login_lock:
                    _login_job = {
                        "status": "ok",
                        "account_id": aid,
                        "email": acc.email if acc else None,
                        "token_path": str(path),
                    }
            except Exception as exc:
                with _login_lock:
                    _login_job = {"status": "error", "error": str(exc)}

        _login_job = {"status": "running", "account_id": aid}
        threading.Thread(target=_run, daemon=True).start()
        return {"ok": True, "job": dict(_login_job)}


def google_login_status() -> dict[str, Any]:
    with _login_lock:
        return dict(_login_job) if _login_job else {"status": "idle"}


def google_set_default(account_id: str) -> dict[str, Any]:
    try:
        set_default_account(account_id)
        return {"ok": True, "default_account": account_id}
    except (AccountNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def google_logout(account_id: str) -> dict[str, Any]:
    try:
        remove_account(account_id)
        return {"ok": True, "removed": account_id}
    except (AccountNotFoundError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def whatsapp_snapshot() -> dict[str, Any]:
    snap = local_status_snapshot()
    out: dict[str, Any] = {"local": snap, "enabled": settings.whatsapp_enabled}
    if settings.whatsapp_enabled:
        session = WhatsAppSession.get()
        try:
            # Fast path: live=True blocks up to wait_s on bridge lock and freezes pair_poll.
            out["live"] = session.status(live=False)
        except Exception as exc:
            out["error"] = str(exc)
        try:
            out["transcription"] = session.transcription_status()
        except Exception as exc:
            out["transcription_error"] = str(exc)
    return out


def whatsapp_pair_start(*, fresh: bool = False) -> dict[str, Any]:
    if not settings.whatsapp_enabled:
        return {"ok": False, "error": "WhatsApp desabilitado (INTEGRATOR_WHATSAPP_ENABLED=false)"}
    if fresh:
        WhatsAppSession.reset()
        remove_session_data()
    try:
        session = WhatsAppSession.get()
        data = session.pair_start()
        return {"ok": True, "data": data}
    except Exception as exc:
        logger.warning("admin whatsapp pair_start: %s", exc)
        return {"ok": False, "error": str(exc)}


def whatsapp_pair_poll() -> dict[str, Any]:
    try:
        session = WhatsAppSession.get()
        data = session.pair_poll()
        return {"ok": True, "data": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def whatsapp_pair_stop() -> dict[str, Any]:
    try:
        session = WhatsAppSession.get()
        data = session.pair_stop()
        return {"ok": True, "data": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def whatsapp_remove_session(*, force: bool = False) -> dict[str, Any]:
    if not has_persisted_session() and not force:
        return {"ok": False, "error": "Nenhuma sessão local", "empty": True}
    try:
        WhatsAppSession.get().shutdown()
    except Exception:
        pass
    WhatsAppSession.reset()
    removed = remove_session_data()
    return {"ok": True, "removed": removed}


def whatsapp_disconnect() -> dict[str, Any]:
    try:
        WhatsAppSession.get().disconnect_worker()
    except Exception:
        WhatsAppSession.reset()
    return {"ok": True}


def hermes_doctor(*, mode: str = "sse") -> dict[str, Any]:
    install = discover_hermes()
    claude = discover_claude_desktop()
    checks = run_all_client_checks(server_name=DEFAULT_SERVER_NAME, mode=mode)
    return {
        "install": {
            "binary": str(install.binary) if install.binary else None,
            "config_path": str(install.config_path),
        },
        "claude_desktop": {
            "config_path": str(claude.config_path),
            "app_found": claude.app_found,
        },
        "checks": [_check_to_dict(c) for c in checks],
        "critical": len(critical_failures(checks)),
    }


def hermes_setup(
    *,
    mode: str = "sse",
    yes: bool = True,
    force: bool = False,
    dry_run: bool = False,
    sse_url: str | None = None,
) -> dict[str, Any]:
    return setup_mcp_clients(
        mode=mode,
        yes=yes,
        force=force,
        dry_run=dry_run,
        sse_url=sse_url,
    )


def list_tools() -> dict[str, Any]:
    meta = list_all_tool_metadata()
    return {"count": len(meta), "tools": meta}


def audit_failures(*, limit: int = 40) -> dict[str, Any]:
    rows = read_audit_failures(limit=limit)
    return {"count": len(rows), "failures": rows}


def open_hermes_install() -> dict[str, Any]:
    try:
        webbrowser.open(HERMES_INSTALL, new=2)
    except Exception:
        pass
    return {"ok": True, "url": HERMES_INSTALL}


def operator_guide_markdown() -> dict[str, Any]:
    path = settings.root_dir / "docs" / "ADMIN_OPERACAO.md"
    if not path.is_file():
        return {"markdown": "# Guia\n\nArquivo docs/ADMIN_OPERACAO.md não encontrado.\n"}
    return {"markdown": path.read_text(encoding="utf-8")}


# ── LinkedIn ──────────────────────────────────────────────────────────────────

def linkedin_status() -> dict[str, Any]:
    from integrator.auth.linkedin_oauth import list_linkedin_accounts

    accounts = list_linkedin_accounts()
    default_id = accounts[0]["id"] if len(accounts) == 1 else (
        next((a["id"] for a in accounts), None)
    )
    return {
        "enabled": settings.linkedin_enabled,
        "client_id_set": bool(settings.linkedin_client_id),
        "client_secret_set": bool(settings.linkedin_client_secret),
        "accounts": accounts,
        "default_account": default_id,
    }


def linkedin_start_oauth(*, account_id: str, public_base: str) -> dict[str, Any]:
    from integrator.auth.linkedin_oauth import LinkedInConfigError, start_linkedin_authorization
    try:
        url = start_linkedin_authorization(public_base=public_base, account_id=account_id)
        return {"ok": True, "auth_url": url}
    except LinkedInConfigError as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def linkedin_disconnect(account_id: str) -> dict[str, Any]:
    from integrator.auth.linkedin_oauth import remove_linkedin_account
    removed = remove_linkedin_account(account_id)
    if removed:
        log_event(logger, "admin.linkedin.disconnected", account_id=account_id)
        return {"ok": True, "removed": account_id}
    return {"ok": False, "error": f"Conta '{account_id}' não encontrada."}
