# openclaw.md - OpenClaw 자동화 아키텍처

이 파일은 OpenClaw 기반 가계부 자동화의 표준 규칙, 워크플로, 결정사항을 기록합니다.

## 목표
- 뱅크샐러드 export → 구글드라이브 저장 → 자동 압축해제 → 정규화 → 중복제거 → 가계부 내역 시트 반영 → 카테고리 자동화 → 예산 집계
- 가계부 내역 시트는 2행이 최신 내역이어야 함
- 카테고리(상세)는 K열에 자동/수동 혼합

## 전체 아키텍처
- 수집(Ingest): Gmail 첨부 최신 export 감지 후 Drive에 저장
- 압축해제(Unzip): 최신 zip을 날짜 폴더로 해제
- 정규화(Normalize): 표준 컬럼으로 변환 후 staging 저장
- 중복제거(Dedup): 기존 시트와 비교하여 신규 내역만 추출
- 반영(Apply): 가계부 내역 2행부터 삽입
- 분류(Categorize): LLM/룰 기반으로 K열 상세 채움
- 예산(Budget): 정규화 예산 시트를 기준으로 집계 갱신

## 현재 경계(준비 단계 완료)
- 구현 완료 범위: **압축 해제 + 가계부 내역 업데이트**
- 이후 단계: **카테고리화 MVP**만 진행
- 대시보드/레이아웃/코칭/예산 조합 로직은 보류
- 원장 테이블만 SOT(Source of Truth)로 유지

## 다음 단계: 카테고리화 MVP 요구사항(요약)
1. 원장(LEDGER) 행에 category 관련 필드 채우기
   - 입력: date, amount(지출 -, 수입 +), merchant, memo(선택), account(선택), raw_text(선택)
   - 출력: category, category_source(rule/manual/llm), reviewed(Y/N), confidence(선택)
2. 분류는 룰 기반 우선
   - RULES: priority, match_type(contains/regex/amount_range), pattern, category_id, enabled
   - 높은 우선순위 룰부터 적용, 최초 매칭 사용
   - 미매칭은 category 비워두고 reviewed=N
3. LLM은 미분류에 한해 보조(선택)
   - 행 단위 구조화 데이터만 입력(JSON)
   - 출력은 추천 category + confidence 수준
4. 수동 분류 → RULES에 반영하는 워크플로 지원

## 표준 컬럼(가계부 내역)
- 날짜
- 시간
- 타입
- 대분류
- 소분류
- 내용
- 금액
- 화폐
- 결제수단
- 메모
- 상세

## 정규화 예산 시트(권장)
- 시트명: 예산_원본
- 컬럼 예시: 프로젝트, 카테고리, 월, 예산, 비고
- 기존 25.7~26.6 예산안 시트는 유지하되, 집계는 예산_원본을 기준으로 변경

## 실행 구조
- 앱 엔트리: scripts/run_pipeline.py
- 구성 파일: app/config.py (환경변수로 세부 설정)
- 주요 파이프라인: app/pipeline/*
- 자동 카테고리 키워드: `data/budget_keywords.json` (예산안 HTML에서 추출)

## OpenClaw 실행 방식(권장)
- 크론잡으로 정기 실행
- 예시: 30분마다 실행
  - `*/30 * * * * cd /Users/junseopark/Documents/Git/Application && /usr/bin/python3 scripts/run_pipeline.py`

## TODO (우선순위)

### P0 — "일단 돌아가게 만들기" (필수)
1. **Gmail 첨부 다운로드 구현** (`app/adapters/gmail.py`)
   - 인증 방식 결정(OAuth)
   - `GMAIL_QUERY`로 최신 메일 + 첨부 1개 선정 로직
   - 첨부 파일명/인코딩/확장자 처리
2. **Drive 업로드 구현** (`app/adapters/drive.py`)
   - 폴더 탐색/생성/업로드
   - 동일 파일 중복 업로드 정책(스킵/덮어쓰기/버전) 결정
3. **Sheets 삽입/업데이트 구현** (`app/adapters/sheets.py`)
   - `insert_rows()` : `LEDGER_INSERT_ROW=2`에 신규 행 삽입
   - `update_detail_column()` : K열(상세) 업데이트(업데이트 대상 행 식별 키 필요)
4. **Normalize 실제 구현** (`app/pipeline/normalize.py`)
   - export(zip 내부)의 실제 포맷(csv/xlsx) 판별
   - 원본 컬럼 → 표준 컬럼 매핑
   - 날짜/시간/금액(부호)/결제수단 정규화

### P1 — "정확도/재실행 안전" (권장)
5. **중복제거를 ‘시트 기준’으로 구현** (`app/pipeline/dedup.py`)
   - 현재는 파일 내부 중복만 제거(seen set)
   - 시트의 기존 거래 일부를 읽어 `row_key`와 비교해 신규만 통과
6. **row_key 기준 검증/개선** (`app/utils/hash.py`)
   - 현재 KEY_FIELDS: 날짜/시간/금액/내용/결제수단
   - 원본 행 ID가 있다면 최우선 키로 사용
7. **관측/로그/에러처리**
   - 단계별 실패 로그
   - 실패 시 중단/스킵/재시도 정책

### P2 — "자동 분류/예산" (추가 기능)
8. **LLM 분류 구현** (`app/adapters/llm.py`)
   - row → 카테고리/상세 제안
   - 프롬프트 템플릿 + 실패 fallback
9. **예산 집계 갱신 구현** (`app/pipeline/budget.py`)
   - 예산_원본 기반 집계 갱신(피벗/수식/요약 시트 정의)

### P3 — 운영
10. **실행 엔트리 정리**
   - 문서에는 `scripts/run_pipeline.py`가 엔트리라고 쓰였는데, 현재 repo에는 없음
   - `scripts/`에 실제 실행 파일 추가(또는 `python -m app.main`으로 통일)
11. **의존성/환경 정리**
   - `requirements.txt` 재생성 및 버전 고정
   - `.env` 템플릿 추가
12. **스케줄링**
   - cron/launchd로 정기 실행(예: 30분마다 / 하루 1회)

## 환경변수(필수/권장)
- APP_DATA_DIR: 데이터 디렉토리(기본 `./data`)
- SPREADSHEET_ID: 대상 스프레드시트 ID
- GMAIL_QUERY: 첨부 검색 쿼리
- 예: `subject:"박준서님의 뱅크샐러드 엑셀 내보내기 데이터" has:attachment`
- DRIVE_FOLDER: 저장할 드라이브 경로
  - 예: `재정/뱅크샐러드`
- SHEET_LEDGER: 가계부 내역 시트명
- SHEET_BUDGET_RAW: 예산_원본 시트명
- LEDGER_HEADER_ROW: 헤더 행(기본 1)
- LEDGER_INSERT_ROW: 신규 삽입 행(기본 2)
- LEDGER_DETAIL_COL: 상세 컬럼(기본 K)
- LEDGER_AUTO_COL: 자동 카테고리 컬럼(기본 L)
- BUDGET_KEYWORDS_PATH: 자동 카테고리 키워드 파일(기본 `./data/budget_keywords.json`)
