from __future__ import annotations

import hashlib


KEY_FIELDS = ["날짜", "시간", "금액", "내용", "결제수단"]


def row_key(row: dict, fields: list[str] | None = None) -> str:
    use_fields = fields or KEY_FIELDS
    parts = [str(row.get(k, "")) for k in use_fields]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
