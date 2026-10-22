# 투자 의사결정 노트 — 프론트엔드

Vue 3 + Vite + TypeScript + Vue Router. UI 라이브러리 없이 일반 CSS를 씁니다.

디자인 콘셉트는 "장부 용지에 쓴 애널리스트의 주석 달린 리포트"입니다. 리포트 본문은 Noto Serif KR, 화면 요소는 IBM Plex Sans KR, 숫자는 IBM Plex Mono이고 `index.html`에서 Google Fonts로 불러옵니다. 오프라인이면 시스템 글꼴로 대체됩니다. 색과 글꼴 토큰은 `src/styles/global.css` 맨 위에 모여 있고, 운영체제 설정에 따라 밝은 테마와 어두운 테마가 바뀝니다.

## 실행

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # 타입 검사(vue-tsc) + 프로덕션 빌드
```

## 목업 모드

기본값은 **목업 모드**(`.env.development`의 `VITE_USE_MOCK=true`)입니다. 백엔드 없이 모든 화면이 동작합니다.

- 데이터는 브라우저 localStorage에 저장되어 새로고침해도 유지됩니다. 상단의 "데이터 초기화"로 처음 상태로 되돌릴 수 있습니다.
- **NVDA**: 이전 결정이 이미 있는 종목입니다. 분석하면 "과거 결정 대비" 섹션이 나오고 철회 조건이 미리 채워집니다.
- **그 외 티커**: 처음 분석하는 종목입니다. 결정을 저장한 뒤 같은 종목을 다시 분석하면 과거 결정 대비 섹션이 나타납니다.

### 실제 백엔드에 연결

`frontend/.env.development.local` 파일을 만들고 아래 한 줄을 넣은 뒤 개발 서버를 다시 시작합니다. (`cp .env.development.local.example .env.development.local`)

```
VITE_USE_MOCK=false
```

프론트는 `/api/*`로 요청하고, Vite 프록시가 `/api`를 떼고 `http://localhost:8000`으로 넘깁니다.
예: `/api/reports/123` → `http://localhost:8000/reports/123`. 그래서 FastAPI에 CORS 설정이 필요 없습니다.

## 백엔드가 맞춰야 할 API

타입은 `src/types/index.ts`에 있고, `backend/agent/schemas.py`와 같은 구조입니다.
날짜(`date`)는 `"YYYY-MM-DD"`, 일시(`datetime`)는 ISO 8601 문자열입니다.

| 요청 | 본문 | 응답 |
|---|---|---|
| `POST /analyze` | `{ticker, market, as_of_date}` | `Report` + `id` (+ `created_at`) |
| `POST /analyze/stream` | `{ticker, market, as_of_date}` | SSE: `node`·`step` 진행 이벤트 → 마지막에 `report`(위와 같은 형태) 또는 `error`. 분석 화면은 이것을 쓴다 |
| `GET /reports/{id}` | | `Report` + `id` |
| `GET /reports?ticker=&market=` | | `[{id, ticker, market, as_of_date, created_at}]` 최신순. 파라미터 없으면 전체 |
| `GET /reports/{id}/highlights` | | `HighlightGroup[]` (각 그룹에 `id`, `created_at`) |
| `POST /reports/{id}/highlights` | `{tag, comment, spans}` | 저장된 `HighlightGroup` (`id` 포함) |
| `POST /decisions` | `{report_id, ticker, market, action, weight, confidence, my_thesis, my_thesis_breaker, evidence_group_ids}` | 저장된 결정 (`id`, `decided_at`, `report_id`, `evidence_group_ids` 포함) |
| `GET /decisions/{ticker}?market=` | | 결정 목록, **최신순** (각 항목에 `id`, `report_id`, `evidence_group_ids`) |

- `weight`는 0~1 비율(예: 12.5% → `0.125`)이거나 `null`입니다.
- `decided_at`은 서버가 채웁니다.
- 오류 응답은 FastAPI 기본 형식(`{"detail": ...}`)이면 화면에 그대로 표시됩니다.

## 하이라이트 동작 전제

- 리포트 섹션은 **원문 그대로**(`white-space: pre-wrap`) 렌더링하고, offset은 각 섹션 원문 기준 글자 위치입니다.
- 그래서 **`write_report`(와 `compare_with_past`의 summary)는 마크다운 없이 일반 텍스트로 출력**해야 합니다.
  마크다운을 HTML로 바꿔 보여주면 화면 글자와 원문 offset이 어긋납니다. 줄바꿈(`\n`)은 괜찮습니다.
- 여러 섹션에 걸친 드래그는 섹션별 조각(span)으로 나뉘어 하나의 그룹으로 저장됩니다. 섹션 밖(제목, 안내 문구)에서 시작하거나 끝난 선택은 섹션 경계로 잘립니다. 앞뒤 공백은 제외됩니다.
- `past_decision_review`는 `summary` 텍스트만 하이라이트할 수 있습니다(필드 이름 `past_decision_review`). 점검표는 하이라이트 대상이 아닙니다.

## 구조

```
src/
├── api/client.ts            목업/실제 API 전환
├── types/index.ts           백엔드 스키마와 같은 타입 + 화면 라벨
├── mocks/                   목업 데이터와 목업 서버
├── composables/useHighlight.ts   선택 → 섹션별 span 계산, 하이라이트 렌더링 조각 계산
├── components/
│   ├── ReportSection.vue    섹션 1개 (data-field 블록)
│   ├── HighlightPopover.vue 태그·메모 입력
│   ├── HighlightList.vue    하이라이트 목록
│   ├── QuantCards.vue       퀀트 지표 카드
│   └── DecisionForm.vue     결정 입력
├── views/
│   ├── AnalyzeView.vue      /                      종목 입력 → 분석
│   ├── ReportView.vue       /reports/:id           리포트 + 하이라이트 + 결정
│   └── HistoryView.vue      /history/:market/:ticker  결정 타임라인
└── router/index.ts
```
