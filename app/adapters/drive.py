from __future__ import annotations

from pathlib import Path
from typing import Optional

from googleapiclient.discovery import build

from app.adapters.google_auth import get_credentials

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _find_folder_id(service, name: str, parent_id: Optional[str]) -> Optional[str]:
    q = ["mimeType = 'application/vnd.google-apps.folder'", f"name = '{name}'", "trashed = false"]
    if parent_id:
        q.append(f"'{parent_id}' in parents")
    else:
        q.append("'root' in parents")

    resp = service.files().list(q=" and ".join(q), fields="files(id, name)").execute()
    files = resp.get("files", [])
    if not files:
        return None
    return files[0]["id"]


def _create_folder(service, name: str, parent_id: Optional[str]) -> str:
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        body["parents"] = [parent_id]
    resp = service.files().create(body=body, fields="id").execute()
    return resp["id"]


def _find_file_id(service, name: str, parent_id: Optional[str]) -> Optional[str]:
    q = [f"name = '{name}'", "trashed = false"]
    if parent_id:
        q.append(f"'{parent_id}' in parents")
    else:
        q.append("'root' in parents")
    resp = service.files().list(q=" and ".join(q), fields="files(id, name)").execute()
    files = resp.get("files", [])
    if not files:
        return None
    return files[0]["id"]


def _ensure_folder_path(service, path: str) -> str:
    parts = [p for p in path.split("/") if p]
    parent_id = None
    for part in parts:
        folder_id = _find_folder_id(service, part, parent_id)
        if not folder_id:
            folder_id = _create_folder(service, part, parent_id)
        parent_id = folder_id
    return parent_id or "root"


def save_to_drive(local_path: Path, drive_folder: str) -> None:
    creds = get_credentials(SCOPES)
    service = build("drive", "v3", credentials=creds)

    folder_id = _ensure_folder_path(service, drive_folder)

    existing_id = _find_file_id(service, local_path.name, folder_id)
    if existing_id:
        return

    media_body = {
        "name": local_path.name,
        "parents": [folder_id],
    }
    # simple upload
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(local_path), resumable=False)
    service.files().create(body=media_body, media_body=media, fields="id").execute()
