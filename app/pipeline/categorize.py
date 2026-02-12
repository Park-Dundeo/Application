from app.config import AppConfig
from app.adapters.llm import classify_detail
from app.adapters.sheets import ensure_header, update_auto_category_column


def auto_categorize(cfg: AppConfig, rows: list[dict]) -> None:
    if not rows:
        return

    ensure_header(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        col_letter=cfg.ledger_auto_col,
        header_value="자동카테고리",
    )

    updates = []
    for row in rows:
        suggestion = classify_detail(row)
        if not suggestion:
            continue
        updates.append((row, suggestion))

    if updates:
        update_auto_category_column(
            spreadsheet_id=cfg.spreadsheet_id,
            sheet_name=cfg.sheet_ledger,
            auto_col=cfg.ledger_auto_col,
            insert_row=cfg.ledger_insert_row,
            updates=updates,
        )
