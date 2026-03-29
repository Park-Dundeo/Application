# 프로젝트 시스템 — 다음 개발 과제

## 1. 스프레드시트 탭 정리
현재 16탭(전체현황 + 15개 프로젝트)은 너무 많음.
- 옵션 A: 층별로 탭 합치기 (3층/고정비+생활비 → 1탭)
- 옵션 B: 2층 이하만 개별 탭, 3~5층은 층별 요약 탭으로 통합
- 우선 현행 유지 후, 실제 사용하면서 필요한 탭만 남기기

## 2. 예산 ↔ 프로젝트 정합성 점검
- `status` 월 총계 5,015,000 vs 수입 3,500,000 → 초과 이유 정리
- 비정기 항목(type: irregular)은 월 적립이므로 실제 지출과 다름
- budget_config.yaml monthly 합계와 projects.yaml monthly 합계 비교

## 3. schedule → Google Calendar 배포
- 각 YAML의 `schedule` 항목을 Google Calendar 이벤트로 생성
- `app/pipeline/schedule.py` 활용 (이미 존재)
- 연간/분기/월간 반복 이벤트 설계

## 4. 피드백 루프 첫 사용
- 스프레드시트 FEEDBACK 섹션에 실제 내용 입력
- `python3 -m app.pipeline.projects export` 실행
- YAML next_actions / gate 업데이트 확인

## 5. 2차 예산 재검토
- 헌장 작성 완료 후 각 프로젝트 budget boundary와 budget_config.yaml 일치 여부 확인
- 5층 총계 조정 필요 항목 파악

---

스프레드시트: https://docs.google.com/spreadsheets/d/1w4bfX44W2NgM4G7EOPfq9lUXKq-KUXJ4cUvA-VVbB-U/edit
환경변수: `export PROJECT_SPREADSHEET_ID=1w4bfX44W2NgM4G7EOPfq9lUXKq-KUXJ4cUvA-VVbB-U`
