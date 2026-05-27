from __future__ import annotations

import base64
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from integrator.auth.google_oauth import load_google_credentials
from langchain_google_community.gmail.utils import build_gmail_service

GMAIL_EXTRA_TOOL_NAMES = frozenset({
    "modify_gmail_labels",
    "reply_gmail_message",
    "list_gmail_attachments",
    "get_gmail_attachment",
    "trash_gmail_message",
    "star_gmail_message",
    "mark_gmail_read",
    "mark_gmail_unread",
    "restore_gmail_message",
    "list_gmail_labels",
    "create_gmail_draft_api",
    "send_gmail_draft",
})


def list_gmail_extra_tool_metadata() -> list[dict[str, Any]]:
    return [
        {
            "name": "modify_gmail_labels",
            "description": (
                "Adiciona ou remove labels de uma mensagem Gmail (ex: INBOX, UNREAD, TRASH). "
                "Remover INBOX arquiva. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "add_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "remove_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["message_id"],
            },
        },
        {
            "name": "reply_gmail_message",
            "description": (
                "Responde a um e-mail na mesma thread. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "body": {"type": "string"},
                    "to": {
                        "type": "string",
                        "description": "Destino; padrão: remetente original.",
                    },
                },
                "required": ["message_id", "body"],
            },
        },
        {
            "name": "list_gmail_attachments",
            "description": (
                "Lista anexos de um e-mail (id, nome, mime, tamanho). "
                "Não baixa o conteúdo — use get_gmail_attachment."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                },
                "required": ["message_id"],
            },
        },
        {
            "name": "get_gmail_attachment",
            "description": (
                "Baixa um anexo para output_path no disco local (caminho absoluto). "
                "O binário não é retornado ao modelo — só metadados e caminho."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "attachment_id": {"type": "string"},
                    "output_path": {
                        "type": "string",
                        "description": "Caminho absoluto do arquivo de destino.",
                    },
                },
                "required": ["message_id", "attachment_id", "output_path"],
            },
        },
        {
            "name": "trash_gmail_message",
            "description": (
                "Move mensagem para a lixeira (TRASH + remove INBOX). Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                },
                "required": ["message_id"],
            },
        },
        {
            "name": "star_gmail_message",
            "description": "Marca ou desmarca estrela (label STARRED).",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "starred": {
                        "type": "boolean",
                        "description": "true=estrelar, false=remover (padrão true).",
                    },
                },
                "required": ["message_id"],
            },
        },
        {
            "name": "mark_gmail_read",
            "description": "Remove label UNREAD (marca como lido).",
            "input_schema": {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
            },
        },
        {
            "name": "mark_gmail_unread",
            "description": "Adiciona label UNREAD.",
            "input_schema": {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
            },
        },
        {
            "name": "restore_gmail_message",
            "description": (
                "Restaura da lixeira para a caixa de entrada. Requer confirm=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
            },
        },
        {
            "name": "list_gmail_labels",
            "description": "Lista labels Gmail (id, nome, tipo).",
            "input_schema": {"type": "object", "properties": {}},
        },
        {
            "name": "create_gmail_draft_api",
            "description": (
                "Cria rascunho Gmail (não envia). Retorna draft_id e message_id."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "send_gmail_draft",
            "description": "Envia rascunho existente pelo draft_id. Requer confirm=true.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                },
                "required": ["draft_id"],
            },
        },
    ]


def _gmail_service(account_id: str):
    credentials = load_google_credentials(account_id=account_id, interactive=False)
    return build_gmail_service(credentials=credentials)


def _collect_attachment_parts(
    payload: dict[str, Any],
    acc: list[dict[str, Any]],
) -> None:
    body = payload.get("body") or {}
    if body.get("attachmentId"):
        acc.append(
            {
                "attachment_id": body["attachmentId"],
                "filename": payload.get("filename") or "attachment",
                "mime_type": payload.get("mimeType") or "application/octet-stream",
                "size": int(body.get("size") or 0),
                "part_id": payload.get("partId"),
            }
        )
    for part in payload.get("parts") or []:
        if isinstance(part, dict):
            _collect_attachment_parts(part, acc)


def invoke_gmail_extra_tool(
    name: str,
    account_id: str,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    args = arguments or {}
    service = _gmail_service(account_id)

    if name == "modify_gmail_labels":
        message_id = str(args.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("message_id é obrigatório")
        body: dict[str, Any] = {}
        add_labels = args.get("add_labels")
        remove_labels = args.get("remove_labels")
        if isinstance(add_labels, list) and add_labels:
            body["addLabelIds"] = [str(x) for x in add_labels]
        if isinstance(remove_labels, list) and remove_labels:
            body["removeLabelIds"] = [str(x) for x in remove_labels]
        if not body:
            raise ValueError("Informe add_labels e/ou remove_labels")
        result = (
            service.users()
            .messages()
            .modify(userId="me", id=message_id, body=body)
            .execute()
        )
        return {
            "message_id": message_id,
            "label_ids": result.get("labelIds", []),
        }

    if name == "reply_gmail_message":
        message_id = str(args.get("message_id", "")).strip()
        body_text = str(args.get("body", "")).strip()
        if not message_id or not body_text:
            raise ValueError("message_id e body são obrigatórios")

        orig = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["Subject", "From", "Message-ID", "References"],
            )
            .execute()
        )
        thread_id = orig.get("threadId", "")
        headers = {
            h["name"].lower(): h["value"]
            for h in orig.get("payload", {}).get("headers", [])
        }
        subject = headers.get("subject", "")
        if subject and not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        to_addr = str(args.get("to") or headers.get("from", "")).strip()
        if not to_addr:
            raise ValueError("Não foi possível determinar destinatário (use to=).")

        mime = MIMEText(body_text)
        mime["to"] = to_addr
        mime["subject"] = subject or "Re:"
        if headers.get("message-id"):
            mime["In-Reply-To"] = headers["message-id"]
            refs = headers.get("references", "")
            mime["References"] = (
                f"{refs} {headers['message-id']}".strip() if refs else headers["message-id"]
            )

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
        sent = (
            service.users()
            .messages()
            .send(
                userId="me",
                body={"raw": raw, "threadId": thread_id},
            )
            .execute()
        )
        return {
            "id": sent.get("id"),
            "thread_id": sent.get("threadId", thread_id),
            "to": to_addr,
        }

    if name == "list_gmail_attachments":
        message_id = str(args.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("message_id é obrigatório")
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        attachments: list[dict[str, Any]] = []
        payload = msg.get("payload") or {}
        if isinstance(payload, dict):
            _collect_attachment_parts(payload, attachments)
        return {
            "message_id": message_id,
            "attachments": attachments,
            "count": len(attachments),
        }

    if name == "get_gmail_attachment":
        message_id = str(args.get("message_id", "")).strip()
        attachment_id = str(args.get("attachment_id", "")).strip()
        output_path = str(args.get("output_path", "")).strip()
        if not message_id or not attachment_id or not output_path:
            raise ValueError("message_id, attachment_id e output_path são obrigatórios")
        dest = Path(output_path).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        att = (
            service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        data = att.get("data")
        if not data:
            raise ValueError("Anexo vazio ou indisponível")
        raw = base64.urlsafe_b64decode(data)
        dest.write_bytes(raw)
        return {
            "message_id": message_id,
            "attachment_id": attachment_id,
            "output_path": str(dest),
            "size": len(raw),
        }

    if name == "trash_gmail_message":
        message_id = str(args.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("message_id é obrigatório")
        result = (
            service.users()
            .messages()
            .modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": ["TRASH"], "removeLabelIds": ["INBOX"]},
            )
            .execute()
        )
        return {
            "message_id": message_id,
            "label_ids": result.get("labelIds", []),
            "trashed": True,
        }

    if name == "star_gmail_message":
        message_id = str(args.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("message_id é obrigatório")
        starred = bool(args.get("starred", True))
        body = (
            {"addLabelIds": ["STARRED"]}
            if starred
            else {"removeLabelIds": ["STARRED"]}
        )
        result = (
            service.users()
            .messages()
            .modify(userId="me", id=message_id, body=body)
            .execute()
        )
        return {
            "message_id": message_id,
            "label_ids": result.get("labelIds", []),
            "starred": starred,
        }

    if name == "mark_gmail_read":
        message_id = str(args.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("message_id é obrigatório")
        result = (
            service.users()
            .messages()
            .modify(userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]})
            .execute()
        )
        return {
            "message_id": message_id,
            "label_ids": result.get("labelIds", []),
            "read": True,
        }

    if name == "mark_gmail_unread":
        message_id = str(args.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("message_id é obrigatório")
        result = (
            service.users()
            .messages()
            .modify(userId="me", id=message_id, body={"addLabelIds": ["UNREAD"]})
            .execute()
        )
        return {
            "message_id": message_id,
            "label_ids": result.get("labelIds", []),
            "read": False,
        }

    if name == "restore_gmail_message":
        message_id = str(args.get("message_id", "")).strip()
        if not message_id:
            raise ValueError("message_id é obrigatório")
        result = (
            service.users()
            .messages()
            .modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["TRASH"], "addLabelIds": ["INBOX"]},
            )
            .execute()
        )
        return {
            "message_id": message_id,
            "label_ids": result.get("labelIds", []),
            "restored": True,
        }

    if name == "list_gmail_labels":
        labels: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            req = service.users().labels().list(userId="me")
            if page_token:
                req = req.pageToken(page_token)
            resp = req.execute()
            for lab in resp.get("labels", []):
                labels.append(
                    {
                        "id": lab.get("id"),
                        "name": lab.get("name"),
                        "type": lab.get("type"),
                    }
                )
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return {"labels": labels, "count": len(labels)}

    if name == "create_gmail_draft_api":
        to_addr = str(args.get("to", "")).strip()
        subject = str(args.get("subject", "")).strip()
        body_text = str(args.get("body", "")).strip()
        if not to_addr or not subject or not body_text:
            raise ValueError("to, subject e body são obrigatórios")
        mime = MIMEText(body_text)
        mime["to"] = to_addr
        mime["subject"] = subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw}})
            .execute()
        )
        msg = draft.get("message", {})
        return {
            "draft_id": draft.get("id"),
            "message_id": msg.get("id"),
            "to": to_addr,
            "subject": subject,
        }

    if name == "send_gmail_draft":
        draft_id = str(args.get("draft_id", "")).strip()
        if not draft_id:
            raise ValueError("draft_id é obrigatório")
        sent = (
            service.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )
        return {
            "draft_id": draft_id,
            "id": sent.get("id"),
            "thread_id": sent.get("threadId"),
            "label_ids": sent.get("labelIds", []),
        }

    raise KeyError(f"Tool Gmail extra desconhecida: {name}")
