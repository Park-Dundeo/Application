from pathlib import Path
import csv
from app.config import AppConfig
from app.utils.hash import row_key, KEY_FIELDS
from app.adapters.sheets import fetch_existing_keys, fetch_max_date


def filter_new_rows(cfg: AppConfig, normalized_path: Path) -> list[dict]:
    seen = fetch_existing_keys(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        key_fields=KEY_FIELDS,
    )
    max_date = fetch_max_date(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        date_field="날짜",
    )
    new_rows = []

    with normalized_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if max_date and row.get("날짜") and row.get("날짜") <= max_date:
                continue

            key = row_key(row, KEY_FIELDS)
            if key in seen:
                continue
            seen.add(key)
            new_rows.append(row)

    return new_rows
