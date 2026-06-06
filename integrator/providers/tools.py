from __future__ import annotations

from typing import Any

from integrator.auth.google_oauth import GoogleAuthError
from integrator.config import settings
from integrator.providers.google_calendar_extra import (
    CALENDAR_EXTRA_TOOL_NAMES,
    invoke_calendar_extra_tool,
    list_calendar_extra_tool_metadata,
)
from integrator.providers.google_contacts_extra import (
    CONTACTS_EXTRA_TOOL_NAMES,
    invoke_contacts_extra_tool,
    list_contacts_extra_tool_metadata,
)
from integrator.providers.google_gmail_extra import (
    GMAIL_EXTRA_TOOL_NAMES,
    invoke_gmail_extra_tool,
    list_gmail_extra_tool_metadata,
)
from integrator.providers.google_tools import (
    invoke_google_tool,
    list_google_tool_metadata,
)
from integrator.providers.linkedin_tools import (
    LINKEDIN_TOOL_NAMES,
    invoke_linkedin_tool,
    list_linkedin_tool_metadata,
)
from integrator.providers.whatsapp_tools import (
    WHATSAPP_TOOL_NAMES,
    invoke_whatsapp_tool,
    list_whatsapp_tool_metadata,
)

GOOGLE_TOOL_COUNT = 12
GMAIL_EXTRA_TOOL_COUNT = len(GMAIL_EXTRA_TOOL_NAMES)
CALENDAR_EXTRA_TOOL_COUNT = len(CALENDAR_EXTRA_TOOL_NAMES)
CONTACTS_EXTRA_TOOL_COUNT = len(CONTACTS_EXTRA_TOOL_NAMES)
WHATSAPP_TOOL_COUNT = len(WHATSAPP_TOOL_NAMES)
LINKEDIN_TOOL_COUNT = len(LINKEDIN_TOOL_NAMES)
TOTAL_TOOL_COUNT = (
    GOOGLE_TOOL_COUNT
    + GMAIL_EXTRA_TOOL_COUNT
    + CALENDAR_EXTRA_TOOL_COUNT
    + CONTACTS_EXTRA_TOOL_COUNT
    + WHATSAPP_TOOL_COUNT
    + LINKEDIN_TOOL_COUNT
)


def list_all_tool_metadata() -> list[dict[str, Any]]:
    from integrator.security.policy import filter_tool_metadata

    tools = [
        *list_google_tool_metadata(),
        *filter_tool_metadata(list_gmail_extra_tool_metadata()),
        *filter_tool_metadata(list_calendar_extra_tool_metadata()),
        *filter_tool_metadata(list_contacts_extra_tool_metadata()),
    ]
    if settings.whatsapp_enabled:
        tools = [*tools, *list_whatsapp_tool_metadata()]
    if settings.linkedin_enabled:
        tools = [*tools, *list_linkedin_tool_metadata()]
    return tools


def is_whatsapp_tool(name: str) -> bool:
    return name in WHATSAPP_TOOL_NAMES


def is_linkedin_tool(name: str) -> bool:
    return name in LINKEDIN_TOOL_NAMES


def _invoke_google_extra_tool(
    name: str,
    arguments: dict[str, Any] | None,
    *,
    invoke_fn: Any,
) -> str:
    import json
    import time

    from integrator.accounts.registry import AccountNotFoundError, resolve_account_id
    from integrator.providers.google_tools import strip_control_args
    from integrator.security.audit import log_tool_invocation
    from integrator.security.policy import (
        ConfirmationRequiredError,
        ToolPolicyError,
        check_confirmation,
        is_tool_allowed,
    )

    started = time.perf_counter()
    account_id: str | None = None

    def _finish(
        *,
        success: bool,
        error_kind: str | None = None,
        blocked: bool = False,
    ) -> None:
        log_tool_invocation(
            name,
            success=success,
            duration_ms=(time.perf_counter() - started) * 1000,
            error_kind=error_kind,
            blocked=blocked,
            account_id=account_id,
        )

    if not is_tool_allowed(name):
        _finish(success=False, error_kind="tool_policy", blocked=True)
        raise ToolPolicyError(f"Tool '{name}' não permitida pela política.")
    try:
        check_confirmation(name, arguments)
    except ConfirmationRequiredError:
        _finish(success=False, error_kind="confirmation_required", blocked=True)
        raise
    args, explicit_account = strip_control_args(arguments)
    try:
        account_id = resolve_account_id(explicit_account)
    except AccountNotFoundError as exc:
        _finish(success=False, error_kind="account", blocked=True)
        raise ToolPolicyError(str(exc)) from exc
    try:
        result = invoke_fn(name, account_id, args)
    except GoogleAuthError as exc:
        _finish(success=False, error_kind="auth")
        raise ToolPolicyError(f"[integrator] Autenticação necessária: {exc}") from exc
    except Exception:
        _finish(success=False, error_kind="execution")
        raise
    _finish(success=True)
    return json.dumps(result, ensure_ascii=False, default=str)


def _invoke_gmail_extra_tool(name: str, arguments: dict[str, Any] | None) -> str:
    return _invoke_google_extra_tool(
        name, arguments, invoke_fn=invoke_gmail_extra_tool
    )


def _invoke_linkedin_tool(name: str, arguments: dict[str, Any] | None) -> str:
    import json
    import time

    from integrator.auth.linkedin_oauth import LinkedInAuthError
    from integrator.security.audit import log_tool_invocation
    from integrator.security.policy import (
        ConfirmationRequiredError,
        ToolPolicyError,
        check_confirmation,
        is_tool_allowed,
        strip_control_args,
    )

    started = time.perf_counter()
    account_id: str | None = None

    def _finish(
        *,
        success: bool,
        error_kind: str | None = None,
        blocked: bool = False,
    ) -> None:
        log_tool_invocation(
            name,
            success=success,
            duration_ms=(time.perf_counter() - started) * 1000,
            error_kind=error_kind,
            blocked=blocked,
            account_id=account_id,
        )

    if not is_tool_allowed(name):
        _finish(success=False, error_kind="tool_policy", blocked=True)
        raise ToolPolicyError(f"Tool '{name}' não permitida pela política.")
    try:
        check_confirmation(name, arguments)
    except ConfirmationRequiredError:
        _finish(success=False, error_kind="confirmation_required", blocked=True)
        raise

    args, explicit_account = strip_control_args(arguments)
    account_id = (explicit_account or "default").strip().lower() or "default"

    try:
        result = invoke_linkedin_tool(name, account_id, args)
    except LinkedInAuthError as exc:
        _finish(success=False, error_kind="auth")
        raise ToolPolicyError(f"[integrator] Autenticação LinkedIn necessária: {exc}") from exc
    except Exception:
        _finish(success=False, error_kind="execution")
        raise
    _finish(success=True)
    return json.dumps(result, ensure_ascii=False, default=str)


def invoke_tool(name: str, arguments: dict[str, Any] | None) -> str:
    if is_whatsapp_tool(name):
        return invoke_whatsapp_tool(name, arguments)
    if is_linkedin_tool(name):
        return _invoke_linkedin_tool(name, arguments)
    if name in GMAIL_EXTRA_TOOL_NAMES:
        return _invoke_gmail_extra_tool(name, arguments)
    if name in CALENDAR_EXTRA_TOOL_NAMES:
        return _invoke_google_extra_tool(
            name, arguments, invoke_fn=invoke_calendar_extra_tool
        )
    if name in CONTACTS_EXTRA_TOOL_NAMES:
        return _invoke_google_extra_tool(
            name, arguments, invoke_fn=invoke_contacts_extra_tool
        )
    return invoke_google_tool(name, arguments)
