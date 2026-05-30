from __future__ import annotations

import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum

from integrator.accounts.registry import list_accounts
from integrator.config import settings
from integrator.hermes.config_merge import DEFAULT_SERVER_NAME, get_mcp_server_entry
from integrator.hermes.discovery import HermesInstall, discover_hermes
from integrator.onboarding.preflight import repo_deps_ok


class CheckStatus(str, Enum):
    OK = "OK"
    FAIL = "FALTA"
    WARN = "AVISO"


@dataclass
class CheckResult:
    id: str
    label: str
    status: CheckStatus
    detail: str
    hint: str | None = None


def _repo_deps_ok() -> bool:
    return repo_deps_ok()


def _sse_service_healthy(port: int | None = None) -> bool:
    p = port if port is not None else settings.service_port
    url = f"http://{settings.service_host}:{p}/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def run_checks(
    *,
    server_name: str = DEFAULT_SERVER_NAME,
    mode: str = "stdio",
) -> list[CheckResult]:
    install = discover_hermes()
    results: list[CheckResult] = []

    uv = shutil.which("uv")
    results.append(
        CheckResult(
            id="uv",
            label="uv no PATH",
            status=CheckStatus.OK if uv else CheckStatus.FAIL,
            detail=uv or "não encontrado",
            hint=None if uv else "https://docs.astral.sh/uv/",
        )
    )

    deps_ok = _repo_deps_ok()
    results.append(
        CheckResult(
            id="deps",
            label="Dependências do repo",
            status=CheckStatus.OK if deps_ok else CheckStatus.FAIL,
            detail=".venv ou uv run integrator status",
            hint=None if deps_ok else "uv sync --all-extras",
        )
    )

    creds = settings.credentials_path.is_file()
    results.append(
        CheckResult(
            id="credentials",
            label="OAuth client Google",
            status=CheckStatus.OK if creds else CheckStatus.FAIL,
            detail=str(settings.credentials_path),
            hint=None if creds else "Coloque credentials.json em credentials/ (ver README)",
        )
    )

    accounts = list_accounts()
    with_token = [a for a in accounts if a.has_token]
    oauth_ok = len(with_token) > 0
    results.append(
        CheckResult(
            id="oauth",
            label="Conta Google autenticada",
            status=CheckStatus.OK if oauth_ok else CheckStatus.FAIL,
            detail=f"{len(with_token)} com token" if accounts else "nenhuma conta",
            hint=None if oauth_ok else "integrator login pessoal",
        )
    )

    hermes_ok = install.binary is not None
    results.append(
        CheckResult(
            id="hermes",
            label="Hermes instalado",
            status=CheckStatus.OK if hermes_ok else CheckStatus.WARN,
            detail=str(install.binary) if install.binary else "hermes não está no PATH",
            hint=None
            if hermes_ok
            else "Instale o Hermes; depois: integrator hermes setup",
        )
    )

    config_parent = install.config_path.parent
    config_writable = config_parent.exists() or config_parent == install.home
    try:
        config_parent.mkdir(parents=True, exist_ok=True)
        config_writable = True
    except OSError:
        config_writable = False

    results.append(
        CheckResult(
            id="config",
            label="Config Hermes",
            status=CheckStatus.OK if config_writable else CheckStatus.FAIL,
            detail=str(install.config_path),
            hint=None if config_writable else f"Não foi possível criar {config_parent}",
        )
    )

    existing = get_mcp_server_entry(install.config_path, server_name)
    if existing:
        results.append(
            CheckResult(
                id="mcp_entry",
                label=f"Entrada MCP '{server_name}'",
                status=CheckStatus.WARN,
                detail="já configurada",
                hint="integrator hermes setup --yes para substituir",
            )
        )
    else:
        results.append(
            CheckResult(
                id="mcp_entry",
                label=f"Entrada MCP '{server_name}'",
                status=CheckStatus.OK,
                detail="ainda não configurada",
                hint="integrator hermes setup",
            )
        )

    if mode == "sse":
        from integrator.service.macos import is_macos, plist_path, is_loaded

        if not is_macos():
            results.append(
                CheckResult(
                    id="sse_platform",
                    label="Serviço SSE (macOS)",
                    status=CheckStatus.FAIL,
                    detail="modo sse requer macOS",
                    hint="Use --mode stdio ou integrator serve no Hermes",
                )
            )
        else:
            plist = plist_path().is_file()
            loaded = is_loaded() if plist else False
            healthy = _sse_service_healthy() if loaded else False
            if healthy:
                st = CheckStatus.OK
                detail = f"health OK em :{settings.service_port}"
            elif loaded:
                st = CheckStatus.WARN
                detail = "serviço carregado mas /health falhou"
            elif plist:
                st = CheckStatus.WARN
                detail = "plist existe, serviço parado"
            else:
                st = CheckStatus.FAIL
                detail = "serviço não instalado"
            results.append(
                CheckResult(
                    id="sse_service",
                    label="Serviço HTTP/SSE",
                    status=st,
                    detail=detail,
                    hint="integrator service install && integrator service start",
                )
            )

    return results


def critical_failures(results: list[CheckResult]) -> list[CheckResult]:
    """Falhas que impedem o integrador MCP de funcionar (Hermes opcional)."""
    critical_ids = {"uv", "deps", "credentials", "oauth", "config"}
    return [r for r in results if r.id in critical_ids and r.status == CheckStatus.FAIL]


def _friendly_hint(result: CheckResult) -> str | None:
    if result.id == "credentials":
        return "integrator init"
    if result.id == "oauth":
        return "integrator init"
    if result.id == "deps":
        return "integrator init"
    if result.id == "uv":
        return "integrator init"
    if result.id == "mcp_entry" and result.status == CheckStatus.OK:
        return "integrator init"
    return result.hint


def format_report(
    results: list[CheckResult],
    install: HermesInstall,
    *,
    friendly: bool = True,
    verbose: bool = False,
) -> str:
    lines = ["Diagnóstico Hermes + integrador\n"]
    for r in results:
        lines.append(f"  [{r.status.value}] {r.label}: {r.detail}")
        hint = _friendly_hint(r) if friendly else r.hint
        if hint:
            lines.append(f"         → {hint}")
    if verbose:
        lines.append(f"\nConfig Hermes: {install.config_path}")
        if install.binary:
            lines.append(f"Binário: {install.binary}")
        else:
            lines.append(
                "Binário: — (YAML pode ser gravado; ative com nova sessão Hermes após instalar)"
            )
    crit = critical_failures(results)
    if crit:
        if friendly:
            lines.append("\nCorrigir tudo automaticamente: integrator init")
        else:
            lines.append("\nCorrija os itens FALTA antes de integrator hermes setup.")
    else:
        if friendly:
            lines.append("\nTudo certo. Se ainda não ligou ao Hermes: integrator init")
        else:
            lines.append("\nPronto para: integrator hermes setup")
    if friendly:
        lines.append("No Hermes: conversa nova ou /reload-mcp")
    else:
        lines.append(
            "Após setup: nova sessão Hermes ou /reload-mcp; modelo/API: hermes model"
        )
    return "\n".join(lines)


def doctor_exit_code(results: list[CheckResult]) -> int:
    return 1 if critical_failures(results) else 0
