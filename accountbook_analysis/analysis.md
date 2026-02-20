# 청지기 재정 시스템 — 프로젝트 현황

> 최종 업데이트: 2026-02-18

## 프로젝트 개요

개인 가계부 자동화 및 예산 관리 시스템. **청지기적 재정 철학** 기반.
- "맡겨진 것을 하나님의 뜻에 맞게 배분하는 것이 목표"
- 목표 주도 배분 / 연봉 내 설계, 부족 시 구함 / 투명한 추적

---

## 시스템 구성

### 1. OpenClaw Pipeline (완료, 크론잡 운영 중)
뱅크샐러드 → Gmail → 7단계 자동 파이프라인 → Google Sheets

```
ingest → unzip → normalize → dedup → apply → categorize → budget
```

- `app/main.py` — 파이프라인 실행 진입점
- `app/pipeline/` — 각 단계별 모듈
- `data/rules.json` — 900+ 분류 규칙
- `data/categories.json` — 44개 유효 카테고리
- **K열 태깅**이 전체 시스템의 핵심 연결고리

### 2. 예산 관리 (Config-Driven, 구현 완료)

```
계획 영역 (YAML + CLI)          현황 영역 (Google Sheets)
┌─────────────────────┐        ┌──────────────────────┐
│ data/               │        │ 준서의 인생 계획       │
│   budget_config.yaml│──deploy─→│  가계부 내역 (원장)  │
│   (구조의 원본)      │        │  예산안 시트 (5층 뷰) │
└─────────────────────┘        └──────────────────────┘
```

#### 5층 예산 구조 (목적 우선순위)

| 층 | 이름 | 철학 | 월 예산 |
|----|------|------|---------|
| 1층 | 하나님의 몫 | 먼저 드리고 나머지로 산다 | 145K |
| 2층 | 사명 프로젝트 | 목표가 예산을 이끈다 | 870K |
| 3층 | 청지기 운영 | 절약이 아니라 적정 관리 | 2,875K |
| 4층 | 성장 씨앗 | 미래 역량 투자 | 20K (+상여) |
| 5층 | 신뢰 여백 | 모자라면 구한다 | 930K |
| **합계** | | | **4,840K/월 · 58,080K/년** |

#### CLI 명령어

```bash
python3 -m app.pipeline.budget validate   # config 무결성 검증
python3 -m app.pipeline.budget status     # 층별 현황 (오프라인)
python3 -m app.pipeline.budget preview    # XLSX 미리보기
python3 -m app.pipeline.budget deploy     # Google Sheets 생성
python3 -m app.pipeline.budget deploy --force  # 재생성
```

#### 워크플로우 사이클

```
① 계획 (yaml) → ② 배포 (deploy) → ③ 추적 (자동) → ④ 점검 (리뷰) → ⑤ 조정 → ①
```

---

## 핵심 파일 구조

```
Application/
├── app/
│   ├── main.py                  # 파이프라인 진입점
│   ├── config.py                # AppConfig 설정
│   ├── adapters/
│   │   ├── google_auth.py       # OAuth 인증
│   │   ├── sheets.py            # Sheets API 래퍼
│   │   └── llm.py               # LLM 분류 보조
│   ├── pipeline/
│   │   ├── budget.py            # 예산 파이프라인 (config-driven)
│   │   ├── categorize.py        # K열 자동 태깅
│   │   ├── apply_sheet.py       # Sheets 기록
│   │   ├── ingest.py / unzip.py / normalize.py / dedup.py
│   │   └── __init__.py
│   └── utils/
│       ├── rules.py             # 규칙 엔진
│       └── ...
├── data/
│   ├── budget_config.yaml       # ★ 예산 구조 원본
│   ├── rules.json               # 분류 규칙 (900+)
│   ├── categories.json          # 유효 카테고리 (44개)
│   ├── budget_keywords.json     # 키워드 분류
│   └── google_token.json        # OAuth 토큰
├── accountbook_analysis/
│   ├── analysis.md              # ← 이 파일
│   ├── steward_finance_philosophy.md    # 철학 문서
│   ├── steward_finance_architecture.drawio  # 아키텍처 다이어그램 (3페이지)
│   ├── spreadsheet_structure.md         # 기존 시트 구조 분석
│   ├── new_budget_proposal.md           # 실적 기반 예산안 제안
│   └── new_budget_sheet.py              # (구버전, budget.py로 대체됨)
└── sample/
    └── 준서의 인생 계획.xlsx    # 원본 스프레드시트 (14시트)
```

---

## 핵심 연결고리: K열 (상세)

```
가계부 내역 K열 값  ←→  budget_config.yaml의 item.key  ←→  예산안 SUMIFS
    "선교 헌금"    →   key: "선교 헌금"                →   =SUMIFS(G:G, K:K, "선교 헌금", A:A, ">="&시작일, A:A, "<="&종료일)
```

- OpenClaw가 `rules.json` 기반으로 K열 자동 태깅
- 태깅률 = 예산 추적 정확도
- 현재 K열 키 36개 등록

---

## 기존 예산안 (25.7~26.6) 분석 결과

### 발견된 수식 버그
- `C13`: `가계부 내역22` 참조 → `가계부 내역`이어야 함
- `M20`: `SUMIF(J열)` → `SUMIF(K열)`이어야 함 (메모가 아닌 상세 기준)
- `B19`: 수식 누락

### 기존 구조 문제점
- 4블록 매트릭스 레이아웃 (A:E, F:J, K:O, P:T) → 확장/수정 어려움
- 저축/투자가 지출 예산에 혼재 → 소비 예산 왜곡
- 비정기 대형 지출 무방비
- 수입(62M) < 예산(77M) → 자산 갈아먹는 구조

### 개선 적용
- 세로형 리스트 레이아웃으로 변경
- 5층 목적 우선순위 구조
- Config-driven 방식으로 구조 유연성 확보
- 실적 기반 예산 금액 재설계 (58M/년, 수입 내)

---

## 개발 로드맵

| Phase | 내용 | 상태 |
|-------|------|------|
| P1 | OpenClaw 자동 분류 파이프라인 | ✅ 완료 (크론잡) |
| P2 | 기존 예산 구조 분석 | ✅ 완료 |
| P3 | 청지기 5층 철학 설계 | ✅ 완료 |
| P4 | Config-driven 예산 시트 생성 | ✅ 완료 |
| P5 | LLM 기반 예산 수정 (`예산` 키워드) | ✅ 완료 (CLAUDE.md) |
| P6 | 예산 기간 1~12월 전환 (SUMIF→SUMIFS) | ✅ 완료 (2026-02-18) |
| P7 | 모니터링 대시보드 강화 (소진율/진행률/페이스/조건부서식) | ✅ 완료 (2026-02-18) |
| **P8** | **월간 리포트 자동 생성** | **🔲 다음 작업** |
| P9 | 대시보드 알림 (초과/부족) | 🔲 미착수 |
| P10 | 연간 리뷰 및 차기 예산 자동 초안 | 🔲 미착수 |

---

## 완료된 작업 상세

### P6: 예산 기간 1~12월 전환 (✅ 2026-02-18)

- `budget_config.yaml`: period `"26.7~27.6"` → `"2026"`, 기간 `2026-01-01`~`2026-12-31`
- `budget.py`: SUMIF → SUMIFS (날짜 범위 조건 추가), 경과 월수 수식 DATEDIF로 개선
- 단일 시트 유지 결정: 가계부 내역은 그대로, 예산안만 연도별 deploy

### P7: 모니터링 대시보드 강화 (✅ 2026-02-18)

- 그리드 확장 9열 → 12열 (J: 소진율, K: 진행률 바, L: 월별 페이스)
- J열 `=F/E`, K열 `=REPT("█",...)`, L열 `=소진율/(경과월/12)`
- 소계/총계 행에도 소진율·진행률·페이스 수식 포함
- 조건부 서식: 0~70% 녹색, 70~90% 노랑, 90~100% 주황, 100%+ 빨강
- J열·L열 퍼센트(0%) 서식 적용
- XLSX preview에도 동일 열·조건부 서식 적용

---

## 다음 작업 상세 (P8)

---

## 참고 문서

- [철학 & 5층 구조](steward_finance_philosophy.md)
- [시스템 아키텍처 다이어그램](steward_finance_architecture.drawio) (3페이지)
- [스프레드시트 구조 분석](spreadsheet_structure.md)
- [실적 기반 예산안 제안](new_budget_proposal.md)
- [CLAUDE.md](../CLAUDE.md) — Claude Code 컨텍스트 (예산 키워드 포함)
