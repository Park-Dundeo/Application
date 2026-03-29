"""
청지기 일정 파이프라인 (Schedule)

data/projects/*.yaml의 schedule 섹션을 읽어서:
  - Google Calendar에 연간 일정 이벤트 생성 (deploy)
  - Calendar + 가계부 내역으로 월간 이행 확인 (check)
  - 연간 일정 텍스트 뷰 (status)

사용법:
  python3 -m app.pipeline.schedule status [--year 2026]
  python3 -m app.pipeline.schedule deploy [--year 2026] [--force]
  python3 -m app.pipeline.schedule check  [--year 2026] [--month 3]
"""

from __future__ import annotations

import argparse
import calendar as cal_mod
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import yaml


# ── 데이터 모델 ─────────────────────────────────────────

OPENCLAW_TAG = "openclaw_schedule"

MONTH_KR = ["1월", "2월", "3월", "4월", "5월", "6월",
             "7월", "8월", "9월", "10월", "11월", "12월"]


@dataclass
class ScheduleItem:
    label: str
    freq: str            # monthly | weekly | quarterly | annual | irregular
    track: str           # transaction | calendar
    budget_key: str = ""
    calendar_title: str = ""
    months: list[int] = field(default_factory=list)  # quarterly 적용 월
    month: int = 0       # annual 적용 월
    day: int = 0         # 특정 일 (monthly day:25 등)
    note: str = ""
    # 컨텍스트 (로더에서 채움)
    tier_id: str = ""
    tier_name: str = ""
    tier_priority: int = 0
    source_id: str = ""
    source_name: str = ""
    source_type: str = ""  # "project" | "routine"

    def applies_to_month(self, m: int) -> bool:
        """주어진 월에 이 항목이 적용되는지"""
        if self.freq in ("monthly", "weekly"):
            return True
        if self.freq == "quarterly":
            return m in self.months
        if self.freq == "annual":
            return m == self.month
        # irregular → transaction 추적이므로 "적용"으로 처리 (check에서 별도 구분)
        return False

    def active_months(self) -> list[int]:
        return [m for m in range(1, 13) if self.applies_to_month(m)]

    @property
    def event_title(self) -> str:
        return self.calendar_title or self.label


# ── YAML 로딩 ────────────────────────────────────────────


def _parse_entry(entry: dict, source_id: str, source_name: str,
                 source_type: str, tier_id: str, tier_name: str,
                 tier_priority: int, fallback_budget_key: str = "") -> ScheduleItem:
    label = entry.get("label", source_name)
    freq = entry.get("freq", "monthly")
    track = entry.get("track", "transaction")
    budget_key = entry.get("budget_key", fallback_budget_key)
    calendar_title = entry.get("calendar_title", "")
    months = entry.get("months", [])
    month = entry.get("month", 0)
    day = entry.get("day", 0)
    note = entry.get("note", "")

    return ScheduleItem(
        label=label,
        freq=freq,
        track=track,
        budget_key=budget_key,
        calendar_title=calendar_title,
        months=months,
        month=month,
        day=day,
        note=note,
        tier_id=tier_id,
        tier_name=tier_name,
        tier_priority=tier_priority,
        source_id=source_id,
        source_name=source_name,
        source_type=source_type,
    )


def load_all_schedules(projects_dir: Path | None = None,
                       budget_config_path: Path | None = None) -> list[ScheduleItem]:
    """data/projects/*.yaml 스캔 → ScheduleItem 목록 (tier priority 순)"""
    if projects_dir is None:
        projects_dir = Path("data/projects")
    if budget_config_path is None:
        budget_config_path = Path("data/budget_config.yaml")

    # budget_config에서 tier 메타 로드
    tier_meta: dict[str, dict] = {}
    if budget_config_path.exists():
        with open(budget_config_path, "r", encoding="utf-8") as f:
            bc = yaml.safe_load(f)
        for t in bc.get("tiers", []):
            tier_meta[t["id"]] = {
                "name": t.get("name", t["id"]),
                "priority": t.get("priority", 99),
            }

    items: list[ScheduleItem] = []

    for yf in sorted(projects_dir.glob("*.yaml")):
        tier_id = yf.stem
        meta = tier_meta.get(tier_id, {"name": tier_id, "priority": 99})
        tier_name = meta["name"]
        tier_priority = meta["priority"]

        with open(yf, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not raw:
            continue

        # ── 루틴
        for routine in raw.get("routines", []):
            sched = routine.get("schedule")
            if not sched:
                continue
            fallback_key = routine.get("budget_item", "")
            entries = [sched] if isinstance(sched, dict) else sched
            for entry in entries:
                items.append(_parse_entry(
                    entry=entry,
                    source_id=routine["id"],
                    source_name=routine.get("name", routine["id"]),
                    source_type="routine",
                    tier_id=tier_id,
                    tier_name=tier_name,
                    tier_priority=tier_priority,
                    fallback_budget_key=fallback_key,
                ))

        # ── 프로젝트
        for project in raw.get("projects", []):
            sched = project.get("schedule")
            if not sched:
                continue
            entries = sched if isinstance(sched, list) else [sched]
            for entry in entries:
                items.append(_parse_entry(
                    entry=entry,
                    source_id=project["id"],
                    source_name=project.get("name", project["id"]),
                    source_type="project",
                    tier_id=tier_id,
                    tier_name=tier_name,
                    tier_priority=tier_priority,
                ))

    items.sort(key=lambda x: (x.tier_priority, x.source_id))
    return items


# ── status (오프라인) ─────────────────────────────────────


def status_year(items: list[ScheduleItem], year: int) -> None:
    """연간 일정 텍스트 뷰 (로컬, Google 연결 없음)"""
    print(f"=== {year}년 프로젝트 일정 현황 ===\n")

    hdr = f"{'항목':<26}" + "".join(f"{m:>5}" for m in MONTH_KR)
    print(hdr)
    print("─" * len(hdr))

    current_tier = ""
    for item in items:
        if item.tier_id != current_tier:
            current_tier = item.tier_id
            print(f"\n  [{item.tier_priority}층] {item.tier_name}")

        icon = "💰" if item.track == "transaction" else "📅"
        display = f"  {icon} {item.source_name}/{item.label}"
        row = f"{display:<26}"

        for m in range(1, 13):
            if item.freq == "irregular":
                row += f"{'  ~':>5}"
            elif item.applies_to_month(m):
                row += f"{'  ●':>5}"
            else:
                row += f"{'  ·':>5}"
        print(row)

    print()
    cal_count = sum(1 for i in items if i.track == "calendar" and i.freq != "irregular")
    tx_count = sum(1 for i in items if i.track == "transaction" and i.freq != "irregular")
    irr_count = sum(1 for i in items if i.freq == "irregular")
    print(f"캘린더 이벤트 대상: {cal_count}개  |  거래 추적 정기: {tx_count}개  |  비정기: {irr_count}개")


# ── deploy (Google Calendar) ─────────────────────────────


def _get_cal_service():
    from googleapiclient.discovery import build
    from app.adapters.google_auth import get_credentials
    creds = get_credentials(["https://www.googleapis.com/auth/calendar"])
    return build("calendar", "v3", credentials=creds)


def _list_openclaw_events(service, calendar_id: str, year: int) -> list[dict]:
    """해당 연도의 openclaw 이벤트 조회"""
    time_min = f"{year}-01-01T00:00:00+09:00"
    time_max = f"{year}-12-31T23:59:59+09:00"
    events: list[dict] = []
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            privateExtendedProperty=f"openclaw={OPENCLAW_TAG}",
            singleEvents=True,
            pageToken=page_token,
        ).execute()
        events.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return events


def deploy_calendar(items: list[ScheduleItem], year: int,
                    calendar_id: str = "primary", force: bool = False) -> None:
    """Google Calendar에 연간 일정 이벤트 생성"""
    service = _get_cal_service()

    # 기존 이벤트 처리
    existing = _list_openclaw_events(service, calendar_id, year)
    if existing:
        if force:
            print(f"기존 OpenClaw 이벤트 삭제: {len(existing)}개")
            for ev in existing:
                service.events().delete(
                    calendarId=calendar_id, eventId=ev["id"]
                ).execute()
        else:
            print(f"INFO: 기존 OpenClaw 이벤트 {len(existing)}개 유지 (append 모드)")
            print("      --force 옵션으로 삭제 후 재생성 가능")

    # track=calendar이고 irregular가 아닌 항목만 이벤트 생성
    cal_items = [i for i in items if i.track == "calendar" and i.freq != "irregular"]
    created = 0

    for item in cal_items:
        for m in item.active_months():
            day = item.day if item.day else 1
            # 존재하지 않는 날짜 처리 (예: 2월 30일)
            last_day = cal_mod.monthrange(year, m)[1]
            day = min(day, last_day)
            event_date = date(year, m, day)

            body = {
                "summary": item.event_title,
                "description": (
                    f"[OpenClaw Schedule]\n"
                    f"층: {item.tier_priority}층 {item.tier_name}\n"
                    f"프로젝트: {item.source_name}\n"
                    f"주기: {item.freq}"
                    + (f"\n비고: {item.note}" if item.note else "")
                ),
                "start": {"date": event_date.isoformat()},
                "end": {"date": event_date.isoformat()},
                "extendedProperties": {
                    "private": {
                        "openclaw": OPENCLAW_TAG,
                        "tier_id": item.tier_id,
                        "source_id": item.source_id,
                        "label": item.label,
                    }
                },
            }
            service.events().insert(calendarId=calendar_id, body=body).execute()
            created += 1

    print(f"캘린더 이벤트 생성: {created}개")
    tx_count = sum(1 for i in items if i.track == "transaction")
    print(f"거래 추적 항목 {tx_count}개는 가계부 내역 K열로 자동 집계됩니다.")


# ── check (월간 이행 확인) ───────────────────────────────


def _get_month_transactions(sheet_service, spreadsheet_id: str,
                             year: int, month: int) -> list[dict]:
    """가계부 내역 시트에서 해당 월 거래 반환"""
    resp = sheet_service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range="'가계부 내역'!A:K",
    ).execute()
    rows = resp.get("values", [])

    result = []
    for row in rows[1:]:  # 헤더 제외
        if len(row) < 7:
            continue
        try:
            d = datetime.strptime(row[0], "%Y-%m-%d").date()
            if d.year != year or d.month != month:
                continue
            result.append({
                "date": d,
                "content": row[5] if len(row) > 5 else "",
                "amount": row[6] if len(row) > 6 else "",
                "budget_key": row[10] if len(row) > 10 else "",
            })
        except (ValueError, IndexError):
            continue
    return result


def check_month(items: list[ScheduleItem], year: int, month: int,
                spreadsheet_id: str, calendar_id: str = "primary") -> None:
    """월간 이행 확인: Calendar + 가계부 내역"""
    from googleapiclient.discovery import build
    from app.adapters.google_auth import get_credentials

    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]
    creds = get_credentials(SCOPES)
    cal_svc = build("calendar", "v3", credentials=creds)
    sheet_svc = build("sheets", "v4", credentials=creds)

    print(f"=== {year}년 {month}월 일정 이행 확인 ===\n")

    # ── Calendar 이벤트 조회
    last_day = cal_mod.monthrange(year, month)[1]
    time_min = f"{year}-{month:02d}-01T00:00:00+09:00"
    time_max = f"{year}-{month:02d}-{last_day:02d}T23:59:59+09:00"
    cal_resp = cal_svc.events().list(
        calendarId=calendar_id,
        timeMin=time_min,
        timeMax=time_max,
        privateExtendedProperty=f"openclaw={OPENCLAW_TAG}",
        singleEvents=True,
    ).execute()
    cal_events = cal_resp.get("items", [])
    cal_labels = {
        ev.get("extendedProperties", {}).get("private", {}).get("label", "")
        for ev in cal_events
    }
    cal_titles = {ev.get("summary", "") for ev in cal_events}

    # ── 거래 조회
    transactions = _get_month_transactions(sheet_svc, spreadsheet_id, year, month)
    tx_keys: dict[str, int] = {}
    for t in transactions:
        bk = t["budget_key"]
        if bk:
            tx_keys[bk] = tx_keys.get(bk, 0) + 1

    # ── 결과 출력
    print(f"{'항목':<32} {'추적':<6} 상태  메모")
    print("─" * 72)

    month_items = [i for i in items if i.freq != "irregular" and i.applies_to_month(month)]
    irr_items = [i for i in items if i.freq == "irregular"]

    done = 0

    for item in month_items:
        label = f"{item.source_name}/{item.label}"[:30]
        track_str = "거래" if item.track == "transaction" else "캘린더"

        if item.track == "transaction":
            count = tx_keys.get(item.budget_key, 0) if item.budget_key else 0
            ok = count > 0
            status = "✓" if ok else "✗"
            note = f"{count}건 (K={item.budget_key})" if ok else f"없음 (K={item.budget_key})"
        else:  # calendar
            ok = (item.label in cal_labels or item.event_title in cal_titles)
            status = "✓" if ok else "?"
            note = "이벤트 확인됨" if ok else "이벤트 없음 (수동 확인)"

        if ok:
            done += 1
        print(f"{label:<32} {track_str:<6} {status}     {note}")

    if irr_items:
        print("\n[비정기]")
        for item in irr_items:
            count = tx_keys.get(item.budget_key, 0) if item.budget_key else 0
            status = "✓" if count > 0 else "·"
            label = f"{item.source_name}/{item.label}"[:30]
            note = f"{count}건" if count > 0 else "이번달 없음"
            print(f"{label:<32} {'거래':<6} {status}     {note}")

    print()
    print(f"정기 항목 {len(month_items)}개 중 {done}개 확인 ({done/len(month_items)*100:.0f}%)"
          if month_items else "정기 항목 없음")

    cal_tx = sum(1 for t in transactions if t["budget_key"])
    print(f"이번달 가계부 거래: {len(transactions)}건 (예산 키 태그됨: {cal_tx}건)")


# ── CLI ──────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="청지기 일정 관리 (Calendar 연동)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  status    연간 일정 텍스트 뷰 (로컬)
  deploy    Google Calendar에 연간 이벤트 생성
  check     월간 일정 이행 확인 (Calendar + 가계부)
        """,
    )
    parser.add_argument("command", choices=["status", "deploy", "check"])
    parser.add_argument("--year", type=int, default=datetime.now().year,
                        help="대상 연도 (기본: 현재 연도)")
    parser.add_argument("--month", type=int, default=datetime.now().month,
                        help="대상 월 (check 전용, 기본: 현재 월)")
    parser.add_argument("--calendar-id", default="primary",
                        help="Google Calendar ID (기본: primary)")
    parser.add_argument("--force", action="store_true",
                        help="deploy 시 기존 이벤트 삭제 후 재생성")
    parser.add_argument("--projects-dir", type=Path, default=Path("data/projects"),
                        help="프로젝트 YAML 디렉토리")

    args = parser.parse_args()

    items = load_all_schedules(args.projects_dir)
    print(f"일정 항목 로드: {len(items)}개\n")

    if args.command == "status":
        status_year(items, args.year)
        return 0

    elif args.command == "deploy":
        deploy_calendar(items, args.year, args.calendar_id, args.force)
        return 0

    elif args.command == "check":
        sid = os.environ.get("SPREADSHEET_ID", "")
        if not sid:
            print("ERROR: SPREADSHEET_ID 환경변수 필요")
            return 1
        check_month(items, args.year, args.month, sid, args.calendar_id)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
