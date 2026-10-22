"""
State 및 데이터 스키마 정의

- 그래프 State (MainState, FundamentalState): TypedDict
- LLM 구조화 출력 / 외부 API 데이터 / DB 저장용 모델: Pydantic BaseModel
"""

from datetime import date, datetime
from typing import Literal, Optional, TypedDict

from langchain_core.documents import Document
from pydantic import BaseModel, Field, field_validator, model_validator


# ─────────────────────────────────────────────
# 공통 타입
# ─────────────────────────────────────────────

Market = Literal["US", "KR"]

# 하이라이트 태그 (DB 저장값은 영문, 프론트 표시는 한글)
#   support    🟢 근거      : 매수 근거로 채택
#   concern    🔴 우려      : 리스크로 인정
#   to_verify  🟡 확인 필요 : 다음 실적 등에서 검증할 것
#   disagree   ⚪ 반대      : 에이전트 분석에 동의하지 않음
HighlightTag = Literal["support", "concern", "to_verify", "disagree"]

# 하이라이트를 달 수 있는 리포트 섹션
ReportField = Literal[
    "investment_thesis",
    "risks",
    "consensus_gap",
    "thesis_breakers",
    "past_decision_review",
]

DecisionAction = Literal["buy", "hold", "sell"]


class Source(BaseModel):
    """리포트·요약의 근거 출처"""

    title: str = Field(description="문서 또는 페이지 제목")
    url: Optional[str] = Field(default=None, description="출처 URL (로컬 문서면 없음)")
    doc_type: Literal["10-K", "10-Q", "broker_report", "web", "quant_api"] = Field(
        description="출처 종류"
    )
    section: Optional[str] = Field(
        default=None, description="10-K 섹션 등 세부 위치 (예: Item 1A)"
    )


# ─────────────────────────────────────────────
# 퀀트 스냅샷 (시장 공통, API → 변환)
# ─────────────────────────────────────────────


class QuantSnapshot(BaseModel):
    """퀀트 노드가 시장별 어댑터로 가져와 변환한 공통 스냅샷.
    결정 시점의 값을 박제하는 용도이므로 as_of_date를 반드시 채운다."""

    ticker: str
    market: Market
    as_of_date: date
    currency: str = Field(description="USD, KRW 등")

    # 기업 정보
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = None

    # 가격 / 거래
    price: Optional[float] = None
    change_pct: Optional[float] = Field(default=None, description="전일 대비 등락률(%)")
    volume: Optional[int] = None

    # 밸류에이션 / 수익성
    per: Optional[float] = None
    forward_per: Optional[float] = None
    pbr: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None
    profit_margin: Optional[float] = None
    dividend_yield: Optional[float] = None

    # 기술적 지표 / 모멘텀
    ma_50: Optional[float] = Field(default=None, description="50일 이동평균")
    ma_200: Optional[float] = Field(default=None, description="200일 이동평균")
    volatility_60d: Optional[float] = Field(
        default=None, description="최근 60거래일 일간 수익률 표준편차(연율화)"
    )
    return_6m: Optional[float] = Field(default=None, description="6개월 수익률(%)")
    return_12m: Optional[float] = Field(default=None, description="12개월 수익률(%)")

    # 컨센서스 (consensus_gap의 근거)
    analyst_target_price: Optional[float] = None
    eps_estimate: Optional[float] = Field(default=None, description="직전 분기 예상 EPS")
    eps_actual: Optional[float] = Field(default=None, description="직전 분기 실제 EPS")
    eps_surprise_pct: Optional[float] = Field(
        default=None, description="(실제 - 예상) / |예상| × 100"
    )

    @field_validator(
        "market_cap", "price", "change_pct", "volume",
        "per", "forward_per", "pbr", "roe", "roa", "profit_margin", "dividend_yield",
        "ma_50", "ma_200", "volatility_60d", "return_6m", "return_12m",
        "analyst_target_price", "eps_estimate", "eps_actual", "eps_surprise_pct",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, v):
        # Alpha Vantage는 값이 없을 때 "None", "-" 같은 문자열을 반환하는 경우가 있음
        if isinstance(v, str):
            v = v.strip().rstrip("%")
            if v in ("", "None", "-", "N/A"):
                return None
        return v


# ─────────────────────────────────────────────
# 펀더멘털 요약 (RAG 서브그래프의 결과, LLM 구조화 출력)
# ─────────────────────────────────────────────


class FundamentalSummary(BaseModel):
    """펀더멘털 서브그래프가 문서를 읽고 정리한 결과.
    숫자 지표는 QuantSnapshot에 두고, 여기에는 문서 기반 해석만 담는다."""

    business_overview: str = Field(
        description="사업 구조, 주요 제품과 매출원, 경쟁 환경 (10-K Item 1 중심)"
    )
    stated_risks: str = Field(
        description="회사가 직접 밝힌 주요 리스크 (10-K Item 1A 중심)"
    )
    management_outlook: str = Field(
        description="경영진의 실적 해석과 향후 전망 (10-K Item 7 MD&A 중심)"
    )
    recent_issues: str = Field(
        description="최근 뉴스, 증권사 리포트에서 확인된 이슈"
    )
    sources: list[Source] = Field(description="요약에 사용한 출처")


# ─────────────────────────────────────────────
# 리포트
# ─────────────────────────────────────────────


class ReportDraft(BaseModel):
    """write_report 노드의 LLM 구조화 출력.
    과거 판단을 보지 않고 작성하므로 past_decision_review는 포함하지 않는다."""

    investment_thesis: str = Field(description="투자 논리: 이 종목을 보유할 이유")
    risks: str = Field(description="주요 리스크")
    consensus_gap: str = Field(
        description="시장 기대치(목표주가, 예상 EPS 등)와 현재 데이터가 갈리는 지점"
    )
    thesis_breakers: str = Field(
        description="이 투자 논리가 틀렸다고 판단할 구체적인 조건"
    )
    sources: list[Source] = Field(description="리포트 작성에 사용한 출처")


class PastDecisionCheck(BaseModel):
    """compare_with_past의 점검 항목 1건"""

    category: Literal["data_change", "thesis_breaker", "to_verify", "thesis_validity"] = Field(
        description=(
            "data_change: 과거 대비 수치 변화 / "
            "thesis_breaker: 내가 정한 철회 조건 점검 / "
            "to_verify: '확인 필요' 하이라이트 점검 / "
            "thesis_validity: 매수 근거 유효성 점검"
        )
    )
    target: str = Field(description="점검 대상 (철회 조건 문장, 하이라이트 원문 등)")
    status: Literal["triggered", "not_triggered", "insufficient_evidence"] = Field(
        description="해당함 / 해당하지 않음 / 판단 근거 부족"
    )
    evidence: str = Field(description="판단 근거")
    sources: list[Source] = Field(default_factory=list)


class PastDecisionReview(BaseModel):
    """compare_with_past 노드의 LLM 구조화 출력. 매수·매도를 권하지 않는다."""

    summary: str = Field(description="과거 결정 대비 달라진 점 요약")
    checks: list[PastDecisionCheck]


class Report(ReportDraft):
    """DB에 저장되는 최종 리포트 (저장 후 수정하지 않음)"""

    ticker: str
    market: Market
    as_of_date: date
    quant_snapshot: QuantSnapshot
    past_decision_review: Optional[PastDecisionReview] = None


# ─────────────────────────────────────────────
# 과거 결정 (DB → past_decision 노드)
# ─────────────────────────────────────────────


class HighlightSpan(BaseModel):
    """하이라이트 조각: 섹션 하나 안의 연속된 범위.
    드래그가 여러 섹션에 걸치면 프론트가 섹션마다 조각을 하나씩 만든다."""

    field: ReportField = Field(description="조각이 속한 섹션 (프론트가 자동으로 채움)")
    start_offset: int = Field(ge=0, description="섹션 텍스트 기준 시작 위치")
    end_offset: int = Field(description="섹션 텍스트 기준 끝 위치 (미포함)")
    quoted_text: str = Field(description="해당 범위의 원문 복사본")

    @model_validator(mode="after")
    def _check_range(self):
        if self.end_offset <= self.start_offset:
            raise ValueError("end_offset은 start_offset보다 커야 합니다")
        return self


class HighlightGroup(BaseModel):
    """사용자의 하이라이트 1회 = 그룹 1개. 태그와 메모는 그룹에 한 번만 단다."""

    id: Optional[str] = Field(default=None, description="DB 저장 후 부여되는 ID")
    tag: HighlightTag
    comment: Optional[str] = Field(default=None, description="사용자 메모 원문")
    spans: list[HighlightSpan] = Field(min_length=1, description="섹션별 조각 (보통 1개)")
    created_at: Optional[datetime] = None


class Decision(BaseModel):
    ticker: str
    market: Market
    decided_at: datetime
    action: DecisionAction
    weight: Optional[float] = Field(default=None, description="포트폴리오 비중(0~1)")
    confidence: int = Field(ge=1, le=5, description="확신도 1~5")
    my_thesis: str = Field(description="내 투자 논리")
    my_thesis_breaker: str = Field(
        description="내가 정한 철회 조건 (결정할 때마다 이전 값을 이어서 복사)"
    )


class PastDecision(BaseModel):
    """past_decision 노드가 SQL로 조회해 compare_with_past에 넘기는 묶음"""

    decision: Decision
    report: Report = Field(description="당시 참고한 리포트 스냅샷")
    highlights: list[HighlightGroup] = Field(
        default_factory=list, description="당시 리포트에 남긴 하이라이트 전체"
    )
    evidence_group_ids: list[str] = Field(
        default_factory=list, description="이 결정의 근거로 연결한 하이라이트 그룹 ID"
    )


# ─────────────────────────────────────────────
# 그래프 State
# ─────────────────────────────────────────────


class MainState(TypedDict):
    # 입력
    ticker: str
    market: Market
    as_of_date: date

    # 병렬 노드 결과 (각 노드가 서로 다른 키에만 쓰므로 리듀서 불필요)
    fundamental_summary: Optional[FundamentalSummary]  # fundamental 서브그래프
    quant_snapshot: Optional[QuantSnapshot]  # quant 노드
    quant_summary: Optional[str]  # quant 노드 (수치 해석)
    past_decision: Optional[PastDecision]  # past_decision 노드 (없으면 None)

    # 후속 노드 결과
    report: Optional[Report]  # write_report → compare_with_past가 review 추가


class FundamentalState(TypedDict):
    """펀더멘털 서브그래프 전용 State (메인 State와 분리)"""

    # 메인 그래프에서 전달받는 값
    ticker: str
    market: Market
    as_of_date: date

    # 내부 처리용
    question: str
    vector_docs: list[Document]
    web_docs: list[Document]
    context: list[Document]
    relevance: Literal["yes", "no"]
    retry_count: int

    # 결과 (메인 State의 fundamental_summary로 옮겨짐)
    summary: Optional[FundamentalSummary]