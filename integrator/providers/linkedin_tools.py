"""LinkedIn MCP tools — 8 tools via ugcPosts + socialActions API."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import quote

from integrator.auth.linkedin_oauth import LinkedInAuthError, load_linkedin_token
from integrator.config import settings

LINKEDIN_TOOL_NAMES = frozenset({
    "get_linkedin_profile",
    "share_linkedin_post",
    "share_linkedin_article",
    "get_linkedin_my_posts",
    "delete_linkedin_post",
    "comment_linkedin_post",
    "like_linkedin_post",
    "unlike_linkedin_post",
})

_LINKEDIN_API = "https://api.linkedin.com"
_RESTLI_HEADERS = {
    "X-Restli-Protocol-Version": "2.0.0",
    "Content-Type": "application/json",
}


def list_linkedin_tool_metadata() -> list[dict[str, Any]]:
    from integrator.security.policy import enrich_linkedin_tool_schema
    return [
        enrich_linkedin_tool_schema(m)
        for m in _raw_metadata()
        if settings.linkedin_enabled
    ]


def _raw_metadata() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_linkedin_profile",
            "description": (
                "Obtém o perfil LinkedIn do usuário autenticado: nome, headline, "
                "foto, email e ID da conta."
            ),
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "share_linkedin_post",
            "description": (
                "Publica uma postagem de texto no LinkedIn. "
                "Visibilidade pública por padrão. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Texto da postagem (máx. 3000 caracteres).",
                    },
                    "visibility": {
                        "type": "string",
                        "enum": ["PUBLIC", "CONNECTIONS"],
                        "description": "Visibilidade: PUBLIC ou CONNECTIONS. Padrão: PUBLIC.",
                    },
                },
                "required": ["text"],
            },
        },
        {
            "name": "share_linkedin_article",
            "description": (
                "Compartilha um link/artigo no LinkedIn com título, descrição e URL. "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Comentário introdutório da publicação.",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL do artigo ou link a compartilhar.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Título do artigo (opcional).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Descrição do artigo (opcional).",
                    },
                    "visibility": {
                        "type": "string",
                        "enum": ["PUBLIC", "CONNECTIONS"],
                        "description": "Visibilidade: PUBLIC ou CONNECTIONS. Padrão: PUBLIC.",
                    },
                },
                "required": ["text", "url"],
            },
        },
        {
            "name": "get_linkedin_my_posts",
            "description": (
                "Lista as postagens recentes do usuário autenticado no LinkedIn."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Número de postagens a retornar (padrão 10, máx. 50).",
                    },
                },
            },
        },
        {
            "name": "delete_linkedin_post",
            "description": (
                "Deleta uma postagem própria do LinkedIn pelo URN. "
                "Use get_linkedin_my_posts para obter o URN. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "post_urn": {
                        "type": "string",
                        "description": "URN da postagem (ex: urn:li:ugcPost:7012345678901234567).",
                    },
                },
                "required": ["post_urn"],
            },
        },
        {
            "name": "comment_linkedin_post",
            "description": (
                "Comenta em uma postagem do LinkedIn pelo URN. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "post_urn": {
                        "type": "string",
                        "description": "URN da postagem.",
                    },
                    "text": {
                        "type": "string",
                        "description": "Texto do comentário.",
                    },
                },
                "required": ["post_urn", "text"],
            },
        },
        {
            "name": "like_linkedin_post",
            "description": (
                "Reage (curtida) a uma postagem do LinkedIn pelo URN. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "post_urn": {
                        "type": "string",
                        "description": "URN da postagem.",
                    },
                },
                "required": ["post_urn"],
            },
        },
        {
            "name": "unlike_linkedin_post",
            "description": (
                "Remove a curtida de uma postagem do LinkedIn. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "post_urn": {
                        "type": "string",
                        "description": "URN da postagem.",
                    },
                },
                "required": ["post_urn"],
            },
        },
    ]


def _api_headers(access_token: str) -> dict[str, str]:
    return {
        **_RESTLI_HEADERS,
        "Authorization": f"Bearer {access_token}",
    }


def _api_get(url: str, access_token: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=_api_headers(access_token))
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LinkedInAuthError(
            f"[integrator] LinkedIn API error {exc.code}: {body[:300]}"
        ) from exc


def _api_post(url: str, access_token: str, body: dict[str, Any]) -> dict[str, Any] | None:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers=_api_headers(access_token),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body_txt = exc.read().decode("utf-8", errors="replace")
        raise LinkedInAuthError(
            f"[integrator] LinkedIn API error {exc.code}: {body_txt[:300]}"
        ) from exc


def _api_delete(url: str, access_token: str) -> None:
    req = urllib.request.Request(
        url,
        headers=_api_headers(access_token),
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LinkedInAuthError(
            f"[integrator] LinkedIn API error {exc.code}: {body[:300]}"
        ) from exc


def _person_urn(token: dict[str, Any]) -> str:
    sub = token.get("sub")
    if not sub:
        raise LinkedInAuthError(
            "[integrator] Sub (person ID) não disponível no token. Reconecte a conta."
        )
    # sub from OpenID Connect is the raw person ID (not the URN)
    if sub.startswith("urn:li:person:"):
        return sub
    return f"urn:li:person:{sub}"


def invoke_linkedin_tool(
    name: str,
    account_id: str,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    args = arguments or {}
    token = load_linkedin_token(account_id)
    access_token = token["access_token"]

    if name == "get_linkedin_profile":
        profile = _api_get(f"{_LINKEDIN_API}/v2/userinfo", access_token)
        return {
            "sub": profile.get("sub"),
            "name": profile.get("name"),
            "given_name": profile.get("given_name"),
            "family_name": profile.get("family_name"),
            "email": profile.get("email"),
            "picture": profile.get("picture"),
            "locale": profile.get("locale"),
        }

    if name == "get_linkedin_my_posts":
        count = max(1, min(int(args.get("count", 10)), 50))
        person_urn = _person_urn(token)
        encoded_urn = quote(person_urn, safe="")
        url = (
            f"{_LINKEDIN_API}/v2/ugcPosts"
            f"?q=authors&authors=List({encoded_urn})&count={count}"
        )
        data = _api_get(url, access_token)
        posts = []
        for element in (data.get("elements") or []):
            content = (
                element.get("specificContent", {})
                .get("com.linkedin.ugc.ShareContent", {})
            )
            posts.append({
                "urn": element.get("id"),
                "text": content.get("shareCommentary", {}).get("text"),
                "created": element.get("created", {}).get("time"),
                "lifecycle_state": element.get("lifecycleState"),
            })
        return {"count": len(posts), "posts": posts}

    if name == "share_linkedin_post":
        text = str(args.get("text", "")).strip()
        if not text:
            raise ValueError("[integrator] text é obrigatório.")
        if len(text) > 3000:
            raise ValueError("[integrator] Texto excede 3000 caracteres.")
        visibility = str(args.get("visibility", "PUBLIC")).upper()
        if visibility not in ("PUBLIC", "CONNECTIONS"):
            visibility = "PUBLIC"
        person_urn = _person_urn(token)
        body = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": visibility,
            },
        }
        result = _api_post(f"{_LINKEDIN_API}/v2/ugcPosts", access_token, body)
        return {
            "ok": True,
            "post_urn": (result or {}).get("id"),
            "text": text[:80] + ("…" if len(text) > 80 else ""),
        }

    if name == "share_linkedin_article":
        text = str(args.get("text", "")).strip()
        url = str(args.get("url", "")).strip()
        if not text or not url:
            raise ValueError("[integrator] text e url são obrigatórios.")
        title = str(args.get("title", "")).strip() or None
        description = str(args.get("description", "")).strip() or None
        visibility = str(args.get("visibility", "PUBLIC")).upper()
        if visibility not in ("PUBLIC", "CONNECTIONS"):
            visibility = "PUBLIC"
        person_urn = _person_urn(token)
        media: dict[str, Any] = {
            "status": "READY",
            "originalUrl": url,
        }
        if title:
            media["title"] = {"text": title}
        if description:
            media["description"] = {"text": description}
        body = {
            "author": person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "ARTICLE",
                    "media": [media],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": visibility,
            },
        }
        result = _api_post(f"{_LINKEDIN_API}/v2/ugcPosts", access_token, body)
        return {
            "ok": True,
            "post_urn": (result or {}).get("id"),
            "url": url,
        }

    if name == "delete_linkedin_post":
        post_urn = str(args.get("post_urn", "")).strip()
        if not post_urn:
            raise ValueError("[integrator] post_urn é obrigatório.")
        encoded = quote(post_urn, safe="")
        _api_delete(f"{_LINKEDIN_API}/v2/ugcPosts/{encoded}", access_token)
        return {"ok": True, "deleted_urn": post_urn}

    if name == "comment_linkedin_post":
        post_urn = str(args.get("post_urn", "")).strip()
        text = str(args.get("text", "")).strip()
        if not post_urn or not text:
            raise ValueError("[integrator] post_urn e text são obrigatórios.")
        person_urn = _person_urn(token)
        encoded = quote(post_urn, safe="")
        body = {
            "actor": person_urn,
            "message": {"text": text},
        }
        result = _api_post(
            f"{_LINKEDIN_API}/v2/socialActions/{encoded}/comments",
            access_token,
            body,
        )
        return {"ok": True, "comment_urn": (result or {}).get("id")}

    if name == "like_linkedin_post":
        post_urn = str(args.get("post_urn", "")).strip()
        if not post_urn:
            raise ValueError("[integrator] post_urn é obrigatório.")
        person_urn = _person_urn(token)
        encoded = quote(post_urn, safe="")
        _api_post(
            f"{_LINKEDIN_API}/v2/socialActions/{encoded}/likes",
            access_token,
            {"actor": person_urn},
        )
        return {"ok": True, "liked_urn": post_urn}

    if name == "unlike_linkedin_post":
        post_urn = str(args.get("post_urn", "")).strip()
        if not post_urn:
            raise ValueError("[integrator] post_urn é obrigatório.")
        person_urn = _person_urn(token)
        encoded_post = quote(post_urn, safe="")
        encoded_person = quote(person_urn, safe="")
        _api_delete(
            f"{_LINKEDIN_API}/v2/socialActions/{encoded_post}/likes/{encoded_person}",
            access_token,
        )
        return {"ok": True, "unliked_urn": post_urn}

    raise KeyError(f"Tool desconhecida: {name}")
