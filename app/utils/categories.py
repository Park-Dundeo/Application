from __future__ import annotations

from pathlib import Path
import json
import os


def load_categories() -> set[str]:
    path = Path(os.environ.get("CATEGORIES_PATH", "./data/categories.json"))
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    if isinstance(data, list):
        return {str(x).strip() for x in data if str(x).strip()}
    return set()
