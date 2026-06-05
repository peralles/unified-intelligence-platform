"""Local admin API and UI for integrator serve-http."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from integrator.admin import handlers as admin_handlers
from integrator.admin.env_file import PERSISTABLE_ENV, bool_env, env_file_path, env_file_writable, upsert_env
from integrator.admin.runtime import RuntimeStore, runtime_file_path
from integrator.config import settings
from integrator.logging_setup import get_logger
from integrator.ops_log import log_event
from integrator.persistence import check_data_persistence

logger = get_logger("admin")

_STATIC = Path(__file__).resolve().parent / "static"
_DIST = _STATIC / "dist"
_RESTART_HINT_KEYS = frozenset({"transcribe_model", "allowlist", "denylist", "confirm_required_tools"})


def _admin_html_path() -> Path:
    built = _DIST / "index.html"
    if built.is_file():
        return built
    return _STATIC / "admin.html"


def _tail_log(name: str, lines: int) -> str:
    log_dir = (settings.log_dir or (settings.root_dir / "data" / "logs")).resolve()
    # Reject names with path separators or dotdot sequences before resolving
    safe_name = name.strip().replace("\\", "/")
    if "/" in safe_name or safe_name.startswith("."):
        return "(nome de arquivo inválido)"
    filename = safe_name if safe_name.endswith(".log") else f"{safe_name}.log"
    path = (log_dir / filename).resolve()
    # Ensure the resolved path stays inside log_dir
    try:
        path.relative_to(log_dir)
    except ValueError:
        return "(acesso negado: caminho fora do diretório de logs)"
    if not path.is_file():
        return f"(arquivo não encontrado: {path.name})"
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"(erro ao ler log: {exc})"
    return "\n".join(content[-lines:])


def _build_state() -> dict[str, Any]:
    store = RuntimeStore()
    runtime = store.load()
    host = settings.service_host
    port = settings.service_port
    # Use 127.0.0.1 in displayed URLs when binding to all interfaces (0.0.0.0 / ::)
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    setup = admin_handlers.setup_status(mode="sse")
    return {
        "service": {
            "host": display_host,
            "port": port,
            "url_admin": f"http://{display_host}:{port}/admin",
            "url_sse": f"http://{display_host}:{port}/sse",
            "url_health": f"http://{display_host}:{port}/health",
            "root_dir": str(settings.root_dir),
        },
        "paths": {
            "runtime_file": str(runtime_file_path()),
            "env_file": str(env_file_path()),
            "whatsapp_session": str(settings.whatsapp_session_path),
            "log_dir": str(settings.log_dir or settings.root_dir / "data" / "logs"),
        },
        "setup": setup,
        "accounts": admin_handlers.list_google_accounts(),
        "mac_service": admin_handlers.mac_service_info(),
        "runtime": runtime,
        "effective": {
            "whatsapp": store.effective_whatsapp(runtime),
            "tools": store.effective_tools(runtime),
            "logging": store.effective_logging(runtime),
        },
        "ignore_numbers_text": store.ignore_numbers_text(runtime),
        "whatsapp_live": admin_handlers.whatsapp_snapshot(),
        "env_defaults": {
            "whatsapp_auto_transcribe": settings.whatsapp_auto_transcribe,
            "transcribe_private_only": settings.whatsapp_transcribe_private_only,
            "transcribe_only_incoming": settings.whatsapp_transcribe_only_incoming,
            "transcribe_model": settings.whatsapp_transcribe_model,
            "transcribe_language": settings.whatsapp_transcribe_language or "",
            "transcribe_prefix": settings.whatsapp_transcribe_prefix,
            "max_message_chars": settings.whatsapp_max_message_chars,
            "max_cached_messages_per_chat": settings.whatsapp_max_cached_messages_per_chat,
            "allowlist": settings.tool_allowlist or "",
            "denylist": settings.tool_denylist or "",
            "confirm_required_tools": settings.confirm_required_tools or "",
            "level": settings.log_level,
            "audit_log_enabled": settings.audit_log_enabled,
            "audit_log_success": settings.audit_log_success,
            "log_tool_success": settings.log_tool_success,
        },
        "notes": {
            "restart_for": (
                "Alterações em modelo MLX, política de tools ou .env exigem "
                "reiniciar o serviço (Admin → Serviço ou serve-http)."
            ),
            "ignore_list": (
                "Números ignorados aplicam-se em tempo real à auto-transcrição "
                "(sem reiniciar)."
            ),
            "cli": "Operação diária via /admin; bootstrap: ./setup.sh ou service install",
        },
        "deployment": {
            "docker": settings.skip_macos_service,
            "oauth_redirect": "/admin/oauth/google/callback",
            "persist_path": "/app/data",
        },
        "persistence": check_data_persistence().to_dict(),
    }


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return {}
    return body if isinstance(body, dict) else {}


async def admin_api_setup_status(_: Request) -> Response:
    mode = "sse"
    return JSONResponse(admin_handlers.setup_status(mode=mode))


async def admin_api_setup_sync(request: Request) -> Response:
    body = await _json_body(request)
    if request.method == "GET":
        return JSONResponse(admin_handlers.sync_deps_status())
    return JSONResponse(admin_handlers.start_sync_deps(verbose=bool(body.get("verbose"))))


async def admin_api_setup_google_steps(_: Request) -> Response:
    return JSONResponse(admin_handlers.open_google_cloud_steps())


async def admin_api_setup_credentials(request: Request) -> Response:
    body = await _json_body(request)
    if "json" in body and isinstance(body["json"], str):
        return JSONResponse(admin_handlers.save_credentials_json(body["json"]))
    index = int(body.get("index", 0))
    return JSONResponse(admin_handlers.import_credentials(from_downloads=True, index=index))


async def admin_api_accounts(_: Request) -> Response:
    return JSONResponse(admin_handlers.list_google_accounts())


async def admin_api_google_login(request: Request) -> Response:
    if request.method == "GET":
        return JSONResponse(admin_handlers.google_login_status())
    body = await _json_body(request)
    account_id = str(body.get("account_id", "pessoal")).strip()
    label = body.get("label")
    return JSONResponse(
        admin_handlers.start_google_login(
            account_id=account_id,
            label=str(label) if label else None,
        )
    )


async def admin_api_google_default(request: Request) -> Response:
    body = await _json_body(request)
    account_id = str(body.get("account_id", "")).strip()
    if not account_id:
        return JSONResponse({"ok": False, "error": "account_id obrigatório"}, status_code=400)
    return JSONResponse(admin_handlers.google_set_default(account_id))


async def admin_api_google_logout(request: Request) -> Response:
    body = await _json_body(request)
    account_id = str(body.get("account_id", "")).strip()
    if not account_id:
        return JSONResponse({"ok": False, "error": "account_id obrigatório"}, status_code=400)
    return JSONResponse(admin_handlers.google_logout(account_id))


async def admin_api_whatsapp_pair(request: Request) -> Response:
    action = request.query_params.get("action", "poll")
    if action == "start":
        body = await _json_body(request) if request.method == "POST" else {}
        fresh = bool(body.get("fresh"))
        result = await asyncio.to_thread(admin_handlers.whatsapp_pair_start, fresh=fresh)
        return JSONResponse(result)
    if action == "stop":
        result = await asyncio.to_thread(admin_handlers.whatsapp_pair_stop)
        return JSONResponse(result)
    result = await asyncio.to_thread(admin_handlers.whatsapp_pair_poll)
    return JSONResponse(result)


async def admin_api_whatsapp_session(request: Request) -> Response:
    if request.method == "DELETE":
        body = await _json_body(request)
        force = bool(body.get("force"))
        return JSONResponse(admin_handlers.whatsapp_remove_session(force=force))
    return JSONResponse(admin_handlers.whatsapp_disconnect())


async def admin_api_service(request: Request) -> Response:
    if request.method == "GET":
        return JSONResponse(admin_handlers.mac_service_info())
    body = await _json_body(request)
    action = str(body.get("action", "status")).strip().lower()
    port = body.get("port")
    port_i = int(port) if port is not None else None
    return JSONResponse(admin_handlers.mac_service_action(action, port=port_i))


async def admin_api_hermes_doctor(_: Request) -> Response:
    mode = "sse"
    return JSONResponse(admin_handlers.hermes_doctor(mode=mode))


async def admin_api_hermes_setup(request: Request) -> Response:
    body = await _json_body(request)
    return JSONResponse(
        admin_handlers.hermes_setup(
            mode=str(body.get("mode", "sse")),
            yes=bool(body.get("yes", True)),
            force=bool(body.get("force")),
            dry_run=bool(body.get("dry_run")),
        )
    )


async def admin_api_hermes_install_link(_: Request) -> Response:
    return JSONResponse(admin_handlers.open_hermes_install())


async def admin_api_tools(_: Request) -> Response:
    return JSONResponse(admin_handlers.list_tools())


async def admin_api_failures(request: Request) -> Response:
    try:
        limit = int(request.query_params.get("limit", "40"))
    except ValueError:
        limit = 40
    limit = max(1, min(limit, 200))
    return JSONResponse(admin_handlers.audit_failures(limit=limit))


def _persist_env_from_effective(effective: dict[str, Any], *, persist: bool) -> list[str]:
    if not persist:
        return []
    env_updates: dict[str, str | None] = {}
    wa = effective.get("whatsapp") or {}
    tools = effective.get("tools") or {}
    logging_cfg = effective.get("logging") or {}

    mapping: dict[str, Any] = {
        "whatsapp_auto_transcribe": wa.get("auto_transcribe"),
        "transcribe_private_only": wa.get("transcribe_private_only"),
        "transcribe_only_incoming": wa.get("transcribe_only_incoming"),
        "transcribe_model": wa.get("transcribe_model"),
        "transcribe_language": wa.get("transcribe_language") or "",
        "transcribe_prefix": wa.get("transcribe_prefix"),
        "max_message_chars": wa.get("max_message_chars"),
        "max_cached_messages_per_chat": wa.get("max_cached_messages_per_chat"),
        "allowlist": tools.get("allowlist") or "",
        "denylist": tools.get("denylist") or "",
        "confirm_required_tools": tools.get("confirm_required_tools") or "",
        "level": logging_cfg.get("level"),
        "audit_log_enabled": logging_cfg.get("audit_log_enabled"),
        "audit_log_success": logging_cfg.get("audit_log_success"),
        "log_tool_success": logging_cfg.get("log_tool_success"),
    }

    touched: list[str] = []
    for runtime_key, env_key in PERSISTABLE_ENV.items():
        if runtime_key not in mapping:
            continue
        value = mapping[runtime_key]
        if isinstance(value, bool):
            env_updates[env_key] = bool_env(value)
        else:
            env_updates[env_key] = str(value)
        touched.append(env_key)

    upsert_env(env_updates)
    return touched


async def admin_index(_: Request) -> Response:
    html_path = _admin_html_path()
    if not html_path.is_file():
        return HTMLResponse("<h1>admin UI ausente</h1>", status_code=500)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


async def admin_api_state(_: Request) -> Response:
    payload = await asyncio.to_thread(_build_state)
    return JSONResponse(payload)


async def admin_oauth_google_start(request: Request) -> Response:
    account_id = request.query_params.get("account_id", "pessoal")
    label = request.query_params.get("label") or None
    from integrator.auth.google_oauth_web import (
        resolve_public_base_url,
        start_oauth_authorization,
    )

    public_base = resolve_public_base_url(
        forwarded_proto=request.headers.get("x-forwarded-proto"),
        forwarded_host=request.headers.get("x-forwarded-host"),
        host=request.headers.get("host"),
    )
    try:
        auth_url = await asyncio.to_thread(
            start_oauth_authorization,
            public_base=public_base,
            account_id=account_id,
            label=label,
        )
    except Exception as exc:
        logger.warning("admin oauth start failed: %s", exc)
        log_event(
            logger,
            "admin.oauth.start_failed",
            level=logging.WARNING,
            error=str(exc),
        )
        return RedirectResponse(
            f"/admin?oauth=error&message={quote(str(exc)[:200])}",
            status_code=302,
        )
    return RedirectResponse(auth_url, status_code=302)


async def admin_oauth_google_callback(request: Request) -> Response:
    from integrator.auth.google_oauth_web import complete_oauth_authorization

    oauth_error = request.query_params.get("error")
    if oauth_error:
        detail = request.query_params.get("error_description") or oauth_error
        return RedirectResponse(
            f"/admin?oauth=error&message={quote(detail[:200])}",
            status_code=302,
        )
    state = request.query_params.get("state", "")
    code = request.query_params.get("code", "")
    if not state or not code:
        return RedirectResponse(
            "/admin?oauth=error&message=Resposta+OAuth+incompleta",
            status_code=302,
        )
    try:
        await asyncio.to_thread(
            complete_oauth_authorization,
            state=state,
            code=code,
        )
    except Exception as exc:
        logger.warning("admin oauth callback failed: %s", exc)
        log_event(
            logger,
            "admin.oauth.callback_failed",
            level=logging.WARNING,
            error=str(exc),
        )
        return RedirectResponse(
            f"/admin?oauth=error&message={quote(str(exc)[:200])}",
            status_code=302,
        )
    return RedirectResponse("/admin?oauth=ok", status_code=302)


async def admin_api_config(request: Request) -> Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "corpo inválido"}, status_code=400)

    store = RuntimeStore()
    patch: dict[str, Any] = {}
    for section in ("whatsapp", "tools", "logging", "service"):
        if section in body and isinstance(body[section], dict):
            patch[section] = body[section]

    ignore_text = body.get("ignore_numbers_text")
    if isinstance(ignore_text, str):
        numbers = store.parse_ignore_lines(ignore_text)
        patch.setdefault("whatsapp", {})["transcribe_ignore_numbers"] = numbers

    updated = store.patch(patch) if patch else store.load()
    effective = {
        "whatsapp": store.effective_whatsapp(updated),
        "tools": store.effective_tools(updated),
        "logging": store.effective_logging(updated),
    }
    persist_env = bool(body.get("persist_env", True))
    env_keys = _persist_env_from_effective(effective, persist=persist_env)
    env_persist_skipped = persist_env and not env_file_writable()

    restart_hints: list[str] = []
    if persist_env:
        for key in _RESTART_HINT_KEYS:
            if key in (body.get("whatsapp") or {}) or key in (body.get("tools") or {}):
                restart_hints.append(key)

    log_event(
        logger,
        "admin.config.saved",
        ignore_count=len(
            (updated.get("whatsapp") or {}).get("transcribe_ignore_numbers") or []
        ),
        persist_env=persist_env,
        env_persist_skipped=env_persist_skipped,
        env_keys=len(env_keys),
    )
    return JSONResponse(
        {
            "ok": True,
            "runtime": updated,
            "effective": effective,
            "ignore_numbers_text": store.ignore_numbers_text(updated),
            "env_updated": env_keys,
            "env_persist_skipped": env_persist_skipped,
            "restart_recommended": bool(restart_hints),
            "restart_hints": restart_hints,
        }
    )


async def admin_api_logs(request: Request) -> Response:
    name = request.query_params.get("file", "integrator")
    try:
        lines = int(request.query_params.get("lines", "150"))
    except ValueError:
        lines = 150
    lines = max(10, min(lines, 2000))
    return JSONResponse({"ok": True, "file": name, "text": _tail_log(name, lines)})


def admin_routes() -> list[Route | Mount]:
    routes: list[Route | Mount] = [
        Route("/admin", endpoint=admin_index, methods=["GET"]),
        Route("/admin/api/state", endpoint=admin_api_state, methods=["GET"]),
        Route("/admin/api/config", endpoint=admin_api_config, methods=["PUT"]),
        Route("/admin/api/logs", endpoint=admin_api_logs, methods=["GET"]),
        Route("/admin/api/setup/status", endpoint=admin_api_setup_status, methods=["GET"]),
        Route("/admin/api/setup/sync", endpoint=admin_api_setup_sync, methods=["GET", "POST"]),
        Route("/admin/api/setup/google-steps", endpoint=admin_api_setup_google_steps, methods=["POST"]),
        Route("/admin/api/setup/credentials", endpoint=admin_api_setup_credentials, methods=["POST"]),
        Route("/admin/api/accounts", endpoint=admin_api_accounts, methods=["GET"]),
        Route("/admin/api/google/login", endpoint=admin_api_google_login, methods=["GET", "POST"]),
        Route("/admin/oauth/google/start", endpoint=admin_oauth_google_start, methods=["GET"]),
        Route("/admin/oauth/google/callback", endpoint=admin_oauth_google_callback, methods=["GET"]),
        Route("/admin/api/google/default", endpoint=admin_api_google_default, methods=["POST"]),
        Route("/admin/api/google/logout", endpoint=admin_api_google_logout, methods=["POST"]),
        Route("/admin/api/whatsapp/pair", endpoint=admin_api_whatsapp_pair, methods=["GET", "POST"]),
        Route("/admin/api/whatsapp/session", endpoint=admin_api_whatsapp_session, methods=["POST", "DELETE"]),
        Route("/admin/api/service", endpoint=admin_api_service, methods=["GET", "POST"]),
        Route("/admin/api/hermes/doctor", endpoint=admin_api_hermes_doctor, methods=["GET"]),
        Route("/admin/api/hermes/setup", endpoint=admin_api_hermes_setup, methods=["POST"]),
        Route("/admin/api/hermes/install", endpoint=admin_api_hermes_install_link, methods=["POST"]),
        Route("/admin/api/tools", endpoint=admin_api_tools, methods=["GET"]),
        Route("/admin/api/failures", endpoint=admin_api_failures, methods=["GET"]),
    ]
    assets = _DIST / "assets"
    if assets.is_dir():
        routes.append(
            Mount(
                "/admin/assets",
                app=StaticFiles(directory=assets),
                name="admin_assets",
            )
        )
    return routes
