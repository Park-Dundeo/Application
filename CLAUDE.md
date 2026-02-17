# OpenClaw — 청지기 재정 시스템

개인 가계부 자동화 + 예산 관리 시스템. 두 개의 독립된 영역으로 구성됩니다.

---

## 영역 1: 자동 카테고리화 (OpenClaw Pipeline)

뱅크샐러드 소비 내역을 자동으로 분류하여 Google Sheets에 기록하는 파이프라인.
크론잡으로 자동 실행되며, 사람 개입 없이 동작합니다.

### 파이프라인 흐름

```
뱅크샐러드 → Gmail(메일 내보내기) → OpenClaw 7단계 → Google Sheets(가계부 내역)
```

### 7단계

| 단계 | 모듈 | 역할 |
|------|------|------|
| 1. ingest | `app/pipeline/ingest.py` | Gmail에서 뱅샐 메일 수신 |
| 2. unzip | `app/pipeline/unzip.py` | 첨부 ZIP → CSV 추출 |
| 3. normalize | `app/pipeline/normalize.py` | CSV 정규화 |
| 4. dedup | `app/pipeline/dedup.py` | 중복 거래 제거 |
| 5. apply | `app/pipeline/apply_sheet.py` | Google Sheets 가계부 내역에 기록 |
| 6. categorize | `app/pipeline/categorize.py` | K열(상세) 자동 태깅 |
| 7. budget | `app/pipeline/budget.py` | 예산 실적 연동 (향후 확장) |

### 분류 규칙 체계

- `data/rules.json` — 900+ 분류 규칙 (contains/regex/amount_range)
- `data/categories.json` — 44개 유효 카테고리 목록
- `data/budget_keywords.json` — 키워드 기반 분류 보조
- `app/utils/rules.py` — Rule 엔진 (priority 순 매칭)
- `app/adapters/llm.py` — LLM 보조 분류 (`USE_LLM=1`일 때)

### 분류 흐름

```
거래 1건 입력
  → rules.json에서 priority 순으로 매칭 시도
    → contains: 패턴 문자열이 필드에 포함되면 매칭
    → regex: 정규식 매칭
    → amount_range: 금액 범위 매칭
  → 매칭 성공 → category 확정, source="rule"
  → 매칭 실패 + USE_LLM=1 → LLM 보조 분류, source="llm"
  → 결과를 M열(category), N열(source), O열(reviewed), P열(confidence)에 기록
```

### 규칙 수정 시 주의

- `rules.json`의 `category` 값은 반드시 `categories.json`에 있는 값이어야 함
- `category` 값은 동시에 `budget_config.yaml`의 `item.key`와 일치해야 예산 집계됨
- 규칙 추가 후 기존 거래 재분류가 필요하면 별도 스크립트 필요

### 관련 파일

```
app/main.py                    # 파이프라인 진입점 (run_pipeline)
app/config.py                  # AppConfig (환경변수 기반 설정)
app/adapters/google_auth.py    # Google OAuth (get_credentials(scopes))
app/adapters/sheets.py         # Sheets API 래퍼 (insert_rows, update_*)
app/adapters/llm.py            # classify_detail() — 키워드/LLM 분류
app/utils/rules.py             # load_rules(), apply_rules() — 규칙 엔진
app/utils/categories.py        # load_categories() — 유효 카테고리 로드
```

### 가계부 내역 시트 컬럼

```
A: 날짜  B: 시간  C: 타입  D: 대분류  E: 소분류  F: 내용  G: 금액
H: 화폐  I: 결제수단  J: 메모  K: 상세(예산키)  L: 자동카테고리
M: category  N: category_source  O: reviewed  P: confidence  Q: 재분류필요
```

---

## 영역 2: 예산안 관리 (청지기 재정)

### 철학

> "모든 소득은 하나님의 것이며, 나는 그것을 맡은 청지기다."

- **목표 주도 배분**: 줄여야 할 지출이 아니라, 배정해야 할 사명
- **연봉 내 설계, 부족 시 구함**: 기본은 수입 내, 하나님의 일에 더 필요하면 기도/추가소득
- **투명한 추적**: 자동 분류 + 월간 리뷰, 데이터가 다음 예산의 근거

### 5층 구조 (목적 우선순위)

| 층 | 이름 | 핵심 |
|----|------|------|
| 1층 | 하나님의 몫 (First Fruits) | 헌금/선교 — 먼저 드리고 나머지로 삶 |
| 2층 | 사명 프로젝트 (Mission) | 효도/관계/찬양/교회 — 목표가 예산을 이끈다 |
| 3층 | 청지기 운영 (Operations) | 고정비+생활비 — 절약이 아닌 적정 관리 |
| 4층 | 성장 씨앗 (Growth) | 저축/투자/자기계발 — 상여금 중심 운용 |
| 5층 | 신뢰 여백 (Trust Margin) | 비정기/예비 — 모자라면 구한다 |

### Config-Driven 워크플로우

**구조의 원본은 `data/budget_config.yaml`** 이며, Google Sheets는 자동 생성되는 뷰입니다.

```
① 계획 — budget_config.yaml 수정
② 배포 — python3 -m app.pipeline.budget deploy --force
③ 추적 — OpenClaw가 매일 자동 분류 → SUMIF 자동 집계
④ 점검 — 월간 리뷰
⑤ 조정 — 리뷰 결과로 config 수정 → ①로 복귀
```

### CLI 명령어

```bash
python3 -m app.pipeline.budget validate   # config 무결성 검증
python3 -m app.pipeline.budget status     # 층별 현황 요약 (오프라인)
python3 -m app.pipeline.budget preview    # XLSX 미리보기 생성
python3 -m app.pipeline.budget deploy     # Google Sheets에 시트 생성
python3 -m app.pipeline.budget deploy --force  # 기존 시트 삭제 후 재생성
```

### budget_config.yaml 구조

```yaml
period: "26.7~27.6"
period_start: "2026-07-01"
income:
  monthly_base: 3_500_000
  annual_bonus: 17_500_000
tiers:
  - id: first_fruits
    name: "하나님의 몫"
    priority: 1
    color: { bg: "#FCE4EC", header: "#C62828" }
    projects:
      - id: mission
        name: "선교"
        goal: "복음 전파에 정기적으로 참여"
        items:
          - key: "선교 헌금"          # ← K열 매칭키
            monthly: 120_000
            note: "매월 정기"
```

- `item.key`는 가계부 내역 K열 값과 정확히 일치해야 SUMIF 집계됨
- `item.type: irregular`는 비정기 지출 (월 적립 방식)
- `item.annual_from_bonus`는 상여금에서 배분되는 금액

### 예산 수정 키워드: `예산`

사용자가 **`예산`** 키워드로 시작하는 메시지를 보내면 **예산 편집 모드**로 동작합니다.

**예산 편집 모드 규칙:**

수정 가능한 파일 (화이트리스트):
- `data/budget_config.yaml` — 예산 구조 수정
- `data/categories.json` — 새 카테고리 등록 (key 추가 시에만)
- `data/rules.json` — 새 분류 규칙 추가 (key 추가 시에만)

수정 금지:
- `app/` 아래 모든 Python 스크립트
- `accountbook_analysis/` 아래 파일
- 기타 모든 코드 파일

실행 가능한 명령어:
- `python3 -m app.pipeline.budget validate`
- `python3 -m app.pipeline.budget status`
- `python3 -m app.pipeline.budget preview`
- `python3 -m app.pipeline.budget deploy`
- `python3 -m app.pipeline.budget deploy --force`

**사용 예시:**
```
사용자: "예산 — 효도 프로젝트에 어머니 여행 항목 추가, 월 15만원"
사용자: "예산 — 식비 90만원으로 올려줘"
사용자: "예산 — 새 프로젝트 '독서모임' 2층에 추가"
사용자: "예산 — 현황 보여줘"
사용자: "예산 — 수입 월 380만으로 변경"
```

**처리 절차:**
1. `data/budget_config.yaml` 읽기
2. 변경 전 현재 상태 확인 (`status` 또는 직접 요약)
3. yaml 수정
4. `validate` 실행 → 무결성 검증
5. 변경 전후 비교 요약:
   - 어떤 항목이 변경되었는지
   - 수입 대비 지출 비율 변화
   - 층별 소계 변화
6. 사용자 확인 대기
7. 확인 후 `deploy --force` 실행 (사용자가 요청할 때만)

**key 추가/변경 시 연동 점검:**
- 새 `item.key` 추가 시 → `categories.json`에 해당 값 존재하는지 확인, 없으면 추가
- 새 `item.key` 추가 시 → `rules.json`에 매칭 규칙이 있는지 안내 (규칙 없으면 K열 태깅 안 됨)
- `item.key` 변경 시 → 기존 거래 K열 값과 불일치 발생 가능성 경고
- 항목 삭제 시 → 기존 거래의 K열 값은 남아있어 미집계 됨을 안내
- validate에서 WARN/ERROR 발생 시 반드시 보고

### 핵심 연결고리: K열

```
rules.json의 category → 가계부 내역 K열 → budget_config.yaml의 item.key → SUMIF 집계
```

세 곳의 값이 일치해야 전체 시스템이 정상 동작합니다.
새 예산 항목을 추가할 때는 이 세 곳을 함께 확인해야 합니다.

### 관련 파일

```
data/budget_config.yaml              # ★ 예산 구조 원본
app/pipeline/budget.py               # Config 로딩 + 시트 생성 + CLI
accountbook_analysis/analysis.md     # 프로젝트 현황 문서
accountbook_analysis/steward_finance_philosophy.md    # 철학 상세
accountbook_analysis/steward_finance_architecture.drawio  # 아키텍처 다이어그램
```

---

## 공통 인프라

### Google Sheets 인증

```python
from app.adapters.google_auth import get_credentials
creds = get_credentials(scopes=[...])  # scopes 인자 필수
```

### 환경변수

```
SPREADSHEET_ID        — Google Sheets 문서 ID
GOOGLE_CLIENT_ID      — OAuth 클라이언트 ID
GOOGLE_CLIENT_SECRET  — OAuth 클라이언트 시크릿
GOOGLE_TOKEN_PATH     — 토큰 저장 경로 (기본: ./data/google_token.json)
GMAIL_QUERY           — Gmail 검색 쿼리
USE_LLM               — LLM 분류 사용 여부 (0|1)
```

### 코드 컨벤션

- Python 3.9+ (시스템 python3 사용)
- 의존성: `requirements.txt` (google-api, openpyxl, pyyaml)
- 한글 주석/문서 사용
- 파이프라인 각 단계는 독립 함수로, `app/main.py`에서 순차 호출
