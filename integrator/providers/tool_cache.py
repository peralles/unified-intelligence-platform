from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

_live_tools_cache: dict[str, dict[str, BaseTool]] = {}


def get_cached_live_tools(account_id: str) -> dict[str, BaseTool] | None:
    return _live_tools_cache.get(account_id)


def set_cached_live_tools(account_id: str, tools: dict[str, BaseTool]) -> None:
    _live_tools_cache[account_id] = tools


def invalidate_live_tools(account_id: str | None = None) -> None:
    if account_id is None:
        _live_tools_cache.clear()
    else:
        _live_tools_cache.pop(account_id, None)
