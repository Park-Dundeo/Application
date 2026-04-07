# OpenClaw Faith Pack — 사용성 중심 구조 정리

---

## 1. 핵심 개념 모델 — 3축 연결

```
                    ┌─────────────┐
                    │   말씀      │
                    │ (Scripture) │
                    └──────┬──────┘
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
 ┌────────────────┐  ┌──────────┐  ┌────────────────┐
 │   양육·전도     │  │ Connection│  │      삶        │
 │ (Discipleship) │◄─┤  (연결점) ├─►│    (Life)      │
 └────────────────┘  └──────────┘  └────────────────┘
                           │
                    "말씀이 삶과 양육에서
                     어떻게 살아있는가?"
```

Connection 엔트리 하나가 scripture/life/discipleship 세 항목을 동시에 묶는 핵심 구조.

---

## 2. 데이터 흐름 전체 구조

```
┌─────────────────────────────────────────────────────────┐
│                    사용자 입력                           │
│  (신앙 대화 / 직접 JSONL 작성)                           │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   JSONL 파일 (데이터 원본)               │
│                                                         │
│  faith-beta/logs/                                       │
│  ├── scripture.jsonl      ← 말씀 관찰 + 통찰            │
│  ├── life.jsonl           ← 현실/영적 경험              │
│  ├── discipleship.jsonl   ← 양육 대상 관찰              │
│  └── connections.jsonl    ← 3축 연결 기록               │
│                                                         │
│  faith-beta/reviews/                                    │
│  └── weekly.jsonl         ← 주간 통찰 요약              │
└────────────┬───────────────────────┬────────────────────┘
             │                       │
             ▼                       ▼
┌────────────────────┐   ┌───────────────────────┐
│   RAG 엔진         │   │   Ontology 엔진        │
│  (의미 검색)        │   │   (관계 구조 쿼리)      │
│                    │   │                       │
│  JSONL → 텍스트    │   │  JSONL → RDF 그래프   │
│  → 임베딩 벡터     │   │  (triples)            │
│  → ChromaDB 저장   │   │  메모리 내 즉시 빌드   │
│                    │   │                       │
│  ~/.openclaw/      │   │  rdflib Graph()       │
│  faith-rag-db/     │   │  (파일 저장 없음)      │
└────────────┬───────┘   └───────────┬───────────┘
             │                       │
             └──────────┬────────────┘
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   CLI 출력 / 에이전트 컨텍스트            │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 두 엔진의 역할 차이

| 질문 유형 | 엔진 선택 | CLI 명령 |
|-----------|-----------|----------|
| "순종에 대해 기록한 내용 찾아줘" | RAG (의미 유사도) | `python -m rag search "순종"` |
| "오늘 말씀에 연결된 삶 기록 뭐야?" | Ontology (관계 구조) | `python -m rag onto brief` |
| "sc-2026-01 ID에 연결된 항목 모두" | Ontology (그래프 탐색) | `python -m rag onto context sc-2026-01` |
| "사순절 시즌 전체 패턴 봐줘" | Ontology (시즌 필터) | `python -m rag onto season Lent` |
| "최근 7일 중요한 연결 뭐였어?" | Ontology (날짜+정렬) | `python -m rag onto recent` |

---

## 4. JSONL 엔트리 구조 (공통 + 카테고리별)

**모든 엔트리 공통 필드**

```
┌─────────────────────────────────────────┐
│  id         "sc-20260301-01"  (필수)    │
│  date       "2026-03-01"      (필수)    │
│  category   scripture|life|   (필수)    │
│             discipleship|               │
│             connection|weekly-review    │
│  tags       ["순종", "전도"]            │
│  priority   low|medium|high             │
│  relatedIds ["lf-20260301-01"]  ←───┐  │
│  timeline   { week, season, phase } │  │
└──────────────────────────────────┬──│──┘
                                   │  │
        양방향 자동 연결 ───────────┘  │
                                      │
Connection 전용 추가 필드             │
┌─────────────────────────────────┐  │
│  scriptureId    "sc-..."        │  │
│  lifeId         "lf-..."   ─────┘  │
│  discipleshipId "ds-..."           │
│  connectionStatement  "말씀의 X가  │
│                        삶의 Y에서  │
│                        Z로 나타남" │
│  insightLevel   1~5 (중요도)       │
└─────────────────────────────────┘
```

---

## 5. 일상 사용 흐름

**하루 기록 흐름**

```
 아침 큐티              신앙 대화 중          저녁 / 주간
     │                      │                    │
     ▼                      ▼                    ▼
scripture.jsonl        life.jsonl           weekly.jsonl
에 1줄 추가            또는                  에 통찰 요약
                   discipleship.jsonl       1개 이상 정리
                       에 1줄 추가
                           │
                           ▼
                   connections.jsonl
                   에 3축 연결 1줄
                   (가능하면)
```

**검색/탐색 흐름**

```
 신앙 대화 시작
     │
     ▼
 onto brief          오늘 말씀 + 연결된 삶/양육 컨텍스트 즉시 로드
     │
     ├─► 더 깊이 파고 싶으면 ──► onto context <id>
     │
     ├─► 주제어로 찾으려면  ──► search "키워드"
     │
     └─► 시즌 패턴 보려면  ──► onto season <시즌명>
```

---

## 6. 설정 구조

```
~/.openclaw/
├── .env                          ← API 키 및 경로 설정
│     OPENAI_API_KEY=...
│     FAITH_RAG_DB_PATH=...       (기본: ~/.openclaw/faith-rag-db)
│     FAITH_RAG_EMBEDDING_BACKEND=openai|local
│
├── faith-rag-db/                 ← ChromaDB 벡터 저장소 (자동 생성)
│
└── workspace/
    ├── git/openclaw-faith-pack/  ← 소스 코드 (git 관리)
    │     rag/
    │     ├── config.py
    │     ├── ingest.py
    │     ├── search.py
    │     ├── ontology.py
    │     └── __main__.py
    │
    └── faith-beta/               ← 실제 기록 데이터
          logs/
          reviews/
          schema/
```

---

## 핵심 요약

| 레이어 | 역할 | 파일 |
|--------|------|------|
| 데이터 | JSONL로 날것의 기록 저장 | `faith-beta/logs/*.jsonl` |
| RAG | "이 주제와 비슷한 기록" 의미 검색 | `ingest.py` + ChromaDB |
| Ontology | "이 항목과 연결된 항목" 관계 탐색 | `ontology.py` + rdflib |
| CLI | 두 엔진을 하나의 인터페이스로 통합 | `__main__.py` |
| 가이드라인 | 에이전트에게 대화 방식 지시 | `FAITH_GUIDELINES.md` |
