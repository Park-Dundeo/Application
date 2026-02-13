from app.config import AppConfig
from app.adapters.llm import classify_detail
from app.adapters.sheets import ensure_header, update_auto_category_column, update_category_block, ensure_checkbox_column
from app.utils.rules import load_rules, apply_rules
import os
from app.utils.logging import log


def auto_categorize(cfg: AppConfig, rows: list[dict]) -> None:
    if not rows:
        return

    ensure_header(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        col_letter=cfg.ledger_category_col,
        header_value="category",
    )
    ensure_header(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        col_letter=cfg.ledger_category_source_col,
        header_value="category_source",
    )
    ensure_header(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        col_letter=cfg.ledger_reviewed_col,
        header_value="reviewed",
    )
    ensure_header(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        col_letter=cfg.ledger_confidence_col,
        header_value="confidence",
    )
    ensure_header(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        col_letter=cfg.ledger_reclass_col,
        header_value="재분류필요",
    )

    ensure_header(
        spreadsheet_id=cfg.spreadsheet_id,
        sheet_name=cfg.sheet_ledger,
        header_row=cfg.ledger_header_row,
        col_letter=cfg.ledger_auto_col,
        header_value="자동카테고리",
    )

    rules = load_rules()
    log(f"rules loaded: {len(rules)}")
    use_llm = os.environ.get("USE_LLM", "0").strip() == "1"

    updates = []
    category_rows = []
    for row in rows:
        suggestion = classify_detail(row)

        category = None
        source = None
        confidence = ""

        if rules:
            category, source = apply_rules(row, rules)
            if category:
                log(f"rule matched: {category}")

        if not category and use_llm:
            suggestion = classify_detail(row)
            if suggestion:
                category = suggestion
                source = "llm"
                confidence = "0.5"

        reviewed = "N"
        if not category:
            category = ""
            source = ""
            confidence = ""

        updates.append((row, suggestion or ""))
        category_rows.append([category, source or "", reviewed, confidence])

    if updates:
        update_auto_category_column(
            spreadsheet_id=cfg.spreadsheet_id,
            sheet_name=cfg.sheet_ledger,
            auto_col=cfg.ledger_auto_col,
            insert_row=cfg.ledger_insert_row,
            updates=updates,
        )

    if category_rows:
        update_category_block(
            spreadsheet_id=cfg.spreadsheet_id,
            sheet_name=cfg.sheet_ledger,
            start_col=cfg.ledger_category_col,
            end_col=cfg.ledger_confidence_col,
            insert_row=cfg.ledger_insert_row,
            values=category_rows,
        )

        # Set checkbox validation for reclassify column for the inserted range
        end_row = cfg.ledger_insert_row + len(category_rows) - 1
        ensure_checkbox_column(
            spreadsheet_id=cfg.spreadsheet_id,
            sheet_name=cfg.sheet_ledger,
            col_letter=cfg.ledger_reclass_col,
            start_row=cfg.ledger_insert_row,
            end_row=end_row,
        )
