from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import base64

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from app.adapters.google_auth import get_credentials


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


@dataclass
class Attachment:
    name: str
    data: bytes


class GmailClient:
    def __init__(self, creds: Credentials):
        self.service = build("gmail", "v1", credentials=creds)

    def list_messages(self, query: str) -> Iterable[dict]:
        resp = self.service.users().messages().list(userId="me", q=query, maxResults=10).execute()
        return resp.get("messages", [])

    def get_message(self, msg_id: str) -> dict:
        return self.service.users().messages().get(userId="me", id=msg_id, format="full").execute()

    def get_attachment(self, msg_id: str, attachment_id: str) -> bytes:
        resp = (
            self.service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=msg_id, id=attachment_id)
            .execute()
        )
        data = resp.get("data", "")
        return base64.urlsafe_b64decode(data.encode("utf-8"))


def _iter_attachments(payload: dict) -> Iterable[tuple[str, str]]:
    # yields (filename, attachmentId)
    parts = payload.get("parts", [])
    for part in parts:
        filename = part.get("filename")
        body = part.get("body", {})
        attachment_id = body.get("attachmentId")
        if filename and attachment_id:
            yield filename, attachment_id
        # handle nested parts
        for nested in part.get("parts", []) or []:
            n_filename = nested.get("filename")
            n_body = nested.get("body", {})
            n_attach = n_body.get("attachmentId")
            if n_filename and n_attach:
                yield n_filename, n_attach


def find_latest_attachment(query: str) -> Attachment | None:
    creds = get_credentials(SCOPES)
    client = GmailClient(creds)

    messages = list(client.list_messages(query))
    if not messages:
        return None

    # Gmail list returns most recent first by default
    msg = client.get_message(messages[0]["id"])
    payload = msg.get("payload", {})

    for filename, attachment_id in _iter_attachments(payload):
        data = client.get_attachment(msg["id"], attachment_id)
        return Attachment(name=filename, data=data)

    return None
