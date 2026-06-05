from __future__ import annotations

from typing import Any

from googleapiclient.discovery import build

from integrator.auth.google_oauth import load_google_credentials

CONTACTS_EXTRA_TOOL_NAMES = frozenset({
    "search_google_contacts",
    "get_google_contact",
    "create_google_contact",
    "update_google_contact",
    "delete_google_contact",
})

_PERSON_FIELDS = "names,emailAddresses,phoneNumbers,organizations,metadata"
_SEARCH_READ_MASK = "names,emailAddresses,phoneNumbers,organizations"


def list_contacts_extra_tool_metadata() -> list[dict[str, Any]]:
    return [
        {
            "name": "search_google_contacts",
            "description": (
                "Busca ou lista contatos Google (People API). Com query, usa busca por "
                "nome/e-mail/telefone; sem query, lista conexões recentes."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca (nome, e-mail ou telefone).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Máximo de resultados (padrão 25, máx. 100).",
                    },
                },
            },
        },
        {
            "name": "get_google_contact",
            "description": (
                "Obtém um contato pelo resourceName (ex: people/c123…). "
                "Use search_google_contacts para descobrir o ID."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "resource_name": {
                        "type": "string",
                        "description": "Resource name do contato (people/…).",
                    },
                },
                "required": ["resource_name"],
            },
        },
        {
            "name": "create_google_contact",
            "description": (
                "Cria contato Google. Pelo menos given_name ou e-mail/telefone. "
                "Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "given_name": {"type": "string"},
                    "family_name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "organization": {"type": "string"},
                },
            },
        },
        {
            "name": "update_google_contact",
            "description": (
                "Atualiza contato existente (campos omitidos permanecem). "
                "Requer resource_name e etag de get_google_contact. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "resource_name": {"type": "string"},
                    "etag": {"type": "string"},
                    "given_name": {"type": "string"},
                    "family_name": {"type": "string"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "organization": {"type": "string"},
                },
                "required": ["resource_name", "etag"],
            },
        },
        {
            "name": "delete_google_contact",
            "description": (
                "Remove contato permanentemente. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "resource_name": {
                        "type": "string",
                        "description": "Resource name do contato (people/…).",
                    },
                },
                "required": ["resource_name"],
            },
        },
    ]


def _people_service(account_id: str):
    credentials = load_google_credentials(account_id=account_id, interactive=False)
    return build("people", "v1", credentials=credentials, cache_discovery=False)


def _clamp_limit(raw: Any, *, default: int = 25, maximum: int = 100) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(value, maximum))


def _normalize_person(person: dict[str, Any]) -> dict[str, Any]:
    names = person.get("names") or []
    primary_name = names[0] if names else {}
    emails = [
        str(item.get("value"))
        for item in (person.get("emailAddresses") or [])
        if item.get("value")
    ]
    phones = [
        str(item.get("value"))
        for item in (person.get("phoneNumbers") or [])
        if item.get("value")
    ]
    orgs = [
        {
            "name": item.get("name"),
            "title": item.get("title"),
        }
        for item in (person.get("organizations") or [])
        if item.get("name") or item.get("title")
    ]
    return {
        "resource_name": person.get("resourceName"),
        "etag": person.get("etag"),
        "display_name": primary_name.get("displayName")
        or primary_name.get("givenName")
        or (emails[0] if emails else None),
        "given_name": primary_name.get("givenName"),
        "family_name": primary_name.get("familyName"),
        "emails": emails,
        "phones": phones,
        "organizations": orgs,
    }


def _contact_body_from_args(args: dict[str, Any]) -> dict[str, Any]:
    body: dict[str, Any] = {}
    given = str(args.get("given_name") or "").strip()
    family = str(args.get("family_name") or "").strip()
    email = str(args.get("email") or "").strip()
    phone = str(args.get("phone") or "").strip()
    organization = str(args.get("organization") or "").strip()

    if given or family:
        name_entry: dict[str, str] = {}
        if given:
            name_entry["givenName"] = given
        if family:
            name_entry["familyName"] = family
        body["names"] = [name_entry]
    if email:
        body["emailAddresses"] = [{"value": email}]
    if phone:
        body["phoneNumbers"] = [{"value": phone}]
    if organization:
        body["organizations"] = [{"name": organization}]
    return body


def invoke_contacts_extra_tool(
    name: str,
    account_id: str,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    args = arguments or {}
    service = _people_service(account_id)

    if name == "search_google_contacts":
        query = str(args.get("query") or "").strip()
        limit = _clamp_limit(args.get("limit"))
        if query:
            response = (
                service.people()
                .searchContacts(
                    query=query,
                    readMask=_SEARCH_READ_MASK,
                    pageSize=limit,
                )
                .execute()
            )
            people = [
                item.get("person") or {}
                for item in (response.get("results") or [])
                if item.get("person")
            ]
        else:
            response = (
                service.people()
                .connections()
                .list(
                    resourceName="people/me",
                    pageSize=limit,
                    personFields=_PERSON_FIELDS,
                )
                .execute()
            )
            people = response.get("connections") or []
        contacts = [_normalize_person(person) for person in people]
        return {"query": query or None, "count": len(contacts), "contacts": contacts}

    if name == "get_google_contact":
        resource_name = str(args.get("resource_name") or "").strip()
        if not resource_name:
            raise ValueError("[integrator] resource_name é obrigatório.")
        person = (
            service.people()
            .get(
                resourceName=resource_name,
                personFields=_PERSON_FIELDS,
            )
            .execute()
        )
        return {"contact": _normalize_person(person)}

    if name == "create_google_contact":
        body = _contact_body_from_args(args)
        if not body:
            raise ValueError(
                "[integrator] Informe given_name, family_name, email, phone ou organization."
            )
        person = service.people().createContact(body=body).execute()
        return {"contact": _normalize_person(person)}

    if name == "update_google_contact":
        resource_name = str(args.get("resource_name") or "").strip()
        etag = str(args.get("etag") or "").strip()
        if not resource_name or not etag:
            raise ValueError("[integrator] resource_name e etag são obrigatórios.")
        patch = _contact_body_from_args(args)
        if not patch:
            raise ValueError("[integrator] Informe ao menos um campo para atualizar.")
        person = (
            service.people()
            .updateContact(
                resourceName=resource_name,
                updatePersonFields=",".join(patch.keys()),
                body={**patch, "etag": etag},
            )
            .execute()
        )
        return {"contact": _normalize_person(person)}

    if name == "delete_google_contact":
        resource_name = str(args.get("resource_name") or "").strip()
        if not resource_name:
            raise ValueError("[integrator] resource_name é obrigatório.")
        service.people().deleteContact(resourceName=resource_name).execute()
        return {"resource_name": resource_name, "deleted": True}

    raise KeyError(f"Tool desconhecida: {name}")
