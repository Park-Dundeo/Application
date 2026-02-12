from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    inbox_dir: Path
    unzip_dir: Path
    staging_dir: Path
    gmail_query: str
    drive_folder: str
    spreadsheet_id: str
    sheet_ledger: str
    sheet_budget_raw: str
    ledger_header_row: int
    ledger_insert_row: int
    ledger_detail_col: str
    ledger_auto_col: str


def load_config() -> AppConfig:
    base = Path(os.environ.get("APP_DATA_DIR", "./data")).resolve()
    return AppConfig(
        data_dir=base,
        inbox_dir=base / "inbox",
        unzip_dir=base / "unzipped",
        staging_dir=base / "staging",
        gmail_query=os.environ.get("GMAIL_QUERY", "from:banksalad has:attachment"),
        drive_folder=os.environ.get("DRIVE_FOLDER", "재정/뱅크샐러드/INBOX"),
        spreadsheet_id=os.environ.get("SPREADSHEET_ID", ""),
        sheet_ledger=os.environ.get("SHEET_LEDGER", "가계부 내역"),
        sheet_budget_raw=os.environ.get("SHEET_BUDGET_RAW", "예산_원본"),
        ledger_header_row=int(os.environ.get("LEDGER_HEADER_ROW", "1")),
        ledger_insert_row=int(os.environ.get("LEDGER_INSERT_ROW", "2")),
        ledger_detail_col=os.environ.get("LEDGER_DETAIL_COL", "K"),
        ledger_auto_col=os.environ.get("LEDGER_AUTO_COL", "L"),
    )
