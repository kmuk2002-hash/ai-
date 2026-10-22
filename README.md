# 투자 의사결정 노트 (Quant + Fundamental Investment Note)

펀더멘털(10-K RAG + 웹 검색)과 퀀트(Alpha Vantage) 관점으로 리포트를 만들고, 사용자가 형광펜·메모·결정을 남기면 다음 분석 때 과거 판단을 점검해 주는 LangGraph 에이전트 + FastAPI + Vue 앱입니다.
설계와 구현 내용은 `docs/투자의사결정_시스템_설계.md`에 있습니다.

## 기획 의도

비슷한 실적 발표에도 주가는 전혀 다르게 움직입니다. 퀀트 지표만 보면 시장 심리에 휩쓸리고, 펀더멘털만 보면 거품을 놓칩니다.
이 서비스는 두 관점을 한 리포트에 담되 **결정은 사람이 내리게** 하고, 그 결정과 근거를 기록해 두었다가
같은 종목을 다시 분석할 때 **그때 정한 철회 조건이 지금 충족됐는지** 점검해 줍니다.
목표는 과거 투자 경험에서 **나만의 투자 기준**을 만들어 가는 것입니다.

## 구현한 기능

| 기능 | 내용 |
|---|---|
| 기업 분석 리포트 | 펀더멘털 서브그래프(10-K·웹 검색 → 관련성 검사 → 부족하면 재검색 → 요약) + 퀀트 노드(Alpha Vantage MCP) → 고정 형식 리포트(투자 논리·리스크·컨센서스 대비 차이·철회 조건). 출처는 LLM이 아니라 코드가 문서에서 만든다 |
| 의사결정 기록 | 리포트 문장에 형광펜(근거·우려·확인 필요·반대)과 메모 → 매수/보류/매도, 비중, 확신도, 내 투자 논리, 철회 조건 저장. 리포트는 저장 후 수정 불가(DB 트리거) |
| 과거 결정 점검 | 같은 종목을 다시 분석하면 지난 결정의 철회 조건·확인 필요 항목을 새 자료로 점검(분석과 비교를 분리해 과거 판단이 새 분석을 오염시키지 않게) |
| 결정 이후 소식 | 점검 결과를 원래 리포트·기록 보관함·상단 알림에 표시. 철회 조건이 충족되면 경고 |
| 기록 보관함 | 리포트와 결정을 날짜별·종목별로 모아 보기, 새 소식만 보기 |
| 진행 상황 스트리밍 | `/analyze/stream`(SSE)로 노드·서브그래프 단계가 끝날 때마다 화면에 표시 |
| 실습 인사이트 적용 | W01 lifespan 1회 컴파일 · W02 MCP + 날짜 캐시 · W03 SSE · W04 고정 워크플로우 vs ReAct 비교 · W06 권위 게이트(판정·출처는 코드가) · W07 재검색 루프 · W08 검증 노드 · W10 모델 라우팅 · W11 병렬 노드 · W12 영속 저장 · W14 LangSmith 추적·평가 |

## 실험 결과 요약 (LangSmith)

| 실험 | 결과 |
|---|---|
| 웹 검색 fixed vs agent (AAPL 각 3회) | agent는 지연 +24%(22.5 → 27.9초), 토큰 +86%, 비용 2.3배, 실행 간 출처 일치도 0.89 → 0.19. 기본값은 fixed |
| 관련성 검사 모델 라우팅 (평가셋 27개, 판정 v2 고정) | gpt-4o-mini → gpt-4.1-nano: 판단 지연 −22.7%, 호출당 비용 −33.2%(추정), 정확도 0.593 → 0.667 |
| 판정 방식 (같은 nano) | v1(LLM이 yes/no) → v2(LLM은 근거 문서만, 판정은 코드): 거짓 yes 91.7% → 50.0% |
| 로컬 모델 (Ollama) | qwen3.5:2b는 지연 −64%이나 거짓 no 53%, qwen2.5:0.5b는 항상 no·출력 상한 없으면 생성이 끝나지 않음 → 작은 모델은 평가셋으로 검증한 크기까지만 라우팅 |

## 한계와 다음 단계

1. **판정의 신뢰성**: 관련성 검사가 아직 부족한 자료의 50%를 통과시킨다. 평가셋이 3종목 27개이고 정답이 검색 주제 기반 라벨이라 잡음이 있다.
   → 사람이 검수한 평가셋으로 확대하고, 프롬프트·모델을 바꿀 때마다 LangSmith Experiment로 회귀 검증.
2. **근거 데이터의 범위**: 10-K RAG는 구현했지만 SEC 요청 제한으로 적재·측정을 못 해 펀더멘털이 웹 기사에 의존한다. Alpha Vantage 무료 플랜(하루 25회, 회사 개요 지표 없음), 국내 시장 미지원.
   → 10-K 적재, 국내 공시(DART) 어댑터, 웹 검색 병렬화.
3. **의사결정 보조 루프가 수동**: 결정 이후 소식은 사용자가 다시 분석해야만 생기고, 쌓인 결정이 아직 개인 투자 기준으로 정리되지 않는다.
   → 결정 종목 주기적 자동 재분석과 알림, 결정 이력에서 투자 기준 도출, 사람이 승인하는 자동매매.

그 밖에: 추적 데이터(수집 문서·리포트 본문)가 LangSmith에 저장되므로 실제 개인 메모를 다루려면 비공개 설정이나 자체 호스팅이 필요하다. 일시적 API 오류의 백오프 재시도는 없다(오류 구분만 함). 알림 읽음 표시는 브라우저에만 저장된다.

```
주식_완성본/
├── backend/   agent(LangGraph) · app(FastAPI) · storage(PostgreSQL) · ingestion(10-K 적재) · scripts
├── frontend/  Vue 3 + Vite
├── db/        schema.sql(리포트·하이라이트·결정) · rag.sql(pgvector) · queries.sql
└── docs/
```

## 실행 순서 (Mac)

필요한 것: Python 3.11, Node 18+, Docker Desktop

### 1. 환경변수

```bash
cp .env.example .env      # 이미 .env가 있으면 빠진 변수만 추가
```

`.env`에 최소한 `OPENAI_API_KEY`, `ALPHAVANTAGE_API_KEY`, `TAVILY_API_KEY`를 넣습니다.
10-K를 적재하려면 `SEC_EDGAR_USER_AGENT="이름 이메일"`도 필요합니다.

### 2. DB (PostgreSQL + pgvector)

```bash
docker compose up -d
```

처음 만들 때 `db/schema.sql`, `db/rag.sql`이 자동 적용됩니다.
예전에 만든 DB 볼륨이 있으면 `rag.sql`은 적재 스크립트가 알아서 적용하니 그대로 두면 됩니다.

### 3. 백엔드 패키지

```bash
cd backend
pip install -r requirements.txt
```

### 4. 10-K 적재 (RAG, 시연 종목만)

```bash
cd backend
python -m ingestion.load AAPL NVDA
```

종목마다 최신 10-K의 Item 1·1A·7을 잘라 임베딩해 저장합니다(OpenAI 임베딩 비용 소량). 적재하지 않아도 분석은 웹 검색만으로 동작합니다.

### 5. API 서버

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

http://localhost:8000/docs 에서 직접 호출해 볼 수 있습니다.

### 6. 프론트엔드

```bash
cd frontend
npm install
cp .env.development.local.example .env.development.local   # 실제 API 사용 (VITE_USE_MOCK=false)
npm run dev                                               # http://localhost:5173
```

`.env.development.local`을 만들지 않으면 목업 모드로 백엔드 없이 화면만 볼 수 있습니다.

### 터미널에서 분석만 해 보기

```bash
cd backend
python -m scripts.run_analysis AAPL
python -m scripts.run_analysis AAPL --web agent --verify
```

## 주요 설정

| 변수 | 기본값 | 설명 |
|---|---|---|
| `WEB_SEARCH_MODE` | `fixed` | `fixed`: 정해진 검색어 4개 / `agent`: ReAct 에이전트가 검색어를 정함 |
| `VERIFY_ENABLED` | `false` | 리포트 숫자를 퀀트 데이터와 대조, 문제가 있으면 1회 재작성 |
| `OPENAI_MODEL` | `gpt-4o-mini` | heavy: 요약·리포트 작성·과거 비교 |
| `OPENAI_MODEL_LIGHT` | `gpt-4.1-nano` | light: 관련성 검사·검색어 재작성·숫자 검증 |
| `LLM_ROUTING` | `tiered` | `single`이면 모든 노드가 heavy (비교 실험용) |
| `RELEVANCE_JUDGE` | `v2` | `v1`: LLM이 yes/no / `v2`: LLM은 주제별 근거 문서만, 판정은 코드 |
| `LLM_PROVIDER` | `openai` | `ollama`면 로컬 모델(`OLLAMA_MODEL`, `OLLAMA_MODEL_LIGHT`)로 실행 |
| `DATABASE_URL` | 로컬 docker | 비우면 DB 없이 동작(과거 결정 없음, 10-K 검색 없음, API 저장 불가) |

## 무료 API 제약

- **Alpha Vantage 무료 플랜**: 하루 25회, 초당 1회. 종목당 3회 호출(EARNINGS, 일봉, 주봉)이라 캐시 없이 하루 8종목.
  `COMPANY_OVERVIEW`가 유료라 PER은 최근 4분기 EPS로 직접 계산하고, PBR·ROE·목표주가 등은 "데이터 없음"으로 표시됩니다.
  같은 날 같은 종목은 `backend/.cache/`에서 읽습니다. 시연 전에 종목별로 한 번씩 분석해 두면 발표 중 한도에 걸리지 않습니다.
- **국내(KR) 시장**은 KIS API 키가 없어 지원하지 않습니다(API가 400으로 응답).

## LangSmith로 추적·비교하기

`.env`에 다음을 넣으면 모든 분석이 LangSmith에 기록됩니다. 키가 없으면 추적만 꺼지고 나머지는 그대로 동작합니다.

```
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=invest-report-agent
```

**무엇이 기록되나**
- 분석 1회 = 루트 실행 `analyze:<티커>`. API·CLI·노트북 어디서 실행해도 같은 이름입니다(`agent/runner.py`).
- 태그: `market:US`, `web:fixed|agent`, `verify:on|off`, `has_past|no_past`, `av_cache:warm|cold`, `source:api|cli|notebook`
- 메타데이터: `ticker`, `market`, `as_of_date`, `model`, `web_search_mode` 등 → LangSmith 화면에서 필터
- 그 아래: LangGraph 노드, LLM 호출(토큰·비용 자동), 그리고 LangChain이 아닌 작업도 span으로
  `alphavantage.fetch_snapshot`(캐시 적중/MCP 호출 목록), `mcp.call_text`/`mcp.call_json`(툴 이름·인자),
  `tavily.search_fixed`/`tavily.search_with_agent`(검색어 수·문서 수), `rag.vector_search`(필터·k), `db.past_decision`

노트북에서는 `from agent.runner import analyze` → `result = await analyze("AAPL")`로 실행하면 같은 태그가 붙습니다.

**Before/After 숫자 뽑기**

```bash
cd backend
python -m scripts.langsmith_stats                                   # 최근 20개 실행: 전체·노드별 지연, 토큰, 비용
python -m scripts.langsmith_stats --compare web:fixed web:agent     # 검색 방식 비교 (평균)
python -m scripts.langsmith_stats --compare av_cache:cold av_cache:warm
python -m scripts.langsmith_stats --compare verify:off verify:on --ticker AAPL
```

비교 실험 예: 같은 종목을 `python -m scripts.run_analysis AAPL --web fixed`와 `--web agent`로 각각 2~3번 실행한 뒤 `--compare`.

**실험 스크립트**

```bash
# 관련성 검사 모델 라우팅: 정답셋(LangSmith Dataset) 만들기 → 모델별 Experiment
python -m scripts.exp_model_routing build --tickers AAPL NVDA MSFT
python -m scripts.exp_model_routing run --models openai:gpt-4o-mini openai:gpt-4.1-nano --judge v2

# 파이프라인 전체 Before/After (설정을 번갈아 실행 → 변형별 평균)
python -m scripts.exp_pipeline AAPL --variant llm=single --variant llm=tiered --repeat 3
```
