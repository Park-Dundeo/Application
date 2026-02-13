from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import json
import sys
import re

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapters.google_auth import get_credentials
from app.adapters.sheets import _get_headers
from app.utils.categories import load_categories


def fetch_rows(spreadsheet_id: str, sheet_name: str, header_row: int, max_rows: int = 8000) -> list[dict]:
    from googleapiclient.discovery import build

    service = build("sheets", "v4", credentials=get_credentials(["https://www.googleapis.com/auth/spreadsheets"]))
    headers = _get_headers(service, spreadsheet_id, sheet_name, header_row)
    if not headers:
        return []

    col_count = len(headers)

    def col_letter(n: int) -> str:
        result = ""
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result
        return result

    last_col = col_letter(col_count)
    start_row = header_row + 1
    end_row = start_row + max_rows - 1
    rng = f"{sheet_name}!A{start_row}:{last_col}{end_row}"
    resp = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    values = resp.get("values", [])

    rows = []
    for row in values:
        item = {headers[i]: row[i] if i < len(row) else "" for i in range(col_count)}
        rows.append(item)
    return rows


def is_target_month(date_str: str, year: int, month: int) -> bool:
    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        return False
    return dt.year == year and dt.month == month


def load_rules(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def save_rules(path: Path, rules: list[dict]) -> None:
    path.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    from app.config import load_config

    cfg = load_config()
    rules_path = Path("./data/rules.json")
    rules = load_rules(rules_path)
    allowed = load_categories()

    rows = fetch_rows(cfg.spreadsheet_id, cfg.sheet_ledger, cfg.ledger_header_row)

    # Build merchant frequency per manual category for target month
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    month = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    top_n = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    counts = defaultdict(Counter)
    for row in rows:
        date_val = str(row.get("날짜", "")).strip()
        if not is_target_month(date_val, year, month):
            continue
        manual = str(row.get("상세", "")).strip()
        if not manual:
            continue
        if allowed and manual not in allowed:
            continue
        merchant = str(row.get("내용", "")).strip()
        if not merchant:
            continue
        # skip too generic merchants
        if re.fullmatch(r"[0-9\-_/ ]+", merchant):
            continue
        counts[manual][merchant] += 1

    # build set of existing (category, pattern)
    existing = {(r.get("category"), r.get("pattern")) for r in rules if isinstance(r, dict)}

    # assign new rules with high priority (lower number)
    min_priority = min([r.get("priority", 1000) for r in rules if isinstance(r, dict)] + [100])
    priority = max(1, min_priority - 100)

    new_rules = []
    for category, ctr in counts.items():
        for merchant, _cnt in ctr.most_common(top_n):
            if (category, merchant) in existing:
                continue
            new_rules.append({
                "priority": priority,
                "match_type": "contains",
                "pattern": merchant,
                "category": category,
                "enabled": True,
                "fields": ["merchant"],
            })
            priority += 1

    if new_rules:
        rules = new_rules + rules
        save_rules(rules_path, rules)

    print(f"added_rules: {len(new_rules)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
