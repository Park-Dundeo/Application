"""
청소년 교육자 커리큘럼 진행현황 HTML 생성기
사용법: python3 -m app.pipeline.curriculum_html [--output path/to/output.html]
"""

import sys
import yaml
import argparse
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).parent.parent.parent
CURRICULUM_DIR = BASE / "data" / "youth" / "curriculum"
INDEX_FILE = CURRICULUM_DIR / "index.yaml"
NOTES_DIR = CURRICULUM_DIR / "notes"


def load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def status_class(status: str) -> str:
    return {
        "완료": "done",
        "진행중": "in-progress",
        "미시작": "not-started",
        "보류": "hold",
    }.get(status or "미시작", "not-started")


def status_label(status: str) -> str:
    return status or "미시작"


def calc_week_progress(weeks: list) -> tuple[int, int]:
    """(완료 주차, 전체 주차)"""
    total = len(weeks)
    done = sum(1 for w in weeks if (w or {}).get("status") == "완료")
    return done, total


def render_week_bar(weeks: list) -> str:
    if not weeks:
        return ""
    cells = []
    for w in weeks:
        s = (w or {}).get("status", "미시작")
        title = (w or {}).get("title") or f"{(w or {}).get('week', '')}주"
        cls = status_class(s)
        cells.append(f'<div class="week-cell {cls}" title="{title}"></div>')
    return f'<div class="week-bar">{"".join(cells)}</div>'


def render_sections_bar(sections: list) -> str:
    if not sections:
        return ""
    cells = []
    for sec in sections:
        date_read = (sec or {}).get("date_read", "")
        has_content = bool((sec or {}).get("key_points"))
        s = "완료" if (date_read and has_content) else ("진행중" if date_read else "미시작")
        title = (sec or {}).get("section", "")
        cls = status_class(s)
        cells.append(f'<div class="week-cell {cls}" title="{title}"></div>')
    return f'<div class="week-bar">{"".join(cells)}</div>'


def render_resource_card(meta: dict, res: dict) -> str:
    status = res.get("status", "미시작")
    title = res.get("title", meta.get("title", ""))
    source = res.get("source", "")
    note = res.get("note", "")
    instructor = res.get("instructor", "")

    # URL 수집 (단일 url 또는 url_intro/url_stage1 등 복수)
    urls = []
    for key, val in res.items():
        if key.startswith("url") and isinstance(val, str) and val.strip():
            label = {"url": "바로가기", "url_intro": "소개", "url_stage1": "1단계"}.get(key, key)
            urls.append((label, val.strip()))

    weeks = res.get("weeks") or []
    sections = res.get("sections") or []

    if weeks:
        done, total = calc_week_progress(weeks)
        progress_bar = render_week_bar(weeks)
        progress_text = f"{done} / {total} 주차 완료"
    elif sections:
        done = sum(1 for s in sections if (s or {}).get("date_read"))
        total = len(sections)
        progress_bar = render_sections_bar(sections)
        progress_text = f"{done} / {total} 섹션 완료"
    else:
        progress_bar = ""
        progress_text = ""

    # key_concepts 수집
    all_concepts = []
    for w in weeks:
        all_concepts.extend((w or {}).get("key_concepts") or [])
    for s in sections:
        all_concepts.extend((s or {}).get("key_points") or [])

    concepts_html = ""
    if all_concepts:
        tags = "".join(f'<span class="tag">{c}</span>' for c in all_concepts[:8])
        concepts_html = f'<div class="concepts">{tags}</div>'

    summary = res.get("summary") or {}
    core_insight = summary.get("core_insight", "")
    insight_html = f'<p class="core-insight">💡 {core_insight}</p>' if core_insight else ""

    links_html = ""
    if urls:
        link_tags = "".join(f'<a class="res-link" href="{u}" target="_blank">{l}</a>' for l, u in urls)
        links_html = f'<div class="res-links">{link_tags}</div>'

    return f"""
    <div class="resource-card {status_class(status)}">
      <div class="card-header">
        <div class="card-title">{title}</div>
        <span class="badge {status_class(status)}">{status_label(status)}</span>
      </div>
      <div class="card-meta">
        <span class="source">{source}</span>
        {"<span class='instructor'>" + instructor + "</span>" if instructor else ""}
      </div>
      {f'<div class="card-note">{note}</div>' if note else ""}
      {links_html}
      {f'<div class="progress-text">{progress_text}</div>' if progress_text else ""}
      {progress_bar}
      {concepts_html}
      {insight_html}
    </div>
    """


def render_notes_section() -> str:
    notes = sorted(NOTES_DIR.glob("*.yaml"))
    notes = [n for n in notes if not n.name.startswith("_")]
    if not notes:
        return '<p class="empty-note">아직 작성된 학습 노트가 없습니다.</p>'

    items = []
    for note_path in reversed(notes):
        data = load_yaml(note_path)
        date = data.get("date", note_path.stem[:10])
        resource = data.get("resource_id", "")
        title = data.get("title", note_path.stem)
        key_concepts = data.get("key_concepts") or []
        field_conn = data.get("field_connection", {}) or {}
        hypothesis = field_conn.get("hypothesis", "")

        tags = "".join(f'<span class="tag">{c}</span>' for c in key_concepts[:5])
        hyp_html = f'<p class="hypothesis">→ 가설: {hypothesis}</p>' if hypothesis else ""

        items.append(f"""
        <div class="note-item">
          <div class="note-header">
            <span class="note-date">{date}</span>
            <span class="note-resource">{resource}</span>
          </div>
          <div class="note-title">{title}</div>
          <div class="concepts">{tags}</div>
          {hyp_html}
        </div>
        """)

    return "".join(items)


def generate_html(index: dict, resources: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    core_list = index.get("core", [])
    supp_list = index.get("supplementary", [])

    # 전체 진행률
    total_core = len(core_list)
    done_core = sum(1 for c in core_list if resources.get(c["id"], {}).get("status") == "완료")
    in_progress_core = sum(1 for c in core_list if resources.get(c["id"], {}).get("status") == "진행중")
    pct = int(done_core / total_core * 100) if total_core else 0

    core_cards = ""
    for meta in core_list:
        res = resources.get(meta["id"], {})
        core_cards += render_resource_card(meta, res)

    supp_cards = ""
    for meta in supp_list:
        res = resources.get(meta["id"], {})
        supp_cards += render_resource_card(meta, res)

    notes_html = render_notes_section()

    goals = index.get("learning_goals") or []
    goals_html = "".join(f"<li>{g}</li>" for g in goals)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>청소년 교육자 커리큘럼 현황</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, 'Noto Sans KR', sans-serif; background: #f5f5f0; color: #2d2d2d; }}

  .header {{ background: #1a1a2e; color: #fff; padding: 32px 40px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 6px; }}
  .header .subtitle {{ font-size: 13px; color: #aaa; }}

  .overview {{ display: flex; gap: 20px; padding: 24px 40px; background: #fff; border-bottom: 1px solid #eee; }}
  .stat-box {{ flex: 1; text-align: center; padding: 16px; background: #f9f9f7; border-radius: 8px; }}
  .stat-box .num {{ font-size: 32px; font-weight: 700; color: #1a1a2e; }}
  .stat-box .label {{ font-size: 12px; color: #888; margin-top: 4px; }}

  .overall-bar {{ height: 6px; background: #e0e0e0; border-radius: 3px; margin: 8px 40px; }}
  .overall-bar-fill {{ height: 100%; background: #4caf82; border-radius: 3px; transition: width 0.3s; }}

  .section {{ padding: 28px 40px; }}
  .section-title {{ font-size: 15px; font-weight: 700; color: #555; margin-bottom: 16px; letter-spacing: 0.5px; text-transform: uppercase; }}

  .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}

  .resource-card {{ background: #fff; border-radius: 10px; padding: 20px; border: 1px solid #eee; border-left: 4px solid #ccc; }}
  .resource-card.done {{ border-left-color: #4caf82; }}
  .resource-card.in-progress {{ border-left-color: #f5a623; }}
  .resource-card.not-started {{ border-left-color: #d0d0d0; }}
  .resource-card.hold {{ border-left-color: #bbb; opacity: 0.7; }}

  .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; margin-bottom: 8px; }}
  .card-title {{ font-size: 14px; font-weight: 600; line-height: 1.4; flex: 1; }}
  .card-meta {{ font-size: 12px; color: #999; margin-bottom: 8px; display: flex; gap: 8px; }}
  .card-note {{ font-size: 12px; color: #888; background: #f9f9f7; padding: 6px 10px; border-radius: 4px; margin-bottom: 8px; }}

  .badge {{ font-size: 11px; padding: 2px 8px; border-radius: 12px; white-space: nowrap; font-weight: 600; }}
  .badge.done {{ background: #e6f7ef; color: #2e7d55; }}
  .badge.in-progress {{ background: #fff4e0; color: #b07000; }}
  .badge.not-started {{ background: #f0f0f0; color: #888; }}
  .badge.hold {{ background: #f0f0f0; color: #aaa; }}

  .res-links {{ display: flex; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }}
  .res-link {{ font-size: 12px; color: #4455cc; background: #eef2ff; padding: 2px 10px; border-radius: 10px; text-decoration: none; }}
  .res-link:hover {{ background: #dde5ff; }}

  .progress-text {{ font-size: 12px; color: #888; margin-bottom: 6px; }}
  .week-bar {{ display: flex; gap: 3px; flex-wrap: wrap; margin-bottom: 10px; }}
  .week-cell {{ width: 18px; height: 18px; border-radius: 3px; cursor: default; }}
  .week-cell.done {{ background: #4caf82; }}
  .week-cell.in-progress {{ background: #f5a623; }}
  .week-cell.not-started {{ background: #e0e0e0; }}

  .concepts {{ display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }}
  .tag {{ font-size: 11px; background: #eef2ff; color: #4455cc; padding: 2px 8px; border-radius: 10px; }}
  .core-insight {{ font-size: 12px; color: #555; margin-top: 8px; padding-top: 8px; border-top: 1px solid #f0f0f0; line-height: 1.5; }}

  .notes-list {{ display: flex; flex-direction: column; gap: 12px; }}
  .note-item {{ background: #fff; border-radius: 8px; padding: 16px; border: 1px solid #eee; }}
  .note-header {{ display: flex; gap: 12px; margin-bottom: 6px; }}
  .note-date {{ font-size: 12px; color: #888; }}
  .note-resource {{ font-size: 12px; color: #4455cc; background: #eef2ff; padding: 1px 8px; border-radius: 10px; }}
  .note-title {{ font-size: 14px; font-weight: 600; margin-bottom: 6px; }}
  .hypothesis {{ font-size: 12px; color: #555; margin-top: 6px; padding-top: 6px; border-top: 1px solid #f5f5f5; }}
  .empty-note {{ color: #aaa; font-size: 13px; padding: 16px 0; }}

  .goals ul {{ list-style: none; display: flex; flex-direction: column; gap: 8px; }}
  .goals li {{ font-size: 13px; color: #555; padding: 10px 14px; background: #fff; border-radius: 6px; border-left: 3px solid #4caf82; }}

  .footer {{ text-align: center; padding: 24px; font-size: 12px; color: #bbb; }}
</style>
</head>
<body>

<div class="header">
  <h1>청소년 교육자 커리큘럼 현황</h1>
  <div class="subtitle">생성일시: {now}</div>
</div>

<div class="overview">
  <div class="stat-box"><div class="num">{total_core}</div><div class="label">핵심 자료</div></div>
  <div class="stat-box"><div class="num">{done_core}</div><div class="label">완료</div></div>
  <div class="stat-box"><div class="num">{in_progress_core}</div><div class="label">진행중</div></div>
  <div class="stat-box"><div class="num">{pct}%</div><div class="label">전체 진행률</div></div>
</div>
<div class="overall-bar"><div class="overall-bar-fill" style="width:{pct}%"></div></div>

<div class="section">
  <div class="section-title">핵심 자료 (Core)</div>
  <div class="cards">{core_cards}</div>
</div>

<div class="section">
  <div class="section-title">보조 / 보류 자료</div>
  <div class="cards">{supp_cards}</div>
</div>

<div class="section goals">
  <div class="section-title">학습 목표</div>
  <ul>{goals_html}</ul>
</div>

<div class="section">
  <div class="section-title">학습 노트 ({len(list(p for p in NOTES_DIR.glob("*.yaml") if not p.name.startswith("_")))}건)</div>
  <div class="notes-list">{notes_html}</div>
</div>

<div class="footer">OpenClaw · 청지기 재정 시스템</div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(BASE / "curriculum.html"))
    args = parser.parse_args()

    index = load_yaml(INDEX_FILE)

    resources = {}
    all_items = list(index.get("core", [])) + list(index.get("supplementary", []))
    for meta in all_items:
        res_file = CURRICULUM_DIR / meta["file"]
        if res_file.exists():
            resources[meta["id"]] = load_yaml(res_file)

    html = generate_html(index, resources)

    out = Path(args.output)
    out.write_text(html, encoding="utf-8")
    print(f"생성 완료: {out}")


if __name__ == "__main__":
    main()
