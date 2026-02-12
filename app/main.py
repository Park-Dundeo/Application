from app.config import load_config
from app.pipeline.ingest import ingest_latest_export
from app.pipeline.unzip import unzip_latest
from app.pipeline.normalize import normalize_latest
from app.pipeline.dedup import filter_new_rows
from app.pipeline.apply_sheet import apply_to_ledger
from app.pipeline.categorize import auto_categorize
from app.pipeline.budget import refresh_budget_views
from datetime import datetime


def run_pipeline() -> int:
    cfg = load_config()

    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.inbox_dir.mkdir(parents=True, exist_ok=True)
    cfg.unzip_dir.mkdir(parents=True, exist_ok=True)
    cfg.staging_dir.mkdir(parents=True, exist_ok=True)

    if not cfg.spreadsheet_id:
        raise RuntimeError("Missing SPREADSHEET_ID environment variable")

    export_path = ingest_latest_export(cfg)
    if not export_path:
        return 0

    unzip_path = unzip_latest(cfg, export_path)
    normalized_path = normalize_latest(cfg, unzip_path)
    new_rows = filter_new_rows(cfg, normalized_path)
    if new_rows:
        def _parse_dt(row: dict) -> datetime:
            date_str = row.get("날짜", "")
            time_str = row.get("시간", "00:00:00")
            try:
                return datetime.fromisoformat(f"{date_str} {time_str}")
            except Exception:
                return datetime.min

        new_rows.sort(key=_parse_dt, reverse=True)
        apply_to_ledger(cfg, new_rows)
        auto_categorize(cfg, new_rows)
        refresh_budget_views(cfg)

    return 0


if __name__ == "__main__":
    raise SystemExit(run_pipeline())
