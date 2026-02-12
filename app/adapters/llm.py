from __future__ import annotations

from typing import Mapping
from pathlib import Path
import json
import os


def _load_keywords() -> list[str]:
    path = Path(os.environ.get("BUDGET_KEYWORDS_PATH", "./data/budget_keywords.json"))
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            # prefer longer matches first
            return sorted({str(x).strip() for x in data if str(x).strip()}, key=lambda s: (-len(s), s))
    except Exception:
        return []
    return []


_KEYWORDS = _load_keywords()


def classify_detail(row: Mapping[str, str]) -> str | None:
    # If user already set detail, keep it as auto category too.
    existing = (row.get("상세") or "").strip()
    if existing:
        return existing

    if not _KEYWORDS:
        return None

    fields = [
        (row.get("내용") or "").strip(),
        (row.get("소분류") or "").strip(),
        (row.get("대분류") or "").strip(),
        (row.get("메모") or "").strip(),
        (row.get("결제수단") or "").strip(),
    ]

    # Exact match
    for field in fields:
        if not field:
            continue
        if field in _KEYWORDS:
            return field

    # Substring match (prefer longer keyword)
    haystack = " ".join([f for f in fields if f])
    for kw in _KEYWORDS:
        if kw and kw in haystack:
            return kw

    return None
