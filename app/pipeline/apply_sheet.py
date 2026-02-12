from app.config import AppConfig
from app.adapters.sheets import insert_rows


def apply_to_ledger(cfg: AppConfig, rows: list[dict]) -> None:
    if not rows:
        return
    insert_rows(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        insert_row=cfg.ledger_insert_row,
        rows=rows,
    )
