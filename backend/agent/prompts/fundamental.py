"""
펀더멘털 서브그래프의 프롬프트와 검색어.
"""

# ─────────────────────────────────────────────
# 방식 A: 처음 검색할 검색어 (영어가 검색 결과가 더 많다)
#   (검색어 틀, 최근 며칠만 볼지 / None이면 기간 제한 없음)
# ─────────────────────────────────────────────
FIXED_QUERIES: list[tuple[str, int | None]] = [
    ("{ticker} company business model revenue segments competitive position", None),
    ("{ticker} 10-K risk factors key business risks", None),
    ("{ticker} latest earnings call guidance outlook analyst expectations", 120),
    ("{ticker} stock news", 30),
]


# ─────────────────────────────────────────────
# 방식 B: ReAct 에이전트
# ─────────────────────────────────────────────
AGENT_SYSTEM = """You are a research assistant collecting source material for an equity research report.
Use the search tool to find information. You do not need to write the report yourself.

Rules:
- Search in English.
- Always pass end_date="{as_of_date}" so that no article published after {as_of_date} is used.
- Use at most {max_searches} searches. Each search should target a different gap.
- When you have enough material, reply with one short sentence listing what you found and stop."""

AGENT_TASK = """Collect material on {ticker} for these four topics:
1. Business model, revenue segments, competitive position
2. Key risks the company itself discloses (e.g., 10-K risk factors)
3. Management outlook, guidance, and analyst expectations from the latest earnings
4. Recent news that could move the stock

Current information need: {question}"""


# ─────────────────────────────────────────────
# 관련성 검사 / 검색어 재작성 / 요약
# ─────────────────────────────────────────────
RELEVANCE_SYSTEM = """당신은 리서치 자료를 검토하는 편집자입니다.
수집된 문서들로 다음 네 가지를 쓸 수 있는지 판단합니다.
  1) 사업 구조와 경쟁 환경  2) 회사가 밝힌 리스크  3) 경영진 전망·가이던스  4) 최근 이슈
네 가지 중 셋 이상을 문서 내용으로 뒷받침할 수 있으면 relevant를 "yes", 아니면 "no"로 답합니다.
"no"일 때는 missing에 부족한 주제를 짧게 적습니다."""

# [v2] 집계는 코드가 한다. LLM은 주제별로 근거 문서 번호만 고른다.
COVERAGE_SYSTEM = """당신은 리서치 자료를 검토하는 편집자입니다.
아래 네 주제 각각에 대해, 그 주제의 내용을 실제로 담고 있는 문서의 번호([숫자])를 고릅니다.
  business_docs : 사업 구조, 주요 제품과 매출원, 경쟁 환경
  risk_docs     : 회사가 밝힌 리스크 (10-K 위험 요인 등)
  outlook_docs  : 경영진 전망, 가이던스, 실적 발표, 애널리스트 기대
  news_docs     : 최근 뉴스와 이슈
규칙
- 제목이나 본문에 그 주제의 구체적인 내용이 있을 때만 고릅니다. 회사 이름만 나오는 것은 해당하지 않습니다.
- 해당하는 문서가 없으면 빈 목록으로 둡니다. 억지로 채우지 않습니다.
- 한 문서가 여러 주제에 해당할 수 있습니다."""

RELEVANCE_HUMAN = """[종목] {ticker}

[수집된 문서]
{docs}"""

REWRITE_SYSTEM = """당신은 검색어를 만드는 리서처입니다.
부족한 정보를 찾기 위한 웹 검색어 하나를 영어로 만듭니다.
종목 티커를 포함하고, 10단어 이내로 씁니다. 검색어만 답합니다."""

REWRITE_HUMAN = """[종목] {ticker}
[부족한 정보] {question}
[이미 찾은 문서 제목]
{titles}"""

SUMMARY_SYSTEM = """당신은 기업 분석 자료를 정리하는 리서치 애널리스트입니다.
수집된 문서만을 근거로 네 항목을 한국어로 요약합니다.

[작성 규칙]
1. 마크다운 없이 일반 문장으로, 각 항목 3~5문장으로 씁니다.
2. 문서에 없는 내용을 지어내지 않습니다. 당신이 원래 알고 있는 정보를 덧붙이지 않습니다.
3. 문서에서 찾을 수 없는 항목은 "수집된 자료에서 확인되지 않음"이라고만 씁니다.
4. 숫자(매출, 성장률, 가이던스 등)는 문서에 나온 그대로 옮깁니다.
5. used_doc_ids에는 요약에 실제로 사용한 문서 번호만 넣습니다."""

SUMMARY_HUMAN = """[종목] {ticker}
[기준일] {as_of_date}

[수집된 문서]
{docs}"""