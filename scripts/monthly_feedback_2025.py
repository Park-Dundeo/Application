from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.adapters.google_auth import get_credentials
from app.adapters.sheets import _get_headers
from app.utils.rules import load_rules, apply_rules
from app.config import load_config


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


def parse_date(date_str: str) -> datetime | None:
    try:
        return datetime.fromisoformat(date_str)
    except Exception:
        return None


def is_target_month(date_str: str, year: int, month: int) -> bool:
    dt = parse_date(date_str)
    if not dt:
        return False
    return dt.year == year and dt.month == month


def build_report(rows: list[dict], rules, year: int, month: int, out_path: Path) -> dict:
    total = 0
    match = 0
    mismatch = 0
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
            if not is_target_month(date_val, year, month):
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
                mismatch += 1

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

    accuracy = (match / total) if total else 0.0
    return {
        "total": total,
        "match": match,
        "mismatch": mismatch,
        "empty_manual": empty_manual,
        "accuracy": accuracy,
        "report": str(out_path),
    }


def main() -> int:
    cfg = load_config()
    if not cfg.spreadsheet_id:
        raise RuntimeError("Missing SPREADSHEET_ID")

    rules = load_rules()
    rows = fetch_rows(cfg.spreadsheet_id, cfg.sheet_ledger, cfg.ledger_header_row)

    out_dir = Path("./data/reports")
    out_dir.mkdir(parents=True, exist_ok=True)

    attempts = 0
    for month in range(12, 0, -1):
        out_path = out_dir / f"category_review_2025-{month:02d}.csv"
        summary = build_report(rows, rules, 2025, month, out_path)
        acc = summary["accuracy"]
        print(f"2025-{month:02d}: total={summary['total']} match={summary['match']} mismatch={summary['mismatch']} empty_manual={summary['empty_manual']} acc={acc:.2%}")
        print(f"report: {summary['report']}")
        if acc < 0.90:
            attempts += 1
            print(f"accuracy below 90% (attempt {attempts}/5). Improve rules and re-run.")
            if attempts >= 5:
                print("reached 5 attempts without 90%+ accuracy. stop.")
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
