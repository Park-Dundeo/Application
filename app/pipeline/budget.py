"""
청지기 재정 예산 파이프라인 (Config-Driven)

budget_config.yaml을 읽어서 Google Sheets 예산안 시트를 생성/갱신합니다.

사용법:
  python -m app.pipeline.budget deploy          # 시트 생성
  python -m app.pipeline.budget deploy --force   # 기존 시트 삭제 후 재생성
  python -m app.pipeline.budget status           # 예산 현황 요약
  python -m app.pipeline.budget validate         # config 무결성 검증
  python -m app.pipeline.budget preview          # XLSX 미리보기 생성
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.config import AppConfig


# ── Config 로딩 ──────────────────────────────────────────


@dataclass
class BudgetItem:
    key: str
    monthly: int
    note: str = ""
    item_type: str = "regular"  # regular | irregular
    annual_from_bonus: int = 0


@dataclass
class Project:
    id: str
    name: str
    goal: str = ""
    note: str = ""
    items: list[BudgetItem] = field(default_factory=list)


@dataclass
class Tier:
    id: str
    name: str
    priority: int
    philosophy: str = ""
    color_bg: str = "#FFFFFF"
    color_header: str = "#333333"
    projects: list[Project] = field(default_factory=list)


@dataclass
class BudgetConfig:
    period: str
    period_start: str
    period_end: str
    monthly_base: int
    annual_bonus: int
    income_description: str
    tiers: list[Tier] = field(default_factory=list)
    bonus_allocation: dict[str, int] = field(default_factory=dict)

    @property
    def annual_income(self) -> int:
        return self.monthly_base * 12 + self.annual_bonus

    def all_items(self) -> list[tuple[Tier, Project, BudgetItem]]:
        """모든 항목을 (tier, project, item) 튜플 리스트로 반환"""
        result = []
        for tier in self.tiers:
            for project in tier.projects:
                for item in project.items:
                    result.append((tier, project, item))
        return result

    def total_monthly(self) -> int:
        return sum(item.monthly for _, _, item in self.all_items())

    def total_annual(self) -> int:
        return sum(item.monthly * 12 for _, _, item in self.all_items())

    def tier_monthly(self, tier_id: str) -> int:
        for tier in self.tiers:
            if tier.id == tier_id:
                return sum(
                    item.monthly
                    for proj in tier.projects
                    for item in proj.items
                )
        return 0


def load_budget_config(config_path: Path | None = None) -> BudgetConfig:
    """budget_config.yaml 파일을 파싱하여 BudgetConfig 객체로 반환"""
    if config_path is None:
        config_path = Path("data/budget_config.yaml")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    tiers = []
    for t in raw.get("tiers", []):
        projects = []
        for p in t.get("projects", []):
            items = []
            for i in p.get("items", []):
                items.append(BudgetItem(
                    key=i["key"],
                    monthly=i.get("monthly", 0),
                    note=i.get("note", ""),
                    item_type=i.get("type", "regular"),
                    annual_from_bonus=i.get("annual_from_bonus", 0),
                ))
            projects.append(Project(
                id=p["id"],
                name=p["name"],
                goal=p.get("goal", ""),
                note=p.get("note", ""),
                items=items,
            ))
        color = t.get("color", {})
        tiers.append(Tier(
            id=t["id"],
            name=t["name"],
            priority=t.get("priority", 99),
            philosophy=t.get("philosophy", ""),
            color_bg=color.get("bg", "#FFFFFF"),
            color_header=color.get("header", "#333333"),
            projects=projects,
        ))

    income = raw.get("income", {})
    return BudgetConfig(
        period=raw.get("period", ""),
        period_start=raw.get("period_start", ""),
        period_end=raw.get("period_end", ""),
        monthly_base=income.get("monthly_base", 0),
        annual_bonus=income.get("annual_bonus", 0),
        income_description=income.get("description", ""),
        tiers=tiers,
        bonus_allocation=raw.get("bonus_allocation", {}),
    )


# ── Google Sheets 서식 헬퍼 ──────────────────────────────


def _hex_to_rgb(hex_color: str) -> dict[str, float]:
    h = hex_color.lstrip("#")
    return {
        "red": int(h[0:2], 16) / 255,
        "green": int(h[2:4], 16) / 255,
        "blue": int(h[4:6], 16) / 255,
    }


def _cell_fmt(sheet_id: int, row: int, col: int,
              col_end: int | None = None, **kwargs: Any) -> dict:
    if col_end is None:
        col_end = col + 1
    fields = []
    cell_format: dict[str, Any] = {}

    if bg := kwargs.get("bg"):
        cell_format["backgroundColor"] = _hex_to_rgb(bg)
        fields.append("userEnteredFormat.backgroundColor")

    tf: dict[str, Any] = {}
    if kwargs.get("bold") is not None:
        tf["bold"] = kwargs["bold"]
    if fc := kwargs.get("font_color"):
        tf["foregroundColor"] = _hex_to_rgb(fc)
    if fs := kwargs.get("font_size"):
        tf["fontSize"] = fs
    if tf:
        cell_format["textFormat"] = tf
        fields.append("userEnteredFormat.textFormat")

    if ha := kwargs.get("h_align"):
        cell_format["horizontalAlignment"] = ha
        fields.append("userEnteredFormat.horizontalAlignment")

    if nf := kwargs.get("num_fmt"):
        cell_format["numberFormat"] = {"type": "NUMBER", "pattern": nf}
        fields.append("userEnteredFormat.numberFormat")

    if kwargs.get("borders"):
        bs = {"style": "SOLID", "color": _hex_to_rgb("#CCCCCC")}
        cell_format["borders"] = {
            "top": bs, "bottom": bs, "left": bs, "right": bs
        }
        fields.append("userEnteredFormat.borders")

    return {
        "repeatCell": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row,
                "endRowIndex": row + 1,
                "startColumnIndex": col,
                "endColumnIndex": col_end,
            },
            "cell": {"userEnteredFormat": cell_format},
            "fields": ",".join(fields),
        }
    }


def _row_fmt(sheet_id: int, row: int, col_end: int = 9,
             **kwargs: Any) -> dict:
    return _cell_fmt(sheet_id, row, 0, col_end, **kwargs)


# ── 시트 생성 (deploy) ──────────────────────────────────


def deploy(cfg: BudgetConfig, spreadsheet_id: str, force: bool = False) -> None:
    """config 기반으로 Google Sheets 예산안 시트 생성"""
    from googleapiclient.discovery import build
    from app.adapters.google_auth import get_credentials

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = get_credentials(SCOPES)
    service = build("sheets", "v4", credentials=creds)

    sheet_title = f"{cfg.period} 예산안"
    ledger_name = "가계부 내역"

    # 기존 시트 확인
    resp = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))"
    ).execute()

    existing_id = None
    for sheet in resp.get("sheets", []):
        if sheet["properties"]["title"] == sheet_title:
            existing_id = sheet["properties"]["sheetId"]
            break

    if existing_id is not None:
        if force:
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"deleteSheet": {"sheetId": existing_id}}]}
            ).execute()
            print(f"기존 시트 삭제: {sheet_title}")
        else:
            print(f"ERROR: '{sheet_title}' 시트가 이미 존재합니다.")
            print("  --force 옵션으로 재생성하거나, 시트 이름을 변경하세요.")
            sys.exit(1)

    # 시트 생성
    result = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "addSheet": {
                "properties": {
                    "title": sheet_title,
                    "gridProperties": {"rowCount": 80, "columnCount": 10},
                }
            }
        }]}
    ).execute()
    sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
    print(f"시트 생성: {sheet_title} (ID: {sheet_id})")

    # ── 데이터 구성 ──
    values: list[list] = []
    row_meta: list[tuple[int, str, Tier | None]] = []

    # period_start에서 연/월 추출
    ps = cfg.period_start  # "2026-07-01"
    ps_year, ps_month = ps.split("-")[0], ps.split("-")[1]

    # Row 0: 제목
    values.append([f"{cfg.period} 예산안 — 청지기 재정"])
    row_meta.append((0, "title", None))

    # Row 1: 수입 대시보드
    values.append([
        "월 기본급", cfg.monthly_base,
        "연간 수입", cfg.annual_income,
        "상여금/년", cfg.annual_bonus,
    ])
    row_meta.append((1, "dashboard", None))

    # Row 2: 동적 대시보드
    values.append([
        "경과 월수",
        f'=MONTH(NOW())-MONTH(DATE({ps_year},{ps_month},1))+1',
        "전월 월급",
        f"=SUMIFS('{ledger_name}'!G:G,'{ledger_name}'!A:A,\">=\"&EOMONTH(TODAY(),-2)+1,'{ledger_name}'!A:A,\"<=\"&EOMONTH(TODAY(),-1),'{ledger_name}'!F:F,\"급여\")",
        "본월 지출",
        f"=SUMIFS('{ledger_name}'!G:G,'{ledger_name}'!A:A,\">=\"&EOMONTH(TODAY(),-1)+1,'{ledger_name}'!A:A,\"<=\"&EOMONTH(TODAY(),0),'{ledger_name}'!C:C,\"지출\")",
    ])
    row_meta.append((2, "dashboard", None))

    # Row 3: 합계 대시보드 (수식은 나중에 채움)
    values.append(["월 소비예산", "", "연 소비예산", "", "월 잔여", "", "연 잔여", ""])
    row_meta.append((3, "dashboard", None))

    # Row 4: 빈 행
    values.append([])
    row_meta.append((4, "blank", None))

    # Row 5: 헤더
    values.append([
        "구분", "프로젝트", "항목", "월 예산", "연 예산",
        "실적", "남은 예산", "여분/부족", "비고",
    ])
    row_meta.append((5, "header", None))

    # ── 데이터 행 생성 ──
    tier_start_rows: dict[str, int] = {}  # tier_id → 0-indexed row
    subtotal_indices: list[int] = []
    prev_tier: Tier | None = None

    for tier, project, item in cfg.all_items():
        # 층이 바뀌면 이전 층 소계 삽입
        if prev_tier is not None and tier.id != prev_tier.id:
            _insert_subtotal(values, row_meta, subtotal_indices,
                             prev_tier, tier_start_rows[prev_tier.id])

        # 새 층 시작
        if prev_tier is None or tier.id != prev_tier.id:
            tier_start_rows[tier.id] = len(values)
            prev_tier = tier

        # 데이터 행
        ri = len(values)
        gs = ri + 1  # 1-indexed
        annual = item.monthly * 12
        note_parts = []
        if item.note:
            note_parts.append(item.note)
        if item.annual_from_bonus:
            note_parts.append(f"상여금 {item.annual_from_bonus:,}")
            annual += item.annual_from_bonus

        values.append([
            tier.name, project.name, item.key,
            item.monthly, annual,
            f"=SUMIF('{ledger_name}'!$K:$K,C{gs},'{ledger_name}'!$G:$G)",
            f"=E{gs}+F{gs}",
            f"=D{gs}*$B$3+F{gs}",
            " / ".join(note_parts) if note_parts else "",
        ])
        row_meta.append((ri, "data", tier))

    # 마지막 층 소계
    if prev_tier is not None:
        _insert_subtotal(values, row_meta, subtotal_indices,
                         prev_tier, tier_start_rows[prev_tier.id])

    # 빈 행 + 총계
    values.append([])
    row_meta.append((len(values) - 1, "blank", None))

    total_ri = len(values)
    gs_total = total_ri + 1

    def _sub_refs(col: str) -> str:
        return "+".join(f"{col}{si + 1}" for si in subtotal_indices)

    values.append([
        "", "", "총계",
        f"={_sub_refs('D')}", f"={_sub_refs('E')}",
        f"={_sub_refs('F')}", f"={_sub_refs('G')}",
        f"={_sub_refs('H')}", "",
    ])
    row_meta.append((total_ri, "total", None))

    # Row 3 대시보드 수식
    values[3] = [
        "월 소비예산", f"=D{gs_total}",
        "연 소비예산", f"=E{gs_total}",
        "월 잔여", "=B2-B4",
        "연 잔여", "=D2-D4",
    ]

    # ── 데이터 입력 ──
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_title}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": values},
    ).execute()
    print(f"데이터 입력: {len(values)}행")

    # ── 서식 적용 ──
    fmt: list[dict] = []

    # 열 너비
    col_widths = [80, 100, 160, 100, 120, 120, 120, 120, 250]
    for i, px in enumerate(col_widths):
        fmt.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id, "dimension": "COLUMNS",
                    "startIndex": i, "endIndex": i + 1,
                },
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        })

    # 제목
    fmt.append(_row_fmt(sheet_id, 0, bold=True, font_size=14))

    # 대시보드
    for r in range(1, 4):
        fmt.append(_row_fmt(sheet_id, r, col_end=8, borders=True))
        for c in [1, 3, 5, 7]:
            fmt.append(_cell_fmt(sheet_id, r, c, c + 1, num_fmt="#,##0"))

    # 헤더
    fmt.append(_row_fmt(
        sheet_id, 5, bg="#333333", bold=True, font_color="#FFFFFF",
        h_align="CENTER", borders=True))

    # 데이터/소계/총계
    for ri, rtype, tier_obj in row_meta:
        if rtype == "data" and tier_obj:
            fmt.append(_row_fmt(sheet_id, ri, bg=tier_obj.color_bg, borders=True))
            for c in range(3, 8):
                fmt.append(_cell_fmt(sheet_id, ri, c, c + 1, num_fmt="#,##0"))
        elif rtype == "subtotal" and tier_obj:
            fmt.append(_row_fmt(
                sheet_id, ri, bg=tier_obj.color_header,
                bold=True, font_color="#FFFFFF", borders=True))
            for c in range(3, 8):
                fmt.append(_cell_fmt(sheet_id, ri, c, c + 1, num_fmt="#,##0"))
        elif rtype == "total":
            fmt.append(_row_fmt(
                sheet_id, ri, bg="#000000", bold=True,
                font_color="#FFFFFF", font_size=11, borders=True))
            for c in range(3, 8):
                fmt.append(_cell_fmt(sheet_id, ri, c, c + 1, num_fmt="#,##0"))

    # 고정 행
    fmt.append({
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": {"frozenRowCount": 6},
            },
            "fields": "gridProperties.frozenRowCount",
        }
    })

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": fmt},
    ).execute()
    print("서식 적용 완료")


def _insert_subtotal(
    values: list[list],
    row_meta: list[tuple],
    subtotal_indices: list[int],
    tier: Tier,
    start_row: int,
) -> None:
    """소계 행을 values에 삽입"""
    ri = len(values)
    gs = ri + 1
    gs_start = start_row + 1
    gs_end = gs - 1
    values.append([
        "", "", f"{tier.name} 소계",
        f"=SUM(D{gs_start}:D{gs_end})",
        f"=SUM(E{gs_start}:E{gs_end})",
        f"=SUM(F{gs_start}:F{gs_end})",
        f"=SUM(G{gs_start}:G{gs_end})",
        f"=SUM(H{gs_start}:H{gs_end})",
        "",
    ])
    row_meta.append((ri, "subtotal", tier))
    subtotal_indices.append(ri)


# ── validate ──────────────────────────────────────────────


def validate(cfg: BudgetConfig) -> bool:
    """config 무결성 검증"""
    ok = True
    keys_seen: dict[str, str] = {}  # key → "tier/project"

    for tier in cfg.tiers:
        if not tier.id:
            print(f"ERROR: 층 id가 비어있음")
            ok = False
        for proj in tier.projects:
            if not proj.id:
                print(f"ERROR: {tier.name} 내 프로젝트 id가 비어있음")
                ok = False
            for item in proj.items:
                if not item.key:
                    print(f"ERROR: {tier.name}/{proj.name} 내 항목 key가 비어있음")
                    ok = False
                loc = f"{tier.name}/{proj.name}"
                if item.key in keys_seen:
                    print(f"WARN: K열 키 중복 '{item.key}'"
                          f" — {keys_seen[item.key]} ↔ {loc}")
                keys_seen[item.key] = loc
                if item.monthly < 0:
                    print(f"ERROR: {loc}/{item.key} 월예산이 음수: {item.monthly}")
                    ok = False

    total = cfg.total_annual()
    income = cfg.annual_income
    ratio = total / income * 100 if income else 0
    print(f"\n연간 수입:     {income:>12,}원")
    print(f"연간 지출예산: {total:>12,}원")
    print(f"비율:          {ratio:>11.1f}%")
    if total > income:
        print(f"WARN: 지출예산이 수입을 {total - income:,}원 초과")

    print(f"\n층별 요약:")
    for tier in cfg.tiers:
        m = cfg.tier_monthly(tier.id)
        a = m * 12
        print(f"  {tier.priority}층 {tier.name:12s}  월 {m:>10,}  연 {a:>12,}")

    print(f"\nK열 키 총 {len(keys_seen)}개")

    if ok:
        print("\n검증 통과")
    else:
        print("\n검증 실패")
    return ok


# ── status ────────────────────────────────────────────────


def status(cfg: BudgetConfig) -> None:
    """예산 현황 요약 (로컬, Sheets 연결 없음)"""
    print(f"=== {cfg.period} 청지기 재정 예산 ===\n")

    print(f"수입: 월 {cfg.monthly_base:,} + 상여 {cfg.annual_bonus:,}"
          f" = 연 {cfg.annual_income:,}\n")

    for tier in cfg.tiers:
        m = cfg.tier_monthly(tier.id)
        proj_count = len(tier.projects)
        item_count = sum(len(p.items) for p in tier.projects)
        print(f"[{tier.priority}층] {tier.name}")
        print(f"  철학: {tier.philosophy}")
        print(f"  월 {m:,} (프로젝트 {proj_count}개, 항목 {item_count}개)")
        for proj in tier.projects:
            pm = sum(i.monthly for i in proj.items)
            goal_str = f" — {proj.goal}" if proj.goal else ""
            print(f"    {proj.name}: 월 {pm:,}{goal_str}")
        print()

    total_m = cfg.total_monthly()
    total_a = cfg.total_annual()
    remain = cfg.annual_income - total_a
    print(f"총계: 월 {total_m:,} / 연 {total_a:,}")
    print(f"잔여: 연 {remain:,} ({'흑자' if remain >= 0 else '적자'})")


# ── preview (XLSX) ────────────────────────────────────────


def preview(cfg: BudgetConfig) -> str:
    """XLSX 미리보기 생성"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("openpyxl 필요: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{cfg.period} 예산안"

    thin = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )

    # 열 너비
    for col, w in {"A": 10, "B": 12, "C": 18, "D": 12, "E": 14,
                   "F": 14, "G": 14, "H": 14, "I": 30}.items():
        ws.column_dimensions[col].width = w

    # 제목
    ws["A1"] = f"{cfg.period} 예산안 — 청지기 재정"
    ws["A1"].font = Font(bold=True, size=14)

    # 대시보드
    dash = [
        ("A2", "월 기본급"), ("B2", cfg.monthly_base),
        ("C2", "연간 수입"), ("D2", cfg.annual_income),
        ("E2", "상여금/년"), ("F2", cfg.annual_bonus),
    ]
    for ref, val in dash:
        ws[ref] = val
        ws[ref].border = thin

    # 헤더
    headers = ["구분", "프로젝트", "항목", "월 예산", "연 예산",
               "실적", "남은 예산", "여분/부족", "비고"]
    hdr_fill = PatternFill(start_color="333333", end_color="333333",
                           fill_type="solid")
    for ci, h in enumerate(headers, 1):
        c = ws.cell(row=4, column=ci, value=h)
        c.fill = hdr_fill
        c.font = Font(bold=True, color="FFFFFF")
        c.alignment = Alignment(horizontal="center")
        c.border = thin

    # 데이터
    row = 5
    prev_tier: Tier | None = None
    tier_start: dict[str, int] = {}
    subtotal_rows: list[int] = []

    for tier, project, item in cfg.all_items():
        if prev_tier and tier.id != prev_tier.id:
            # 소계
            _xlsx_subtotal(ws, row, prev_tier, tier_start[prev_tier.id], thin)
            subtotal_rows.append(row)
            row += 1

        if prev_tier is None or tier.id != prev_tier.id:
            tier_start[tier.id] = row
            prev_tier = tier

        bg_hex = tier.color_bg.replace("#", "")
        fill = PatternFill(start_color=bg_hex, end_color=bg_hex,
                           fill_type="solid")
        annual = item.monthly * 12 + item.annual_from_bonus
        data = [tier.name, project.name, item.key, item.monthly, annual,
                "", "", "", item.note]
        for ci, val in enumerate(data, 1):
            c = ws.cell(row=row, column=ci, value=val)
            c.fill = fill
            c.border = thin
            if ci in (4, 5, 6, 7, 8):
                c.number_format = "#,##0"
        row += 1

    # 마지막 소계
    if prev_tier:
        _xlsx_subtotal(ws, row, prev_tier, tier_start[prev_tier.id], thin)
        subtotal_rows.append(row)
        row += 1

    # 총계
    row += 1
    total_fill = PatternFill(start_color="000000", end_color="000000",
                             fill_type="solid")
    ws.cell(row=row, column=3, value="총계")
    for c in range(1, 10):
        cell = ws.cell(row=row, column=c)
        cell.fill = total_fill
        cell.font = Font(bold=True, color="FFFFFF", size=11)
        cell.border = thin

    for c in [4, 5]:
        col_l = get_column_letter(c)
        formula = "+".join(f"{col_l}{r}" for r in subtotal_rows)
        ws.cell(row=row, column=c, value=f"={formula}")
        ws.cell(row=row, column=c).number_format = "#,##0"

    out_path = f"accountbook_analysis/budget_{cfg.period}.xlsx"
    wb.save(out_path)
    print(f"미리보기 생성: {out_path}")
    return out_path


def _xlsx_subtotal(ws, row, tier, start_row, border):
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    hdr_hex = tier.color_header.replace("#", "")
    fill = PatternFill(start_color=hdr_hex, end_color=hdr_hex,
                       fill_type="solid")
    ws.cell(row=row, column=3, value=f"{tier.name} 소계")
    for c in range(1, 10):
        cell = ws.cell(row=row, column=c)
        cell.fill = fill
        cell.font = Font(bold=True, color="FFFFFF")
        cell.border = border
    for c in [4, 5]:
        col_l = get_column_letter(c)
        ws.cell(row=row, column=c,
                value=f"=SUM({col_l}{start_row}:{col_l}{row - 1})")
        ws.cell(row=row, column=c).number_format = "#,##0"


# ── pipeline 통합용 (기존 인터페이스 유지) ────────────────


def refresh_budget_views(cfg: AppConfig) -> None:
    """기존 파이프라인 호환용. 추후 자동 갱신 로직 추가."""
    return


# ── CLI ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="청지기 재정 예산 관리",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  deploy     Google Sheets에 예산안 시트 생성
  validate   config 무결성 검증
  status     예산 현황 요약 (로컬)
  preview    XLSX 미리보기 생성
        """,
    )
    parser.add_argument("command", choices=["deploy", "validate", "status", "preview"])
    parser.add_argument("--config", type=Path, default=Path("data/budget_config.yaml"),
                        help="budget config 경로")
    parser.add_argument("--force", action="store_true",
                        help="deploy 시 기존 시트 삭제 후 재생성")

    args = parser.parse_args()

    budget_cfg = load_budget_config(args.config)

    if args.command == "validate":
        return 0 if validate(budget_cfg) else 1

    elif args.command == "status":
        status(budget_cfg)
        return 0

    elif args.command == "preview":
        preview(budget_cfg)
        return 0

    elif args.command == "deploy":
        import os
        sid = os.environ.get("SPREADSHEET_ID", "")
        if not sid:
            print("ERROR: SPREADSHEET_ID 환경변수 필요")
            return 1
        deploy(budget_cfg, sid, force=args.force)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
