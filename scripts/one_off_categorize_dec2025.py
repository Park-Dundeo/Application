from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapters.google_auth import get_credentials
from app.adapters.sheets import _get_headers  # reuse header reader
from app.utils.rules import load_rules, apply_rules
from app.config import load_config


def fetch_rows(spreadsheet_id: str, sheet_name: str, header_row: int, max_rows: int = 5000) -> list[dict]:
    from googleapiclient.discovery import build

    service = build("sheets", "v4", credentials=get_credentials(["https://www.googleapis.com/auth/spreadsheets"]))
    headers = _get_headers(service, spreadsheet_id, sheet_name, header_row)
    if not headers:
        return []

    col_count = len(headers)
    # Build range A{header_row+1}:<last_col>
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


def is_dec_2025(date_str: str) -> bool:
    try:
        dt = datetime.fromisoformat(date_str)
    except Exception:
        return False
    return dt.year == 2025 and dt.month == 12


def main() -> int:
    cfg = load_config()
    if not cfg.spreadsheet_id:
        raise RuntimeError("Missing SPREADSHEET_ID")

    rules = load_rules()

    rows = fetch_rows(cfg.spreadsheet_id, cfg.sheet_ledger, cfg.ledger_header_row)

    out_dir = Path("./data/reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "category_review_2025-12.csv"

    total = 0
    match = 0
    mismatched = 0
    empty_manual = 0

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date",
            "time",
            "amount",
            "merchant",
            "manual_detail",
            "auto_category",
            "rule_source",
            "match",
        ])

        for row in rows:
            date_val = str(row.get("날짜", "")).strip()
            if not is_dec_2025(date_val):
                continue

            total += 1
            manual = str(row.get("상세", "")).strip()
            auto, source = apply_rules(row, rules) if rules else (None, None)
            auto = auto or ""
            source = source or ""

            if not manual:
                empty_manual += 1

            is_match = manual == auto and manual != ""
            if is_match:
                match += 1
            elif manual or auto:
                mismatched += 1

            writer.writerow([
                date_val,
                str(row.get("시간", "")).strip(),
                str(row.get("금액", "")).strip(),
                str(row.get("내용", "")).strip(),
                manual,
                auto,
                source,
                "Y" if is_match else "N",
            ])

    print(f"rows: {total}")
    print(f"match: {match}")
    print(f"mismatch: {mismatched}")
    print(f"empty_manual: {empty_manual}")
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
