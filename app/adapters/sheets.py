from __future__ import annotations

from typing import Iterable

from googleapiclient.discovery import build

from app.adapters.google_auth import get_credentials
from app.utils.hash import row_key

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.readonly",
]


def _col_letter(n: int) -> str:
    # 1-based
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result


def _get_service():
    creds = get_credentials(SCOPES)
    return build("sheets", "v4", credentials=creds)


def _get_sheet_id(service, spreadsheet_id: str, sheet_name: str) -> int:
    resp = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))").execute()
    for sheet in resp.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == sheet_name:
            return int(props.get("sheetId"))
    raise RuntimeError(f"Sheet not found: {sheet_name}")


def _get_headers(service, spreadsheet_id: str, sheet_name: str, header_row: int) -> list[str]:
    rng = f"{sheet_name}!{header_row}:{header_row}"
    resp = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    values = resp.get("values", [[]])
    return [v.strip() for v in values[0] if v is not None]


def insert_rows(
    spreadsheet_id: str,
    sheet_name: str,
    header_row: int,
    insert_row: int,
    rows: Iterable[dict],
) -> None:
    service = _get_service()
    sheet_id = _get_sheet_id(service, spreadsheet_id, sheet_name)

    rows_list = list(rows)
    if not rows_list:
        return

    headers = _get_headers(service, spreadsheet_id, sheet_name, header_row)
    if not headers:
        raise RuntimeError("Header row is empty")

    # Insert empty rows at insert_row
    start_index = insert_row - 1
    end_index = start_index + len(rows_list)
    body = {
        "requests": [
            {
                "insertDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": start_index,
                        "endIndex": end_index,
                    },
                    "inheritFromBefore": False,
                }
            }
        ]
    }
    service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()

    values = []
    for row in rows_list:
        values.append([row.get(h, "") for h in headers])

    last_col = _col_letter(len(headers))
    write_range = f"{sheet_name}!A{insert_row}:{last_col}{insert_row + len(values) - 1}"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=write_range,
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def update_detail_column(
    spreadsheet_id: str,
    sheet_name: str,
    detail_col: str,
    insert_row: int,
    updates: list[tuple[dict, str]],
) -> None:
    if not updates:
        return

    service = _get_service()
    values = [[u[1]] for u in updates]
    end_row = insert_row + len(values) - 1
    rng = f"{sheet_name}!{detail_col}{insert_row}:{detail_col}{end_row}"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def ensure_header(
    spreadsheet_id: str,
    sheet_name: str,
    header_row: int,
    col_letter: str,
    header_value: str,
) -> None:
    service = _get_service()
    rng = f"{sheet_name}!{col_letter}{header_row}"
    resp = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    current = ""
    values = resp.get("values", [])
    if values and values[0]:
        current = str(values[0][0]).strip()
    if current == header_value:
        return
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueInputOption="USER_ENTERED",
        body={"values": [[header_value]]},
    ).execute()


def update_auto_category_column(
    spreadsheet_id: str,
    sheet_name: str,
    auto_col: str,
    insert_row: int,
    updates: list[tuple[dict, str]],
) -> None:
    if not updates:
        return

    service = _get_service()
    values = [[u[1]] for u in updates]
    end_row = insert_row + len(values) - 1
    rng = f"{sheet_name}!{auto_col}{insert_row}:{auto_col}{end_row}"
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=rng,
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()


def fetch_existing_keys(
    spreadsheet_id: str,
    sheet_name: str,
    header_row: int,
    key_fields: list[str],
    max_rows: int = 5000,
) -> set[str]:
    service = _get_service()

    headers = _get_headers(service, spreadsheet_id, sheet_name, header_row)
    if not headers:
        return set()

    col_count = len(headers)
    last_col = _col_letter(col_count)
    start_row = header_row + 1
    end_row = start_row + max_rows - 1
    rng = f"{sheet_name}!A{start_row}:{last_col}{end_row}"
    resp = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    values = resp.get("values", [])

    index = {h: i for i, h in enumerate(headers)}
    keys = set()
    for row in values:
        obj = {}
        for k in key_fields:
            idx = index.get(k)
            obj[k] = row[idx] if idx is not None and idx < len(row) else ""
        keys.add(row_key(obj, key_fields))

    return keys


def fetch_max_date(
    spreadsheet_id: str,
    sheet_name: str,
    header_row: int,
    date_field: str = "날짜",
    max_rows: int = 5000,
) -> str | None:
    service = _get_service()
    headers = _get_headers(service, spreadsheet_id, sheet_name, header_row)
    if not headers:
        return None

    try:
        date_idx = headers.index(date_field)
    except ValueError:
        return None

    col_count = len(headers)
    last_col = _col_letter(col_count)
    start_row = header_row + 1
    end_row = start_row + max_rows - 1
    rng = f"{sheet_name}!A{start_row}:{last_col}{end_row}"
    resp = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=rng).execute()
    values = resp.get("values", [])

    max_date = None
    for row in values:
        if date_idx >= len(row):
            continue
        value = row[date_idx]
        if not value:
            continue
        if max_date is None or value > max_date:
            max_date = value

    return max_date
