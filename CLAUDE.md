# OpenClaw — 청지기 재정 시스템

개인 가계부 자동화 + 예산 관리 시스템. 세 개의 독립된 영역으로 구성됩니다.

---

## 영역 1: 자동 카테고리화 (OpenClaw Pipeline)

뱅크샐러드 소비 내역을 자동으로 분류하여 Google Sheets에 기록하는 파이프라인 (크론잡).

```
뱅크샐러드 → Gmail → OpenClaw 7단계 → Google Sheets(가계부 내역)
단계: ingest → unzip → normalize → dedup → apply_sheet → categorize → budget
```

### 분류 규칙 체계

- `data/rules.json` — 분류 규칙 (contains/regex/amount_range), priority 순 매칭
- `data/categories.json` — 유효 카테고리 목록
- `app/utils/rules.py` — Rule 엔진 (`load_rules()`, `apply_rules()`)
- `app/adapters/llm.py` — LLM 보조 분류 (`USE_LLM=1`일 때)

### 규칙 수정 시 주의

- `rules.json`의 `category` 값은 `categories.json`에 있어야 하고, `budget_config.yaml`의 `item.key`와 일치해야 예산 집계됨
- 규칙 추가 후 기존 거래 재분류가 필요하면 별도 스크립트 필요

### 주요 파일

```
app/main.py                 # 파이프라인 진입점
app/config.py               # AppConfig (환경변수 기반)
app/adapters/google_auth.py # Google OAuth
app/adapters/sheets.py      # Sheets API 래퍼
app/utils/rules.py          # 규칙 엔진
```

---

## 영역 2: 예산안 관리 (청지기 재정)

> "모든 소득은 하나님의 것이며, 나는 그것을 맡은 청지기다."

**구조의 원본은 `data/budget_config.yaml`**, Google Sheets는 자동 생성되는 뷰.

### 5층 구조

| 층 | 이름 | 핵심 |
|----|------|------|
| 1층 | 하나님의 몫 | 헌금/선교 — 먼저 드리고 나머지로 삶 |
| 2층 | 사명 프로젝트 | 효도/관계/찬양/교회 — 목표가 예산을 이끈다 |
| 3층 | 청지기 운영 | 고정비+생활비 — 절약이 아닌 적정 관리 |
| 4층 | 성장 씨앗 | 저축/투자/자기계발 — 상여금 중심 운용 |
| 5층 | 신뢰 여백 | 비정기/예비 — 모자라면 구한다 |

### CLI 명령어

```bash
python3 -m app.pipeline.budget validate        # config 무결성 검증
python3 -m app.pipeline.budget status          # 층별 현황 요약
python3 -m app.pipeline.budget preview         # XLSX 미리보기
python3 -m app.pipeline.budget deploy          # Google Sheets 생성
python3 -m app.pipeline.budget deploy --force  # 기존 시트 삭제 후 재생성
```

### 예산 수정 키워드: `예산`

`예산`으로 시작하는 메시지 → **예산 편집 모드**로 동작.

**수정 가능 (화이트리스트):**
- `data/budget_config.yaml`
- `data/categories.json` (key 추가 시에만)
- `data/rules.json` (key 추가 시에만)

**수정 금지:** `app/` 아래 Python 스크립트, `accountbook_analysis/`, 기타 코드 파일

**처리 절차:**
1. `budget_config.yaml` 읽기 → 현재 상태 파악
2. yaml 수정
3. `validate` 실행
4. 변경 전후 비교 요약 (항목, 수입 대비 비율, 층별 소계)
5. 사용자 확인 대기
6. 확인 후 `deploy --force` (요청 시에만)

**key 추가/변경 시 연동 점검:**
- 새 `item.key` → `categories.json` 존재 확인, 없으면 추가
- 새 `item.key` → `rules.json` 매칭 규칙 안내 (없으면 K열 태깅 안 됨)
- `item.key` 변경 → 기존 K열 불일치 경고
- 항목 삭제 → 기존 거래 K열 미집계 안내
- validate WARN/ERROR → 반드시 보고

### 핵심 연결고리: K열

```
rules.json의 category → 가계부 내역 K열 → budget_config.yaml의 item.key → SUMIF 집계
```

세 곳의 값이 일치해야 전체 시스템이 정상 동작합니다.

### 주요 파일

```
data/budget_config.yaml   # ★ 예산 구조 원본
app/pipeline/budget.py    # Config 로딩 + 시트 생성 + CLI
```

---

## 영역 3: 프로젝트 헌장 관리 (청지기 프로젝트)

```
YAML 편집 → deploy → Sheets 모니터링 뷰
                         ↓ FEEDBACK 섹션 작성
                       export → YAML 업데이트
```

### YAML 파일

- `data/projects/{tier_id}.yaml` — tier_id는 budget_config.yaml의 `tier.id`와 일치
- 각 프로젝트: 헌장 + Gate 3단계(A_seed/B_grow/C_handoff) + schedule + next_actions

### CLI 명령어

```bash
python3 -m app.pipeline.projects status           # 로컬 텍스트 뷰
python3 -m app.pipeline.projects deploy [--force] # 스프레드시트 생성/갱신
python3 -m app.pipeline.projects export           # FEEDBACK → YAML 업데이트
```

### FEEDBACK → export 처리 규칙

| 행 | 입력 내용 | export 처리 |
|----|-----------|------------|
| 날짜 | YYYY-MM-DD | review_history.date |
| 잘 된 것 | 자유 텍스트 | review_history.good |
| 안 된 것 | 자유 텍스트 | review_history.bad |
| 배운 것 | 자유 텍스트 | review_history.learned |
| Gate 변경? | `없음` / `A→B` / `B→C` | gate 상태 업데이트 |
| 다음 액션 | 개행 구분 목록 | next_actions 전체 교체 |

### 주요 파일 / ENV

```
data/projects/           # 층별 헌장 YAML
app/pipeline/projects.py # deploy / status / export
app/pipeline/schedule.py # schedule → Google Calendar

PROJECT_SPREADSHEET_ID   # 프로젝트 스프레드시트 ID
```

---

## 공통 인프라

### Google 인증

```python
from app.adapters.google_auth import get_credentials
creds = get_credentials(scopes=[...])  # scopes 인자 필수
```

토큰 재발급 (스코프 변경/만료 시):
```bash
rm data/google_token.json
python3 -c "
from app.adapters.google_auth import get_credentials
get_credentials([
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.readonly',
])"
```

### 환경변수

```
SPREADSHEET_ID         — 가계부/예산 Sheets ID
PROJECT_SPREADSHEET_ID — 프로젝트 전용 Sheets ID
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
GOOGLE_TOKEN_PATH      — 기본: ./data/google_token.json
GMAIL_QUERY            — Gmail 검색 쿼리
USE_LLM                — LLM 분류 사용 여부 (0|1)
```

### gws CLI

`gws` 명령어로 Drive/Sheets/Gmail/Calendar/Tasks를 Bash에서 직접 조작 가능.
구조: `gws <service> <resource> <method> --params '<JSON>' --json '<JSON>'`
스키마 확인: `gws schema <service.resource.method>`

### 코드 컨벤션

- Python 3.9+ (시스템 python3)
- 의존성: `requirements.txt` (google-api, openpyxl, pyyaml)
- 한글 주석/문서
- 파이프라인 각 단계는 독립 함수, `app/main.py`에서 순차 호출
