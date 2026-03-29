"""
청지기 재정 프로젝트 헌장 파이프라인 (v2)

data/projects/*.yaml을 읽어서 별도 Google Spreadsheet에 시트를 생성합니다.
  - 전체 현황  : 간트 스타일 타임라인 뷰 (모든 프로젝트 + 마일스톤)
  - 프로젝트별 : 9개 섹션 모니터링 카드 + FEEDBACK 입력 영역

ENV:
  PROJECT_SPREADSHEET_ID — 없으면 신규 생성 후 ID 출력, 있으면 기존 사용

사용법:
  python3 -m app.pipeline.projects status              # 로컬 텍스트 뷰
  python3 -m app.pipeline.projects deploy [--force]    # 스프레드시트 생성/갱신
  python3 -m app.pipeline.projects export              # 피드백 → YAML 업데이트
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.pipeline.budget import load_budget_config


# ── 데이터 모델 ──────────────────────────────────────────


@dataclass
class Routine:
    id: str
    name: str
    description: str
    budget_item: str
    monthly: int
    schedule: list[dict] = field(default_factory=list)


@dataclass
class ProjectCharter:
    id: str
    name: str
    budget_items: list[str]
    monthly: int
    project_type: str = "mission"   # "mission" | "relation"
    calling: str = ""
    discernment: dict = field(default_factory=dict)
    companionship: str = ""
    practice_template: list[str] = field(default_factory=list)
    fruit_evidence: dict = field(default_factory=dict)
    delegation: dict = field(default_factory=dict)
    review_rhythm: str = ""
    boundaries: dict = field(default_factory=dict)
    handoff_condition: str = ""
    exit_condition: str = ""
    gates: dict = field(default_factory=dict)
    next_actions: list[str] = field(default_factory=list)
    schedule: list[dict] = field(default_factory=list)


@dataclass
class TierCharters:
    tier_id: str
    tier_name: str
    tier_priority: int
    color_bg: str
    color_header: str
    philosophy: str
    routines: list[Routine] = field(default_factory=list)
    projects: list[ProjectCharter] = field(default_factory=list)


# ── YAML 로딩 ────────────────────────────────────────────


def load_all_projects(
    projects_dir: Path | None = None,
    budget_config_path: Path | None = None,
) -> list[TierCharters]:
    """data/projects/*.yaml 전체 스캔 → TierCharters 리스트 (priority 순)"""
    if projects_dir is None:
        projects_dir = Path("data/projects")
    if budget_config_path is None:
        budget_config_path = Path("data/budget_config.yaml")

    budget_cfg = load_budget_config(budget_config_path)
    tier_meta = {t.id: t for t in budget_cfg.tiers}

    tier_charters: list[TierCharters] = []

    for yaml_path in sorted(projects_dir.glob("*.yaml")):
        tier_id = yaml_path.stem
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        meta = tier_meta.get(tier_id)
        if meta:
            tier_name, tier_priority = meta.name, meta.priority
            color_bg, color_header, philosophy = meta.color_bg, meta.color_header, meta.philosophy
        else:
            tier_name, tier_priority = tier_id, 99
            color_bg, color_header, philosophy = "#FFFFFF", "#333333", ""

        def _norm_schedule(raw_sched):
            if not raw_sched:
                return []
            if isinstance(raw_sched, dict):
                return [raw_sched]
            return list(raw_sched)

        routines = [
            Routine(
                id=r["id"], name=r["name"],
                description=r.get("description", ""),
                budget_item=r.get("budget_item", ""),
                monthly=r.get("monthly", 0),
                schedule=_norm_schedule(r.get("schedule")),
            )
            for r in raw.get("routines", [])
        ]

        projects = [
            ProjectCharter(
                id=p["id"], name=p["name"],
                budget_items=p.get("budget_items", []),
                monthly=p.get("monthly", 0),
                project_type=p.get("project_type", "mission"),
                calling=p.get("calling", "").strip(),
                discernment=p.get("discernment", {}),
                companionship=p.get("companionship", ""),
                practice_template=p.get("practice_template", []),
                fruit_evidence=p.get("fruit_evidence", {}),
                delegation=p.get("delegation", {}),
                review_rhythm=p.get("review_rhythm", ""),
                boundaries=p.get("boundaries", {}),
                handoff_condition=p.get("handoff_condition", ""),
                exit_condition=p.get("exit_condition", ""),
                gates=p.get("gates", {}),
                next_actions=p.get("next_actions", []),
                schedule=_norm_schedule(p.get("schedule")),
            )
            for p in raw.get("projects", [])
        ]

        tier_charters.append(TierCharters(
            tier_id=tier_id, tier_name=tier_name,
            tier_priority=tier_priority,
            color_bg=color_bg, color_header=color_header,
            philosophy=philosophy,
            routines=routines, projects=projects,
        ))

    return sorted(tier_charters, key=lambda t: t.tier_priority)


# ── Gate / 완성도 헬퍼 ────────────────────────────────────


def _gate_info(gates: dict) -> tuple[str, str, str]:
    """(표시 텍스트, 배경색, 텍스트색)"""
    c = gates.get("C_handoff", {}).get("status", "")
    b = gates.get("B_grow", {}).get("status", "")
    a = gates.get("A_seed", {}).get("status", "")
    if c in ("진행중", "통과"):
        return "C 이양", "#E3F2FD", "#1565C0"
    if b == "통과":
        return "B ✓", "#E8F5E9", "#1B5E20"
    if b in ("분별 중", "분별중"):
        return "B 심화중", "#FFF9C4", "#F57F17"
    if b == "유지":
        return "B 유지", "#FFF9C4", "#F57F17"
    if a == "통과":
        return "A ✓", "#E8F5E9", "#2E7D32"
    return "—", "#F5F5F5", "#9E9E9E"


def _gate_display_row(gates: dict) -> str:
    """Gate 상태를 한 줄 텍스트로 표현"""
    a_st = gates.get("A_seed", {}).get("status", "미도달")
    b_st = gates.get("B_grow", {}).get("status", "미도달")
    c_st = gates.get("C_handoff", {}).get("status", "미도달")
    return f"A: {a_st}  →  B: {b_st}  →  C: {c_st}"


def _highest_gate_label(gates: dict) -> str:
    c = gates.get("C_handoff", {}).get("status", "")
    b = gates.get("B_grow", {}).get("status", "")
    a = gates.get("A_seed", {}).get("status", "")
    if c in ("진행중", "통과"):
        return "C"
    if b == "통과":
        return "B통과"
    if b in ("분별 중", "분별중", "유지"):
        return "B진행"
    if a == "통과":
        return "A"
    return "준비중"


def _charter_completion(proj: ProjectCharter) -> float:
    checks = [
        bool(proj.calling and proj.calling.strip()),
        bool(proj.discernment),
        bool(proj.companionship and proj.companionship.strip()),
        bool(proj.practice_template),
        bool(proj.fruit_evidence),
        bool(proj.delegation),
        bool(proj.review_rhythm and proj.review_rhythm.strip()),
        bool(proj.boundaries),
        bool(proj.handoff_condition and proj.handoff_condition.strip()),
        bool(proj.exit_condition and proj.exit_condition.strip()),
    ]
    return sum(checks) / 10


def _completion_bar(pct: float) -> str:
    filled = round(pct * 10)
    return "■" * filled + "□" * (10 - filled) + f" {int(pct * 100)}%"


# ── 일정 헬퍼 ────────────────────────────────────────────


def _active_months(sched_items: list[dict]) -> set[int]:
    """schedule 항목 목록에서 활성 월 집합 반환"""
    months: set[int] = set()
    for s in sched_items:
        freq = s.get("freq", "")
        if freq in ("monthly", "weekly"):
            months.update(range(1, 13))
        elif freq == "quarterly":
            months.update(s.get("months", []))
        elif freq == "annual":
            m = s.get("month", 0)
            if m:
                months.add(m)
        # irregular → skip
    return months


def _milestone_months(sched_items: list[dict]) -> list[tuple[int, str]]:
    """(월, 레이블) 튜플 목록 — annual/quarterly 이벤트만"""
    result: list[tuple[int, str]] = []
    for s in sched_items:
        label = s.get("label", "")
        freq = s.get("freq", "")
        if freq == "annual":
            m = s.get("month", 0)
            if m:
                result.append((m, label))
        elif freq == "quarterly":
            for m in s.get("months", []):
                result.append((m, label))
    return result


# ── Google Sheets 서식 헬퍼 ──────────────────────────────

GANTT_COLS = 16       # A~P
PROJECT_TAB_COLS = 14  # A~N


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
    fields: list[str] = []
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

    if va := kwargs.get("v_align"):
        cell_format["verticalAlignment"] = va
        fields.append("userEnteredFormat.verticalAlignment")

    if nf := kwargs.get("num_fmt"):
        cell_format["numberFormat"] = {"type": "NUMBER", "pattern": nf}
        fields.append("userEnteredFormat.numberFormat")

    if kwargs.get("borders"):
        bs = {"style": "SOLID", "color": _hex_to_rgb("#CCCCCC")}
        cell_format["borders"] = {
            "top": bs, "bottom": bs, "left": bs, "right": bs
        }
        fields.append("userEnteredFormat.borders")

    if kwargs.get("wrap"):
        cell_format["wrapStrategy"] = "WRAP"
        fields.append("userEnteredFormat.wrapStrategy")

    if not fields:
        return {}

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


def _row_fmt(sheet_id: int, row: int, col_end: int | None = None, **kwargs: Any) -> dict:
    return _cell_fmt(sheet_id, row, 0, col_end, **kwargs)


def _merge(sheet_id: int, row: int, col_start: int = 0, col_end: int = PROJECT_TAB_COLS) -> dict:
    return {
        "mergeCells": {
            "range": {
                "sheetId": sheet_id,
                "startRowIndex": row,
                "endRowIndex": row + 1,
                "startColumnIndex": col_start,
                "endColumnIndex": col_end,
            },
            "mergeType": "MERGE_ALL",
        }
    }


def _set_row_height(sheet_id: int, row: int, px: int) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id, "dimension": "ROWS",
                "startIndex": row, "endIndex": row + 1,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


def _set_col_widths(sheet_id: int, widths: list[int]) -> list[dict]:
    return [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id, "dimension": "COLUMNS",
                    "startIndex": i, "endIndex": i + 1,
                },
                "properties": {"pixelSize": px},
                "fields": "pixelSize",
            }
        }
        for i, px in enumerate(widths)
    ]


def _freeze(sheet_id: int, rows: int = 0, cols: int = 0) -> dict:
    props: dict[str, Any] = {}
    fields_list: list[str] = []
    if rows:
        props["frozenRowCount"] = rows
        fields_list.append("gridProperties.frozenRowCount")
    if cols:
        props["frozenColumnCount"] = cols
        fields_list.append("gridProperties.frozenColumnCount")
    return {
        "updateSheetProperties": {
            "properties": {
                "sheetId": sheet_id,
                "gridProperties": props,
            },
            "fields": ",".join(fields_list),
        }
    }


# ════════════════════════════════════════════════════════
# 탭 1: 전체 현황 (간트)
# 16열: A=항목명(180) B=층(55) C=Gate(80) D=월예산(90) E~P=월1~12(38each)
# ════════════════════════════════════════════════════════

GANTT_COL_WIDTHS = [180, 55, 80, 90] + [38] * 12  # 16 cols total
MONTH_LABELS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
BLOCK_FULL = "██"
BLOCK_LIGHT = "░░"


def _gantt_row(name: str, tier_label: str, gate: str, monthly: int,
               active: set[int]) -> list:
    cells = [name, tier_label, gate, monthly if monthly else ""]
    for m in range(1, 13):
        cells.append(BLOCK_FULL if m in active else "")
    return cells


def _build_gantt_layout(tiers: list[TierCharters]) -> dict:
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")

    values: list[list] = []
    row_meta: list[tuple] = []

    # ── Row 0: 제목
    title_row = ["전체 현황"] + [""] * 3 + MONTH_LABELS
    title_row[-1] = f"배포: {today}"  # 마지막 열(P)에 배포일
    values.append(title_row)
    row_meta.append(("title", None, None))

    # ── Row 1: 컬럼 헤더
    values.append(["항목명", "층", "Gate", "월예산"] + MONTH_LABELS)
    row_meta.append(("col_header", None, None))

    for tier in tiers:
        # ── 층 배너
        banner_row = [f"{tier.tier_priority}층 — {tier.tier_name}"] + [""] * 15
        values.append(banner_row)
        row_meta.append(("tier_banner", tier, None))

        # ── 루틴 행
        for routine in tier.routines:
            active = _active_months(routine.schedule)
            if not active:
                active = set(range(1, 13))  # 루틴은 기본 전월
            values.append(_gantt_row(
                routine.name,
                f"{tier.tier_priority}층",
                "루틴",
                routine.monthly,
                active,
            ))
            row_meta.append(("routine", tier, {"routine": routine}))

        # ── 프로젝트 행 + 마일스톤 행
        for proj in tier.projects:
            gate_text, _, _ = _gate_info(proj.gates)
            # 프로젝트 기간: 일정이 있으면 그 활성 월, 없으면 전월
            if proj.schedule:
                proj_active = _active_months(proj.schedule)
                if not proj_active:
                    proj_active = set(range(1, 13))
            else:
                proj_active = set(range(1, 13))

            values.append(_gantt_row(
                proj.name,
                f"{tier.tier_priority}층",
                gate_text,
                proj.monthly,
                proj_active,
            ))
            row_meta.append(("project", tier, {"project": proj}))

            # 마일스톤 행
            for (m, label) in _milestone_months(proj.schedule):
                ms_row = [f"  └ {label}"] + ["", "", ""]
                for i in range(1, 13):
                    ms_row.append(BLOCK_FULL if i == m else "")
                values.append(ms_row)
                row_meta.append(("milestone", tier, {"month": m}))

        # ── 루틴 마일스톤
        for routine in tier.routines:
            for (m, label) in _milestone_months(routine.schedule):
                ms_row = [f"  └ {routine.name}/{label}"] + ["", "", ""]
                for i in range(1, 13):
                    ms_row.append(BLOCK_FULL if i == m else "")
                values.append(ms_row)
                row_meta.append(("milestone", tier, {"month": m}))

        # ── 층 소계
        tier_monthly = (
            sum(r.monthly for r in tier.routines)
            + sum(p.monthly for p in tier.projects)
        )
        subtotal = [f"{tier.tier_name} 소계", "", "", tier_monthly] + [""] * 12
        values.append(subtotal)
        row_meta.append(("tier_subtotal", tier, None))

        # ── 빈 행
        values.append([""] * 16)
        row_meta.append(("blank", None, None))

    # ── 총계
    grand_total = sum(
        sum(r.monthly for r in t.routines) + sum(p.monthly for p in t.projects)
        for t in tiers
    )
    values.append(["전체 합계", "", "", grand_total] + [""] * 12)
    row_meta.append(("total", None, None))

    return {"values": values, "row_meta": row_meta}


def _apply_gantt_fmt(sheet_id: int, layout: dict) -> list[dict]:
    fmt: list[dict] = []
    fmt.extend(_set_col_widths(sheet_id, GANTT_COL_WIDTHS))
    fmt.append(_freeze(sheet_id, rows=2, cols=1))

    for ri, (rtype, tier_obj, extra) in enumerate(layout["row_meta"]):
        if rtype == "title":
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg="#263238", bold=True, font_size=14, font_color="#FFFFFF"))
            # 월 라벨 강조
            for ci in range(4, 16):
                fmt.append(_cell_fmt(sheet_id, ri, ci, ci + 1,
                                     h_align="CENTER", font_size=9,
                                     font_color="#90A4AE", bg="#263238"))
        elif rtype == "col_header":
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg="#37474F", bold=True, font_size=9,
                                font_color="#ECEFF1", h_align="CENTER"))
            fmt.append(_cell_fmt(sheet_id, ri, 0, 1,
                                 h_align="LEFT", bg="#37474F",
                                 bold=True, font_color="#ECEFF1"))
            fmt.append(_cell_fmt(sheet_id, ri, 3, 4,
                                 h_align="RIGHT", bg="#37474F",
                                 bold=True, font_color="#ECEFF1"))
        elif rtype == "tier_banner" and tier_obj:
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg=tier_obj.color_header,
                                bold=True, font_size=11, font_color="#FFFFFF"))
            fmt.append(_set_row_height(sheet_id, ri, 30))
        elif rtype == "routine" and tier_obj:
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg="#F5F5F5", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, 1, 2,
                                 font_size=9, font_color="#9E9E9E", h_align="CENTER"))
            fmt.append(_cell_fmt(sheet_id, ri, 2, 3,
                                 font_size=8, font_color="#BDBDBD", h_align="CENTER"))
            fmt.append(_cell_fmt(sheet_id, ri, 3, 4,
                                 h_align="RIGHT", num_fmt="#,##0", font_size=9))
            for ci in range(4, 16):
                fmt.append(_cell_fmt(sheet_id, ri, ci, ci + 1,
                                     h_align="CENTER", font_color="#78909C",
                                     font_size=8, bg="#F5F5F5"))
        elif rtype == "project" and tier_obj:
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg=tier_obj.color_bg, borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, 0, 1,
                                 bold=True, font_color=tier_obj.color_header))
            fmt.append(_cell_fmt(sheet_id, ri, 1, 2,
                                 font_size=9, font_color=tier_obj.color_header, h_align="CENTER"))
            gate_text, gate_bg, gate_fg = _gate_info(
                extra["project"].gates if extra else {}
            )
            fmt.append(_cell_fmt(sheet_id, ri, 2, 3,
                                 bg=gate_bg, font_color=gate_fg,
                                 bold=True, font_size=9, h_align="CENTER"))
            fmt.append(_cell_fmt(sheet_id, ri, 3, 4,
                                 h_align="RIGHT", num_fmt="#,##0", font_size=9))
            for ci in range(4, 16):
                fmt.append(_cell_fmt(sheet_id, ri, ci, ci + 1,
                                     h_align="CENTER", font_color=tier_obj.color_header,
                                     font_size=9, bg=tier_obj.color_bg))
        elif rtype == "milestone" and tier_obj:
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg="#FAFAFA", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, 0, 1,
                                 font_size=8, font_color="#9E9E9E"))
            m = (extra or {}).get("month", 0)
            if m:
                ci = 3 + m  # col 4 = month 1
                fmt.append(_cell_fmt(sheet_id, ri, ci, ci + 1,
                                     h_align="CENTER", font_color="#37474F",
                                     bold=True, bg="#E3F2FD"))
            fmt.append(_set_row_height(sheet_id, ri, 22))
        elif rtype == "tier_subtotal" and tier_obj:
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg=tier_obj.color_header,
                                bold=True, font_color="#FFFFFF"))
            fmt.append(_cell_fmt(sheet_id, ri, 3, 4,
                                 h_align="RIGHT", num_fmt="#,##0",
                                 bold=True, font_color="#FFFFFF"))
            fmt.append(_set_row_height(sheet_id, ri, 28))
        elif rtype == "total":
            fmt.append(_row_fmt(sheet_id, ri, GANTT_COLS,
                                bg="#263238", bold=True, font_color="#FFFFFF",
                                font_size=11))
            fmt.append(_cell_fmt(sheet_id, ri, 3, 4,
                                 h_align="RIGHT", num_fmt="#,##0",
                                 bold=True, font_color="#FFFFFF"))

    return [f for f in fmt if f]


# ════════════════════════════════════════════════════════
# 탭 2+: 프로젝트 모니터링 탭
# 14열 (A~N)
# A=레이블(150) B~M=내용(55each, 타임라인 월) N=여백(60)
# 비타임라인 섹션: B~G(좌), H~N(우) 로 분할 병합
# ════════════════════════════════════════════════════════

PROJECT_TAB_COL_WIDTHS = [150] + [55] * 12 + [60]  # A + B~M(12 months) + N

# col 인덱스 상수
A = 0
B = 1
G = 6
H = 7
N_COL = 13
FULL_END = 14  # PROJECT_TAB_COLS


def _build_project_tab_layout(tier: TierCharters, proj: ProjectCharter) -> dict:
    """프로젝트 탭 레이아웃 (9개 섹션)"""
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")

    values: list[list] = []
    row_meta: list[tuple] = []

    def _empty():
        return [""] * FULL_END

    def _add(row, meta):
        values.append(row)
        row_meta.append(meta)

    pct = _charter_completion(proj)

    # ══════════════════════════════════════
    # [1] HEADER
    # ══════════════════════════════════════

    # 프로젝트명 (크게)
    title_row = _empty()
    title_row[A] = proj.name
    _add(title_row, ("header_title", None))

    # 층 정보
    tier_row = _empty()
    tier_row[A] = f"{tier.tier_priority}층 · {tier.tier_name}  |  {tier.philosophy}"
    _add(tier_row, ("header_tier", None))

    # 부르심 한줄
    calling_row = _empty()
    calling_row[A] = "부르심"
    calling_row[B] = proj.calling.replace("\n", " ").strip()
    _add(calling_row, ("header_calling", None))

    # Gate 상태
    gate_row = _empty()
    gate_row[A] = "Gate"
    a_st = proj.gates.get("A_seed", {}).get("status", "미도달")
    b_st = proj.gates.get("B_grow", {}).get("status", "미도달")
    c_st = proj.gates.get("C_handoff", {}).get("status", "미도달")
    gate_row[B] = f"A: {a_st}"
    gate_row[H // 2] = f"→ B: {b_st}"  # roughly col 3~4
    gate_row[H] = f"→ C: {c_st}"
    _add(gate_row, ("header_gate", {"a": a_st, "b": b_st, "c": c_st}))

    # 지표
    metrics_row = _empty()
    metrics_row[A] = "지표"
    metrics_row[B] = f"월예산  {proj.monthly:,}원"
    metrics_row[H // 2 + 1] = f"헌장완성도  {_completion_bar(pct)}"
    metrics_row[H] = f"회고주기  {proj.review_rhythm}"
    _add(metrics_row, ("header_metrics", None))

    # ══════════════════════════════════════
    # [2] MISSION
    # ══════════════════════════════════════
    sec_row = _empty()
    sec_row[A] = "MISSION"
    _add(sec_row, ("section_header", {"color": tier.color_header}))

    calling_full = _empty()
    calling_full[A] = "부르심"
    calling_full[B] = proj.calling.strip()
    _add(calling_full, ("mission_calling", None))

    # ══════════════════════════════════════
    # [3] GATE B (분별 정보)
    # ══════════════════════════════════════
    b_gate = proj.gates.get("B_grow", {})
    b_question = b_gate.get("question", "")
    b_paths = b_gate.get("possible_paths", [])
    b_method = b_gate.get("discernment_method", proj.discernment.get("method", ""))
    b_timing = b_gate.get("check_timing", proj.review_rhythm)

    b_status = b_gate.get("status", "")
    gate_b_active = b_status in ("분별 중", "분별중", "유지")

    gate_b_hdr = _empty()
    gate_b_hdr[A] = "GATE B — 분별"
    if b_status:
        gate_b_hdr[B] = f"현재 상태: {b_status}"
    _add(gate_b_hdr, ("section_header_gate_b", {"active": gate_b_active}))

    # 핵심 질문
    q_row = _empty()
    q_row[A] = "핵심 질문"
    q_row[B] = b_question or "(없음)"
    _add(q_row, ("gate_b_question", {"active": gate_b_active}))

    # 분별 경로
    if b_paths:
        path_hdr = _empty()
        path_hdr[A] = ""
        path_hdr[B] = "경로명"
        path_hdr[H] = "설명"
        path_hdr[N_COL] = "투자"
        _add(path_hdr, ("gate_b_path_header", None))

        for path in b_paths:
            path_row = _empty()
            path_row[A] = ""
            path_row[B] = path.get("name", "")
            path_row[H] = path.get("description", "")
            path_row[N_COL] = path.get("investment", "")
            _add(path_row, ("gate_b_path_row", {"active": gate_b_active}))

    # 분별 방법
    method_row = _empty()
    method_row[A] = "분별방법"
    method_row[B] = b_method
    method_row[N_COL] = b_timing
    _add(method_row, ("gate_b_method", None))

    # ══════════════════════════════════════
    # [4] TIMELINE
    # ══════════════════════════════════════
    tl_sec = _empty()
    tl_sec[A] = "TIMELINE"
    _add(tl_sec, ("section_header", {"color": tier.color_header}))

    # 컬럼 헤더 (B~M = 월 1~12)
    tl_hdr = _empty()
    tl_hdr[A] = "항목"
    for i, m in enumerate(range(1, 13)):
        tl_hdr[B + i] = str(m)
    _add(tl_hdr, ("timeline_header", None))

    # 프로젝트 전체 기간 (░░)
    if proj.schedule:
        proj_active = _active_months(proj.schedule)
        if not proj_active:
            proj_active = set(range(1, 13))
    else:
        proj_active = set(range(1, 13))

    proj_tl = _empty()
    proj_tl[A] = proj.name
    for i, m in enumerate(range(1, 13)):
        proj_tl[B + i] = BLOCK_LIGHT if m in proj_active else ""
    _add(proj_tl, ("timeline_project", {"tier": tier}))

    # 마일스톤 행 (██)
    for (m, label) in _milestone_months(proj.schedule):
        ms_tl = _empty()
        ms_tl[A] = f"  └ {label}"
        for i, mi in enumerate(range(1, 13)):
            ms_tl[B + i] = BLOCK_FULL if mi == m else ""
        _add(ms_tl, ("timeline_milestone", {"tier": tier, "month": m}))

    # ══════════════════════════════════════
    # [5] ACTIONS  |  [6] BOUNDARIES (side-by-side)
    # ══════════════════════════════════════
    left_sec = _empty()
    left_sec[A] = "ACTIONS"
    left_sec[H] = "BOUNDARIES"
    _add(left_sec, ("section_header_dual", {"color": tier.color_header}))

    actions = proj.next_actions
    bd = proj.boundaries
    boundary_items = []
    if bd:
        if bd.get("money"):
            boundary_items.append(f"💰 {bd['money']}")
        if bd.get("time"):
            boundary_items.append(f"⏱ {bd['time']}")
        if bd.get("role"):
            boundary_items.append(f"👤 {bd['role']}")
        if bd.get("value"):
            boundary_items.append(f"💡 {bd['value']}")

    max_rows = max(len(actions), len(boundary_items), 1)
    for i in range(max_rows):
        ab_row = _empty()
        if i < len(actions):
            ab_row[A] = f"□ {actions[i]}"
        if i < len(boundary_items):
            ab_row[H] = boundary_items[i]
        _add(ab_row, ("actions_boundary_row", {"tier": tier}))

    # ══════════════════════════════════════
    # [7] FRUIT EVIDENCE  |  [8] DELEGATION (side-by-side)
    # ══════════════════════════════════════
    fe_sec = _empty()
    fe_sec[A] = "FRUIT EVIDENCE"
    fe_sec[H] = "DELEGATION"
    _add(fe_sec, ("section_header_dual", {"color": tier.color_header}))

    fe = proj.fruit_evidence
    dlg = proj.delegation

    fe_items = []
    if fe.get("qualitative"):
        fe_items.append(f"질적: {fe['qualitative']}")
    if fe.get("quantitative"):
        fe_items.append(f"양적: {fe['quantitative']}")

    dlg_items = []
    if dlg.get("current"):
        dlg_items.append(f"현재 역할: {dlg['current']}")
    if dlg.get("track"):
        dlg_items.append(f"트랙: {dlg['track']}")
    if proj.review_rhythm:
        dlg_items.append(f"회고주기: {proj.review_rhythm}")

    max_rows2 = max(len(fe_items), len(dlg_items), 1)
    for i in range(max_rows2):
        fd_row = _empty()
        if i < len(fe_items):
            fd_row[A] = fe_items[i]
        if i < len(dlg_items):
            fd_row[H] = dlg_items[i]
        _add(fd_row, ("fruit_delegation_row", {"tier": tier}))

    # ══════════════════════════════════════
    # [9] FEEDBACK (사용자 입력 영역)
    # ══════════════════════════════════════
    fb_sec = _empty()
    fb_sec[A] = "📝 FEEDBACK"
    fb_sec[N_COL] = f"최종 배포: {today}"
    _add(fb_sec, ("section_header_feedback", None))

    feedback_labels = [
        "날짜",
        "잘 된 것",
        "안 된 것",
        "배운 것",
        "Gate 변경?",
        "다음 액션",
    ]
    for label in feedback_labels:
        fb_row = _empty()
        fb_row[A] = label
        # B~N은 빈 입력 셀
        _add(fb_row, ("feedback_input_row", None))

    # 빈 행 (하단 여백)
    _add(_empty(), ("blank", None))

    return {"values": values, "row_meta": row_meta}


def _apply_project_tab_fmt(sheet_id: int, layout: dict, tier: TierCharters) -> list[dict]:
    fmt: list[dict] = []
    fmt.extend(_set_col_widths(sheet_id, PROJECT_TAB_COL_WIDTHS))
    fmt.append(_freeze(sheet_id, rows=5))

    for ri, (rtype, extra) in enumerate(layout["row_meta"]):
        if rtype == "header_title":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg=tier.color_header, bold=True, font_size=18,
                                font_color="#FFFFFF"))
            fmt.append(_merge(sheet_id, ri, A, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 40))

        elif rtype == "header_tier":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg=tier.color_bg, font_size=9,
                                font_color=tier.color_header))
            fmt.append(_merge(sheet_id, ri, A, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 22))

        elif rtype == "header_calling":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg="#FAFAFA", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=9, bold=True, font_color="#546E7A"))
            fmt.append(_cell_fmt(sheet_id, ri, B, FULL_END,
                                 font_size=9, font_color="#37474F", wrap=True))
            fmt.append(_merge(sheet_id, ri, B, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 36))

        elif rtype == "header_gate":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg="#ECEFF1", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=9, bold=True, font_color="#546E7A"))
            a_st = (extra or {}).get("a", "")
            b_st = (extra or {}).get("b", "")
            # A gate color
            a_color = "#2E7D32" if a_st == "통과" else "#9E9E9E"
            fmt.append(_cell_fmt(sheet_id, ri, B, H // 2,
                                 font_size=10, bold=True, font_color=a_color))
            b_color = "#F57F17" if b_st in ("분별 중", "분별중", "유지") else (
                "#1B5E20" if b_st == "통과" else "#9E9E9E"
            )
            fmt.append(_cell_fmt(sheet_id, ri, H // 2, H,
                                 font_size=10, bold=True, font_color=b_color))
            fmt.append(_cell_fmt(sheet_id, ri, H, FULL_END,
                                 font_size=10, font_color="#9E9E9E"))

        elif rtype == "header_metrics":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg="#ECEFF1", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=9, bold=True, font_color="#546E7A"))
            fmt.append(_cell_fmt(sheet_id, ri, B, H // 2 + 1,
                                 font_size=9, font_color="#37474F"))
            fmt.append(_cell_fmt(sheet_id, ri, H // 2 + 1, H,
                                 font_size=9, font_color="#37474F"))
            fmt.append(_cell_fmt(sheet_id, ri, H, FULL_END,
                                 font_size=9, font_color="#757575", wrap=True))
            fmt.append(_set_row_height(sheet_id, ri, 30))

        elif rtype == "section_header":
            color = (extra or {}).get("color", "#455A64")
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg=color, bold=True, font_size=10,
                                font_color="#FFFFFF"))
            fmt.append(_merge(sheet_id, ri, A, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 28))

        elif rtype == "section_header_gate_b":
            active = (extra or {}).get("active", False)
            bg = "#FFF9C4" if active else "#F5F5F5"
            fc = "#F57F17" if active else "#9E9E9E"
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg=bg, bold=True, font_size=10, font_color=fc))
            fmt.append(_merge(sheet_id, ri, A, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 28))

        elif rtype == "gate_b_question":
            active = (extra or {}).get("active", False)
            bg = "#FFFDE7" if active else "#FAFAFA"
            fc = "#E65100" if active else "#9E9E9E"
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg=bg, borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=9, bold=True,
                                 font_color="#F57F17" if active else "#9E9E9E"))
            fmt.append(_cell_fmt(sheet_id, ri, B, FULL_END,
                                 font_size=11, bold=active, font_color=fc,
                                 wrap=True))
            fmt.append(_merge(sheet_id, ri, B, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 50))

        elif rtype == "gate_b_path_header":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg="#F5F5F5", font_size=9, font_color="#9E9E9E",
                                bold=True, h_align="CENTER"))
            fmt.append(_merge(sheet_id, ri, B, H))
            fmt.append(_merge(sheet_id, ri, H, N_COL))
            fmt.append(_set_row_height(sheet_id, ri, 24))

        elif rtype == "gate_b_path_row":
            active = (extra or {}).get("active", False)
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg="#FAFAFA", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, B, H,
                                 bold=True, font_color=tier.color_header, wrap=True))
            fmt.append(_merge(sheet_id, ri, B, H))
            fmt.append(_cell_fmt(sheet_id, ri, H, N_COL,
                                 font_size=9, font_color="#455A64", wrap=True))
            fmt.append(_merge(sheet_id, ri, H, N_COL))
            fmt.append(_cell_fmt(sheet_id, ri, N_COL, FULL_END,
                                 font_size=9, font_color="#78909C",
                                 h_align="CENTER", bg="#ECEFF1"))
            fmt.append(_set_row_height(sheet_id, ri, 40))

        elif rtype == "gate_b_method":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg="#F5F5F5", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=9, bold=True, font_color="#546E7A"))
            fmt.append(_cell_fmt(sheet_id, ri, B, N_COL,
                                 font_size=9, font_color="#455A64", wrap=True))
            fmt.append(_merge(sheet_id, ri, B, N_COL))
            fmt.append(_cell_fmt(sheet_id, ri, N_COL, FULL_END,
                                 font_size=8, font_color="#9E9E9E"))

        elif rtype == "mission_calling":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg=tier.color_bg, borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=9, bold=True, font_color=tier.color_header))
            fmt.append(_cell_fmt(sheet_id, ri, B, FULL_END,
                                 font_size=10, font_color="#37474F", wrap=True))
            fmt.append(_merge(sheet_id, ri, B, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 70))

        elif rtype == "section_header_dual":
            color = (extra or {}).get("color", "#455A64")
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg=color))
            fmt.append(_cell_fmt(sheet_id, ri, A, H,
                                 bold=True, font_size=10, font_color="#FFFFFF", bg=color))
            fmt.append(_merge(sheet_id, ri, A, H))
            fmt.append(_cell_fmt(sheet_id, ri, H, FULL_END,
                                 bold=True, font_size=10, font_color="#FFFFFF", bg=color))
            fmt.append(_merge(sheet_id, ri, H, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 28))

        elif rtype == "actions_boundary_row":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg=tier.color_bg, borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, H,
                                 font_size=9, font_color="#37474F", wrap=True))
            fmt.append(_merge(sheet_id, ri, A, H))
            fmt.append(_cell_fmt(sheet_id, ri, H, FULL_END,
                                 font_size=9, font_color="#455A64", wrap=True))
            fmt.append(_merge(sheet_id, ri, H, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 36))

        elif rtype == "fruit_delegation_row":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg="#FAFAFA", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, H,
                                 font_size=9, font_color="#455A64", wrap=True))
            fmt.append(_merge(sheet_id, ri, A, H))
            fmt.append(_cell_fmt(sheet_id, ri, H, FULL_END,
                                 font_size=9, font_color="#546E7A", wrap=True))
            fmt.append(_merge(sheet_id, ri, H, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 36))

        elif rtype == "timeline_header":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg="#37474F", bold=True, font_size=9,
                                font_color="#ECEFF1", h_align="CENTER"))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 h_align="LEFT", bg="#37474F",
                                 bold=True, font_color="#ECEFF1"))
            fmt.append(_set_row_height(sheet_id, ri, 24))

        elif rtype == "timeline_project":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg=tier.color_bg, borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 bold=True, font_color=tier.color_header))
            for ci in range(B, N_COL):
                fmt.append(_cell_fmt(sheet_id, ri, ci, ci + 1,
                                     h_align="CENTER", font_color=tier.color_header,
                                     font_size=8))
            fmt.append(_set_row_height(sheet_id, ri, 28))

        elif rtype == "timeline_milestone":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg="#FAFAFA", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=8, font_color="#9E9E9E"))
            m = (extra or {}).get("month", 0)
            if m:
                ci = B + m - 1  # col B = month 1
                fmt.append(_cell_fmt(sheet_id, ri, ci, ci + 1,
                                     h_align="CENTER", font_color="#1565C0",
                                     bold=True, bg="#E3F2FD"))
            fmt.append(_set_row_height(sheet_id, ri, 22))

        elif rtype == "section_header_feedback":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END,
                                bg="#E8F5E9", bold=True, font_size=11,
                                font_color="#2E7D32"))
            fmt.append(_cell_fmt(sheet_id, ri, A, N_COL,
                                 bg="#E8F5E9", bold=True, font_size=11,
                                 font_color="#2E7D32"))
            fmt.append(_merge(sheet_id, ri, A, N_COL))
            fmt.append(_cell_fmt(sheet_id, ri, N_COL, FULL_END,
                                 font_size=8, font_color="#9E9E9E",
                                 h_align="RIGHT", bg="#E8F5E9"))
            fmt.append(_set_row_height(sheet_id, ri, 30))

        elif rtype == "feedback_input_row":
            fmt.append(_row_fmt(sheet_id, ri, FULL_END, bg="#F1F8E9"))
            fmt.append(_cell_fmt(sheet_id, ri, A, B,
                                 font_size=9, bold=True, font_color="#33691E",
                                 bg="#F1F8E9"))
            bs = {"style": "SOLID", "color": _hex_to_rgb("#A5D6A7")}
            input_fmt = {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": ri,
                        "endRowIndex": ri + 1,
                        "startColumnIndex": B,
                        "endColumnIndex": FULL_END,
                    },
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": _hex_to_rgb("#FFFFFF"),
                        "borders": {
                            "top": bs, "bottom": bs, "left": bs, "right": bs
                        },
                        "wrapStrategy": "WRAP",
                    }},
                    "fields": "userEnteredFormat.backgroundColor,"
                              "userEnteredFormat.borders,"
                              "userEnteredFormat.wrapStrategy",
                }
            }
            fmt.append(input_fmt)
            fmt.append(_merge(sheet_id, ri, B, FULL_END))
            fmt.append(_set_row_height(sheet_id, ri, 36))

    return [f for f in fmt if f]


# ════════════════════════════════════════════════════════
# 탭 3: relation 프로젝트 — 간소화 탭
# 4섹션: HEADER / CALLING+DEEPEN / ACTIONS+BOUNDARIES / FEEDBACK
# ════════════════════════════════════════════════════════

RELATION_TAB_COLS = 10  # A~J


def _build_relation_tab_layout(tier: TierCharters, proj: ProjectCharter) -> dict:
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")

    values: list[list] = []
    row_meta: list[tuple] = []
    W = RELATION_TAB_COLS

    def _e():
        return [""] * W

    def _add(row, meta):
        values.append(row)
        row_meta.append(meta)

    # ── [1] HEADER
    title = _e(); title[0] = proj.name
    _add(title, ("rel_title",))

    tier_row = _e(); tier_row[0] = f"{tier.tier_priority}층 · {tier.tier_name}"
    _add(tier_row, ("rel_tier",))

    gate_text, _, _ = _gate_info(proj.gates)
    b_q = proj.gates.get("B_grow", {}).get("question", "")
    gate_row = _e()
    gate_row[0] = "Gate"
    gate_row[1] = gate_text
    gate_row[5] = f"월 {proj.monthly:,}원" if proj.monthly else ""
    _add(gate_row, ("rel_gate", proj.gates))

    # ── [2] 부르심
    _add([f"부르심"] + [""] * (W - 1), ("rel_section", {"label": "부르심"}))

    calling_row = _e()
    calling_row[0] = proj.calling.strip()
    _add(calling_row, ("rel_calling",))

    # ── [3] 심화 질문 (Gate B)
    if b_q:
        _add(["심화 질문"] + [""] * (W - 1), ("rel_section", {"label": "심화"}))
        q_row = _e(); q_row[0] = b_q
        _add(q_row, ("rel_deepen",))

    # ── [4] ACTIONS + 경계
    actions_row = _e()
    actions_row[0] = "할 것"
    actions_row[5] = "경계"
    _add(actions_row, ("rel_dual_header",))

    bd = proj.boundaries
    boundary_items = []
    if bd.get("money"):  boundary_items.append(f"💰 {bd['money']}")
    if bd.get("time"):   boundary_items.append(f"⏱ {bd['time']}")
    if bd.get("role"):   boundary_items.append(f"👤 {bd['role']}")
    if bd.get("value"):  boundary_items.append(f"💡 {bd['value']}")

    max_r = max(len(proj.next_actions), len(boundary_items), 1)
    for i in range(max_r):
        row = _e()
        if i < len(proj.next_actions):
            row[0] = f"□ {proj.next_actions[i]}"
        if i < len(boundary_items):
            row[5] = boundary_items[i]
        _add(row, ("rel_ab_row", tier))

    # ── [5] FEEDBACK
    fb_hdr = _e(); fb_hdr[0] = "📝 FEEDBACK"; fb_hdr[W - 1] = f"배포: {today}"
    _add(fb_hdr, ("rel_fb_header",))

    for label in ["날짜", "잘 된 것", "안 된 것", "배운 것", "Gate 변경?", "다음 액션"]:
        fb_row = _e(); fb_row[0] = label
        _add(fb_row, ("rel_fb_input",))

    _add(_e(), ("blank",))

    return {"values": values, "row_meta": row_meta}


def _apply_relation_tab_fmt(sheet_id: int, layout: dict, tier: TierCharters) -> list[dict]:
    fmt: list[dict] = []
    W = RELATION_TAB_COLS
    col_widths = [240] + [80] * 4 + [240] + [80] * 4
    fmt.extend(_set_col_widths(sheet_id, col_widths))
    fmt.append(_freeze(sheet_id, rows=3))

    for ri, meta in enumerate(layout["row_meta"]):
        rtype = meta[0]

        if rtype == "rel_title":
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg=tier.color_header, bold=True, font_size=16,
                                font_color="#FFFFFF"))
            fmt.append(_merge(sheet_id, ri, 0, W))
            fmt.append(_set_row_height(sheet_id, ri, 38))

        elif rtype == "rel_tier":
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg=tier.color_bg, font_size=9,
                                font_color=tier.color_header))
            fmt.append(_merge(sheet_id, ri, 0, W))
            fmt.append(_set_row_height(sheet_id, ri, 20))

        elif rtype == "rel_gate":
            gates = meta[1] if len(meta) > 1 else {}
            gate_text, gate_bg, gate_fg = _gate_info(gates)
            fmt.append(_row_fmt(sheet_id, ri, W, bg="#ECEFF1", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, 0, 1,
                                 font_size=9, bold=True, font_color="#546E7A"))
            fmt.append(_cell_fmt(sheet_id, ri, 1, 4,
                                 bg=gate_bg, font_color=gate_fg, bold=True,
                                 font_size=10, h_align="CENTER"))
            fmt.append(_merge(sheet_id, ri, 1, 4))
            fmt.append(_cell_fmt(sheet_id, ri, 5, W,
                                 font_size=9, font_color="#546E7A", h_align="RIGHT"))
            fmt.append(_merge(sheet_id, ri, 5, W))

        elif rtype == "rel_section":
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg=tier.color_header, bold=True, font_size=10,
                                font_color="#FFFFFF"))
            fmt.append(_merge(sheet_id, ri, 0, W))
            fmt.append(_set_row_height(sheet_id, ri, 26))

        elif rtype == "rel_calling":
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg=tier.color_bg, borders=True, wrap=True))
            fmt.append(_cell_fmt(sheet_id, ri, 0, W,
                                 font_size=10, font_color="#37474F", wrap=True))
            fmt.append(_merge(sheet_id, ri, 0, W))
            fmt.append(_set_row_height(sheet_id, ri, 60))

        elif rtype == "rel_deepen":
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg="#FFFDE7", borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, 0, W,
                                 font_size=10, font_color="#E65100",
                                 bold=True, wrap=True))
            fmt.append(_merge(sheet_id, ri, 0, W))
            fmt.append(_set_row_height(sheet_id, ri, 48))

        elif rtype == "rel_dual_header":
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg=tier.color_header, bold=True, font_size=9,
                                font_color="#FFFFFF"))
            fmt.append(_cell_fmt(sheet_id, ri, 0, 5,
                                 bg=tier.color_header, bold=True, font_size=9,
                                 font_color="#FFFFFF"))
            fmt.append(_merge(sheet_id, ri, 0, 5))
            fmt.append(_cell_fmt(sheet_id, ri, 5, W,
                                 bg=tier.color_header, bold=True, font_size=9,
                                 font_color="#FFFFFF"))
            fmt.append(_merge(sheet_id, ri, 5, W))
            fmt.append(_set_row_height(sheet_id, ri, 26))

        elif rtype == "rel_ab_row":
            tier_obj = meta[1] if len(meta) > 1 else tier
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg=tier.color_bg, borders=True))
            fmt.append(_cell_fmt(sheet_id, ri, 0, 5,
                                 font_size=9, font_color="#37474F", wrap=True))
            fmt.append(_merge(sheet_id, ri, 0, 5))
            fmt.append(_cell_fmt(sheet_id, ri, 5, W,
                                 font_size=9, font_color="#455A64", wrap=True))
            fmt.append(_merge(sheet_id, ri, 5, W))
            fmt.append(_set_row_height(sheet_id, ri, 34))

        elif rtype == "rel_fb_header":
            fmt.append(_row_fmt(sheet_id, ri, W,
                                bg="#E8F5E9", bold=True, font_size=11,
                                font_color="#2E7D32"))
            fmt.append(_cell_fmt(sheet_id, ri, 0, W - 1,
                                 bg="#E8F5E9", bold=True, font_size=11,
                                 font_color="#2E7D32"))
            fmt.append(_merge(sheet_id, ri, 0, W - 1))
            fmt.append(_cell_fmt(sheet_id, ri, W - 1, W,
                                 font_size=8, font_color="#9E9E9E",
                                 h_align="RIGHT", bg="#E8F5E9"))
            fmt.append(_set_row_height(sheet_id, ri, 28))

        elif rtype == "rel_fb_input":
            fmt.append(_row_fmt(sheet_id, ri, W, bg="#F1F8E9"))
            fmt.append(_cell_fmt(sheet_id, ri, 0, 1,
                                 font_size=9, bold=True, font_color="#33691E"))
            bs = {"style": "SOLID", "color": _hex_to_rgb("#A5D6A7")}
            fmt.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": ri, "endRowIndex": ri + 1,
                        "startColumnIndex": 1, "endColumnIndex": W,
                    },
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": _hex_to_rgb("#FFFFFF"),
                        "borders": {"top": bs, "bottom": bs, "left": bs, "right": bs},
                        "wrapStrategy": "WRAP",
                    }},
                    "fields": "userEnteredFormat.backgroundColor,"
                              "userEnteredFormat.borders,"
                              "userEnteredFormat.wrapStrategy",
                }
            })
            fmt.append(_merge(sheet_id, ri, 1, W))
            fmt.append(_set_row_height(sheet_id, ri, 34))

    return [f for f in fmt if f]


# ════════════════════════════════════════════════════════
# 스프레드시트 생성/조회
# ════════════════════════════════════════════════════════


def _create_or_get_spreadsheet(service, title: str = "청지기 프로젝트 관리") -> str:
    sid = os.environ.get("PROJECT_SPREADSHEET_ID", "")
    if sid:
        return sid
    body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": "전체 현황"}}],
    }
    result = service.spreadsheets().create(body=body).execute()
    new_id = result["spreadsheetId"]
    url = result.get("spreadsheetUrl", "")
    print(f"신규 스프레드시트 생성됨: {url}")
    print(f"  → 환경변수에 저장하세요: export PROJECT_SPREADSHEET_ID={new_id}")
    return new_id


# ════════════════════════════════════════════════════════
# deploy
# ════════════════════════════════════════════════════════


GANTT_SHEET_TITLE = "전체 현황"


def deploy(tiers: list[TierCharters], force: bool = False) -> None:
    """스프레드시트에 전체 현황 + 프로젝트별 탭 생성"""
    from googleapiclient.discovery import build
    from app.adapters.google_auth import get_credentials

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = get_credentials(SCOPES)
    service = build("sheets", "v4", credentials=creds)

    spreadsheet_id = _create_or_get_spreadsheet(service)

    # 기존 시트 목록 조회
    resp = service.spreadsheets().get(
        spreadsheetId=spreadsheet_id,
        fields="sheets(properties(sheetId,title))"
    ).execute()
    existing: dict[str, int] = {
        s["properties"]["title"]: s["properties"]["sheetId"]
        for s in resp.get("sheets", [])
    }

    # 대상 탭 목록: 전체 현황 + 프로젝트별
    all_projects = [(tier, proj) for tier in tiers for proj in tier.projects]
    target_titles = [GANTT_SHEET_TITLE] + [proj.name for _, proj in all_projects]

    # 충돌 확인 및 삭제
    temp_sheet_id = None
    conflict = [t for t in target_titles if t in existing]
    if conflict:
        if not force:
            print(f"ERROR: 이미 존재하는 시트: {conflict}")
            print("  --force 옵션으로 재생성하세요.")
            sys.exit(1)
        # 스프레드시트는 항상 최소 1개 시트 필요 → 전체 삭제 시 임시 탭 먼저 생성
        needs_temp = len(conflict) >= len(existing)
        temp_sheet_id = None
        if needs_temp:
            tmp = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [{"addSheet": {"properties": {"title": "_tmp_"}}}]}
            ).execute()
            temp_sheet_id = tmp["replies"][0]["addSheet"]["properties"]["sheetId"]
        delete_requests = [{"deleteSheet": {"sheetId": existing[t]}} for t in conflict]
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": delete_requests}
        ).execute()
        print(f"기존 시트 삭제: {conflict}")

    # ── 전체 현황 (Gantt) 생성
    gantt_layout = _build_gantt_layout(tiers)
    gantt_values = gantt_layout["values"]

    result = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": [{
            "addSheet": {
                "properties": {
                    "title": GANTT_SHEET_TITLE,
                    "gridProperties": {
                        "rowCount": max(len(gantt_values) + 10, 50),
                        "columnCount": GANTT_COLS,
                    },
                    "index": 0,
                }
            }
        }]}
    ).execute()
    gantt_sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
    print(f"시트 생성: {GANTT_SHEET_TITLE} (ID: {gantt_sheet_id}, {len(gantt_values)}행)")

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{GANTT_SHEET_TITLE}'!A1",
        valueInputOption="USER_ENTERED",
        body={"values": gantt_values},
    ).execute()

    gantt_fmt = _apply_gantt_fmt(gantt_sheet_id, gantt_layout)
    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={"requests": gantt_fmt},
    ).execute()
    print(f"  서식 적용 완료 ({len(gantt_fmt)}개 요청)")

    # ── 프로젝트별 탭 생성
    for tab_index, (tier, proj) in enumerate(all_projects, start=1):
        # project_type에 따라 렌더러 선택
        if proj.project_type == "relation":
            tab_layout = _build_relation_tab_layout(tier, proj)
            tab_cols = RELATION_TAB_COLS
            apply_fmt = lambda sid, layout, t: _apply_relation_tab_fmt(sid, layout, t)
        else:  # mission (기본)
            tab_layout = _build_project_tab_layout(tier, proj)
            tab_cols = PROJECT_TAB_COLS
            apply_fmt = lambda sid, layout, t: _apply_project_tab_fmt(sid, layout, t)

        tab_values = tab_layout["values"]
        type_label = "관계" if proj.project_type == "relation" else "사역"

        result = service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{
                "addSheet": {
                    "properties": {
                        "title": proj.name,
                        "gridProperties": {
                            "rowCount": max(len(tab_values) + 10, 50),
                            "columnCount": tab_cols,
                        },
                        "index": tab_index,
                    }
                }
            }]}
        ).execute()
        tab_sheet_id = result["replies"][0]["addSheet"]["properties"]["sheetId"]
        print(f"시트 생성: {proj.name} [{type_label}] (ID: {tab_sheet_id}, {len(tab_values)}행)")

        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{proj.name}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": tab_values},
        ).execute()

        tab_fmt = apply_fmt(tab_sheet_id, tab_layout, tier)
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": tab_fmt},
        ).execute()
        print(f"  서식 적용 완료 ({len(tab_fmt)}개 요청)")

    # 임시 탭 삭제
    if temp_sheet_id is not None:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"deleteSheet": {"sheetId": temp_sheet_id}}]}
        ).execute()

    print(f"\n배포 완료: https://docs.google.com/spreadsheets/d/{spreadsheet_id}")


# ════════════════════════════════════════════════════════
# export (피드백 → YAML 업데이트)
# ════════════════════════════════════════════════════════


def export_feedback(
    tiers: list[TierCharters],
    projects_dir: Path,
) -> None:
    """각 프로젝트 탭의 FEEDBACK 섹션 읽기 → YAML 업데이트"""
    from datetime import date
    from googleapiclient.discovery import build
    from app.adapters.google_auth import get_credentials

    sid = os.environ.get("PROJECT_SPREADSHEET_ID", "")
    if not sid:
        print("ERROR: PROJECT_SPREADSHEET_ID 환경변수 필요")
        sys.exit(1)

    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = get_credentials(SCOPES)
    service = build("sheets", "v4", credentials=creds)

    today = date.today().isoformat()

    # YAML 파일 → raw dict 매핑 (수정 후 저장용)
    yaml_raws: dict[Path, dict] = {}
    for yaml_path in sorted(projects_dir.glob("*.yaml")):
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_raws[yaml_path] = yaml.safe_load(f) or {}

    updated_count = 0

    for tier in tiers:
        for proj in tier.projects:
            # 프로젝트 탭 전체 읽기 (A열만)
            try:
                resp = service.spreadsheets().values().get(
                    spreadsheetId=sid,
                    range=f"'{proj.name}'!A1:N100",
                ).execute()
            except Exception as e:
                print(f"  SKIP {proj.name}: {e}")
                continue

            rows = resp.get("values", [])

            # FEEDBACK 배너 행 찾기
            fb_start = None
            for i, row in enumerate(rows):
                if row and "📝 FEEDBACK" in str(row[0]):
                    fb_start = i + 1  # 배너 다음 행부터 입력
                    break

            if fb_start is None:
                print(f"  SKIP {proj.name}: FEEDBACK 섹션 없음")
                continue

            # 6개 필드 읽기
            def _get_val(row_idx: int) -> str:
                if row_idx < len(rows):
                    row = rows[row_idx]
                    # B열(index 1) 이후 값 합치기
                    return " ".join(str(c) for c in row[1:] if c).strip()
                return ""

            fb_date = _get_val(fb_start)       # 날짜
            fb_good = _get_val(fb_start + 1)   # 잘 된 것
            fb_bad = _get_val(fb_start + 2)    # 안 된 것
            fb_learned = _get_val(fb_start + 3)  # 배운 것
            fb_gate = _get_val(fb_start + 4)   # Gate 변경?
            fb_actions = _get_val(fb_start + 5)  # 다음 액션

            # 값이 하나도 없으면 건너뜀
            has_content = any([fb_date, fb_good, fb_bad, fb_learned, fb_gate, fb_actions])
            if not has_content:
                print(f"  SKIP {proj.name}: FEEDBACK 입력 없음")
                continue

            print(f"  EXPORT {proj.name}:")

            # YAML raw에서 프로젝트 찾기
            target_proj_dict = None
            for yaml_path, raw in yaml_raws.items():
                for p in raw.get("projects", []):
                    if p.get("id") == proj.id:
                        target_proj_dict = p
                        break
                if target_proj_dict:
                    break

            if not target_proj_dict:
                print(f"    YAML에서 {proj.id} 찾을 수 없음")
                continue

            # Gate 변경 처리
            if fb_gate and fb_gate.strip() not in ("", "없음"):
                gate_change = fb_gate.strip()
                if "A→B" in gate_change or "A->B" in gate_change:
                    gates = target_proj_dict.setdefault("gates", {})
                    gates.setdefault("B_grow", {})["status"] = "분별 중"
                    print(f"    Gate A→B 업데이트")
                elif "B→C" in gate_change or "B->C" in gate_change:
                    gates = target_proj_dict.setdefault("gates", {})
                    gates.setdefault("C_handoff", {})["status"] = "진행중"
                    print(f"    Gate B→C 업데이트")

            # 다음 액션 갱신
            if fb_actions:
                new_actions = [a.strip() for a in fb_actions.split("\n") if a.strip()]
                if new_actions:
                    target_proj_dict["next_actions"] = new_actions
                    print(f"    next_actions 갱신: {len(new_actions)}개")

            # 회고 이력 추가
            review_entry: dict[str, str] = {
                "date": fb_date or today,
            }
            if fb_good:
                review_entry["good"] = fb_good
            if fb_bad:
                review_entry["bad"] = fb_bad
            if fb_learned:
                review_entry["learned"] = fb_learned

            history = target_proj_dict.setdefault("review_history", [])
            history.append(review_entry)
            print(f"    review_history 추가: {review_entry['date']}")

            updated_count += 1

    # YAML 저장
    if updated_count > 0:
        for yaml_path, raw in yaml_raws.items():
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(raw, f, allow_unicode=True,
                          default_flow_style=False, sort_keys=False)
        print(f"\nYAML 업데이트 완료 ({updated_count}개 프로젝트)")
    else:
        print("\n업데이트할 피드백 없음")


# ── status (오프라인) ─────────────────────────────────────


def status(tiers: list[TierCharters]) -> None:
    print("=== 준서의 프로젝트 현황 ===\n")

    for tier in tiers:
        print(f"[{tier.tier_priority}층] {tier.tier_name}")
        if tier.philosophy:
            print(f"  철학: {tier.philosophy}")

        if tier.routines:
            print(f"  루틴 ({len(tier.routines)}개):")
            for r in tier.routines:
                print(f"    ○ {r.name}: {r.monthly:,}/월")

        if tier.projects:
            print(f"  프로젝트 ({len(tier.projects)}개):")
            for p in tier.projects:
                gate_text, _, _ = _gate_info(p.gates)
                pct = _charter_completion(p)
                bar = _completion_bar(pct)
                print(f"    ● {p.name}  [{gate_text}]  월 {p.monthly:,}  헌장 {bar}")
                b_q = p.gates.get("B_grow", {}).get("question", "")
                if b_q:
                    print(f"      분별 질문: {b_q}")
                if p.next_actions:
                    print(f"      → {p.next_actions[0]}")

        tier_total = (
            sum(r.monthly for r in tier.routines)
            + sum(p.monthly for p in tier.projects)
        )
        print(f"  ── 층 합계: 월 {tier_total:,}\n")

    grand = sum(
        sum(r.monthly for r in t.routines) + sum(p.monthly for p in t.projects)
        for t in tiers
    )
    print(f"총계: 월 {grand:,}")


# ── CLI ───────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="청지기 재정 프로젝트 헌장 관리",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  status     프로젝트 현황 요약 (로컬)
  deploy     Google Sheets에 전체 현황 + 프로젝트별 탭 생성
  export     각 프로젝트 탭 FEEDBACK → YAML 업데이트
        """,
    )
    parser.add_argument("command", choices=["deploy", "status", "export"])
    parser.add_argument(
        "--projects-dir", type=Path, default=Path("data/projects"),
        help="프로젝트 YAML 디렉토리",
    )
    parser.add_argument(
        "--config", type=Path, default=Path("data/budget_config.yaml"),
        help="budget config 경로",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="deploy 시 기존 시트 삭제 후 재생성",
    )

    args = parser.parse_args()

    tiers = load_all_projects(args.projects_dir, args.config)
    if not tiers:
        print(f"ERROR: {args.projects_dir} 에서 YAML 파일을 찾을 수 없습니다.")
        return 1

    if args.command == "status":
        status(tiers)
        return 0

    elif args.command == "deploy":
        deploy(tiers, force=args.force)
        return 0

    elif args.command == "export":
        export_feedback(tiers, args.projects_dir)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
