from pathlib import Path
import zipfile
from datetime import datetime
import os
from app.config import AppConfig


def unzip_latest(cfg: AppConfig, export_path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    target_dir = cfg.unzip_dir / stamp

    # Avoid stale files from earlier runs on the same day.
    if target_dir.exists():
        for child in target_dir.iterdir():
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                import shutil
                shutil.rmtree(child, ignore_errors=True)

    target_dir.mkdir(parents=True, exist_ok=True)

    if export_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(export_path, "r") as zf:
            password = os.environ.get("ZIP_PASSWORD", "").encode("utf-8") or None
            if password:
                zf.setpassword(password)
            zf.extractall(target_dir)
    else:
        (target_dir / export_path.name).write_bytes(export_path.read_bytes())

    return target_dir
