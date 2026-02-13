from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import sys


def log(message: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    print(line)

    log_path = Path(os.environ.get("APP_LOG_PATH", "./data/logs/pipeline.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # best-effort logging
        pass
