from __future__ import annotations

from pathlib import Path
from app.config import AppConfig
from app.adapters.gmail import find_latest_attachment
from app.adapters.drive import save_to_drive


def ingest_latest_export(cfg: AppConfig) -> Path | None:
    attachment = find_latest_attachment(cfg.gmail_query)
    if attachment is None:
        return None

    local_path = cfg.inbox_dir / attachment.name
    local_path.write_bytes(attachment.data)
    save_to_drive(local_path, cfg.drive_folder)
    return local_path
