import asyncio
import math
from datetime import date, datetime, timedelta
from typing import Any

from agent import mcp_client
from agent.adapters import cache
from agent.schemas import QuantSnapshot
from agent.tracing import annotate, traced

SERVER = "alphavantage"
SOURCE = "alphavantage"
CALL_INTERVAL_SEC = 1.2   # 무료 플랜: 초당 1회 제한

# (툴 이름, symbol 외에 추가로 넘길 인자)
#   datatype="json"      : 시계열 툴은 기본이 CSV라서 JSON으로 요청
#   return_full_data=True: 응답이 클 때 일부만 주지 않고 전체를 받도록 요청 (시계열)
#
# COMPANY_OVERVIEW는 유료 전용이라 쓰지 않는다. (무료 키로 호출하면 "premium endpoint" 응답)
#   → PER은 EARNINGS로 직접 계산하고, PBR·ROE·목표주가·업종 등은 None(데이터 없음)으로 둔다.
# 종목당 3회 호출 → 무료 플랜(하루 25회)으로 캐시 없이 하루 8종목
FUNCTIONS: list[tuple[str, dict]] = [
    ("EARNINGS", {}),
    ("TIME_SERIES_DAILY", {"outputsize": "compact", "datatype": "json", "return_full_data": True}),
    ("TIME_SERIES_WEEKLY", {"datatype": "json", "return_full_data": True}),
]


async def _fetch_all(symbol: str) -> dict[str, dict]:
    """4개 툴 결과를 모은다. 캐시에 있는 것은 건너뛰고, 없는 것만 MCP로 호출한다.
    중간에 하나가 실패해도 성공한 응답은 바로 캐시에 저장해서 호출 횟수를 낭비하지 않는다."""
    raw = {fn: cache.load(SOURCE, fn, symbol) for fn, _ in FUNCTIONS}
    # 예전에 실수로 저장된 에러 응답이 캐시에 있으면 무시하고 다시 받는다
    raw = {fn: (None if _api_message(data) else data) for fn, data in raw.items()}
    missing = [(fn, extra) for fn, extra in FUNCTIONS if raw[fn] is None]

    # 오늘 이미 일봉 권한 오류를 받았다면, 장이 끝날 때까지 다시 부르지 않는다 (호출 한도 절약)
    if raw["TIME_SERIES_DAILY"] is None and _daily_blocked_recently(symbol):
        missing = [(fn, extra) for fn, extra in missing if fn != "TIME_SERIES_DAILY"]
        _use_previous_daily(raw, symbol)

    annotate(
        cache_hits=[fn for fn, _ in FUNCTIONS if raw[fn] is not None],
        mcp_calls=[fn for fn, _ in missing],
        cache="warm" if not missing else "cold",
    )

    if missing:
        errors: list[Exception] = []
        async with mcp_client.session(SERVER) as s:
            for i, (fn, extra) in enumerate(missing):
                if i > 0:
                    await asyncio.sleep(CALL_INTERVAL_SEC)   # 연달아 부르면 초당 제한에 걸림
                try:
                    data = await mcp_client.call_json(s, fn, {"symbol": symbol, **extra})
                    _raise_if_api_message(fn, data)
                except RuntimeError as e:
                    errors.append(e)      # 실패한 툴은 기록만 하고 다음 툴로
                    continue
                raw[fn] = data
                cache.save(SOURCE, fn, symbol, data)   # 성공한 응답은 바로 저장

        # 일봉(TIME_SERIES_DAILY)은 미국 장중에 무료 키로 호출하면
        # "realtime US market data" 권한 오류가 날 수 있다 → 주봉으로 대체하고 계속 진행
        fatal = [e for e in errors if "TIME_SERIES_DAILY" not in str(e)]
        if fatal:
            raise fatal[0]
        if errors:
            cache.save(SOURCE, DAILY_BLOCK_MARK, symbol, {"at": datetime.now().isoformat()})
            _use_previous_daily(raw, symbol)

    return raw


# ─────────────────────────────────────────────
# 장중 일봉 대체: 직전 장 마감 일봉 → 없으면 주봉
#   무료 키로 미국 장중에 TIME_SERIES_DAILY를 부르면 "realtime US market data" 권한 오류가 난다.
#   전날 받아 둔 일봉 캐시가 있으면 그게 곧 직전 장 마감 기준 데이터다.
# ─────────────────────────────────────────────
DAILY_BLOCK_MARK = "TIME_SERIES_DAILY__blocked"
DAILY_BLOCK_MINUTES = 60   # 권한 오류 후 이 시간 동안은 일봉을 다시 부르지 않는다


def _daily_blocked_recently(symbol: str) -> bool:
    mark = cache.load(SOURCE, DAILY_BLOCK_MARK, symbol)
    if not mark:
        return False
    try:
        return datetime.now() - datetime.fromisoformat(mark["at"]) < timedelta(minutes=DAILY_BLOCK_MINUTES)
    except (KeyError, ValueError):
        return False


def _use_previous_daily(raw: dict, symbol: str) -> None:
    prev = cache.load_latest_before(SOURCE, "TIME_SERIES_DAILY", symbol, date.today())
    if prev and not _api_message(prev[1]):
        day, data = prev
        raw["TIME_SERIES_DAILY"] = data
        print(f"[Alpha Vantage] {symbol}: 장중이라 오늘 일봉을 받을 수 없어 {day}에 받아 둔 일봉(직전 장 마감 기준)을 씁니다.")
        annotate(daily_source=f"previous_cache:{day}")
    else:
        print(f"[Alpha Vantage] {symbol}: 장중이라 일봉을 받을 수 없고 이전 일봉 캐시도 없어 주봉으로 대체합니다.")
        annotate(daily_source="weekly_fallback")


def _api_message(data: Any) -> str | None:
    """응답이 데이터가 아니라 안내/에러 메시지면 그 내용을, 정상 데이터면 None을 반환한다.

    Alpha Vantage는 실패해도 정상 JSON으로 안내 문구를 보낸다.
      - MCP 서버 형식 : {"error": {"type": "rate_limit", "message": "...", "detail": "..."}}
      - REST API 형식 : {"Information": "..."} / {"Note": "..."} / {"Error Message": "..."}
      - 없는 티커     : {}
    """
    if not isinstance(data, dict):
        return None
    if not data:
        return "빈 응답 (티커를 확인하세요)"
    err = data.get("error")
    if isinstance(err, dict):
        return f"{err.get('type', 'error')}: {err.get('message', '')}"
    if isinstance(err, str):
        return err
    for key in ("Error Message", "Information", "Note"):
        if key in data:
            return str(data[key])
    return None


def _raise_if_api_message(function: str, data: Any) -> None:
    msg = _api_message(data)
    if msg:
        raise RuntimeError(f"[Alpha Vantage] {function}: {msg}")


def _num(v: Any) -> float | None:
    """'31.5' → 31.5, 'None' / '-' / '' → None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    v = str(v).strip().rstrip("%")
    if v in ("", "None", "-", "N/A"):
        return None
    try:
        return float(v)
    except ValueError:
        return None
 
 
def _pct(v: Any) -> float | None:
    """소수 비율 → 퍼센트. '0.157' → 15.7"""
    n = _num(v)
    return None if n is None else round(n * 100, 4)
 
 
def _closes(series: dict, as_of: date) -> list[tuple[date, float, float]]:
    """{'2026-10-17': {'4. close': '..', '5. volume': '..'}} → [(날짜, 종가, 거래량)] 오래된 순.
    as_of_date 이후 데이터는 버린다(미래 정보 누수 방지)."""
    rows = []
    for d, bar in series.items():
        day = date.fromisoformat(d)
        if day <= as_of:
            rows.append((day, float(bar["4. close"]), float(bar.get("5. volume", 0))))
    rows.sort(key=lambda r: r[0])
    return rows
 
 
def _return_since(rows: list[tuple[date, float, float]], as_of: date, days: int) -> float | None:
    """as_of 기준 days일 전에 가장 가까운(그 이전) 종가 대비 수익률(%)"""
    if not rows:
        return None
    target = as_of - timedelta(days=days)
    past = [r for r in rows if r[0] <= target]
    if not past:
        return None
    start, end = past[-1][1], rows[-1][1]
    return round((end / start - 1) * 100, 4)
 
 
def _volatility(rows: list[tuple[date, float, float]], n: int = 60) -> float | None:
    """최근 n거래일 일간 로그수익률 표준편차, 연율화(%)"""
    closes = [r[1] for r in rows[-(n + 1):]]
    if len(closes) < n + 1:
        return None
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:])]
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    return round(math.sqrt(var) * math.sqrt(252) * 100, 4)
 
 
def _ttm_eps(earnings: dict, as_of: date) -> float | None:
    """as_of_date 이전에 발표된 최근 4개 분기 EPS 합 (TTM EPS)"""
    quarters = [
        q for q in earnings.get("quarterlyEarnings", [])
        if q.get("reportedDate") and date.fromisoformat(q["reportedDate"]) <= as_of
    ]
    quarters.sort(key=lambda q: q["reportedDate"])
    eps = [_num(q.get("reportedEPS")) for q in quarters[-4:]]
    if len(eps) < 4 or any(v is None for v in eps):
        return None
    return sum(eps)


def _moving_average(rows: list[tuple[date, float, float]], n: int) -> float | None:
    """최근 n개 종가의 단순 이동평균"""
    closes = [r[1] for r in rows[-n:]]
    return round(sum(closes) / n, 4) if len(closes) == n else None


def _latest_quarter(earnings: dict, as_of: date) -> dict | None:
    """as_of_date 이전에 발표된 가장 최근 분기 실적"""
    quarters = [
        q for q in earnings.get("quarterlyEarnings", [])
        if q.get("reportedDate") and date.fromisoformat(q["reportedDate"]) <= as_of
    ]
    quarters.sort(key=lambda q: q["reportedDate"])
    return quarters[-1] if quarters else None
 
 
# ─────────────────────────────────────────────
# 메인 함수
# ─────────────────────────────────────────────
 
 
@traced("alphavantage.fetch_snapshot", process_outputs=lambda s: {"price": s.price, "per": s.per, "eps_surprise_pct": s.eps_surprise_pct} if s else {})
async def fetch_snapshot(ticker: str, as_of_date: date) -> QuantSnapshot:
    symbol = ticker.upper()

    raw = await _fetch_all(symbol)
    earnings = raw["EARNINGS"]
    daily = raw["TIME_SERIES_DAILY"] or {}      # 장중 권한 오류 시 None → 주봉으로 대체
    weekly = raw["TIME_SERIES_WEEKLY"]

    daily_rows = _closes(daily.get("Time Series (Daily)", {}), as_of_date)
    weekly_rows = _closes(weekly.get("Weekly Time Series", {}), as_of_date)
    if not daily_rows and not weekly_rows:
        raise RuntimeError(f"[Alpha Vantage] {symbol}: {as_of_date} 이전 시세가 없습니다.")

    has_daily = bool(daily_rows)
    base = daily_rows if has_daily else weekly_rows
    last, prev = base[-1], (base[-2] if len(base) > 1 else None)
    price = last[1]
    q = _latest_quarter(earnings, as_of_date) or {}

    # PER = 현재가 ÷ 최근 4분기 EPS 합. 적자(EPS ≤ 0)면 PER이 의미가 없어 None
    ttm = _ttm_eps(earnings, as_of_date)
    per = round(price / ttm, 4) if ttm and ttm > 0 else None

    return QuantSnapshot(
        ticker=symbol,
        market="US",
        as_of_date=as_of_date,
        currency="USD",
        # 기업 정보: 무료 툴로는 얻을 수 없음
        sector=None,
        industry=None,
        market_cap=None,
        # 가격 / 거래 (일별 시세의 마지막 거래일)
        price=price,
        # 일봉이 없으면 전일 대비·거래량은 구할 수 없어 None (주봉 기준 값으로 오해하지 않도록)
        change_pct=round((price / prev[1] - 1) * 100, 4) if prev and has_daily else None,
        volume=int(last[2]) if has_daily else None,
        # 밸류에이션 / 수익성: PER만 직접 계산, 나머지는 유료 데이터라 None
        per=per,
        forward_per=None,
        pbr=None,
        roe=None,
        roa=None,
        profit_margin=None,
        dividend_yield=None,
        # 기술적 지표 / 모멘텀
        ma_50=_moving_average(daily_rows, 50),
        ma_200=_moving_average(weekly_rows, 40),   # 일봉은 100일치뿐이라 40주 이동평균으로 근사
        volatility_60d=_volatility(daily_rows, 60),
        return_6m=_return_since(weekly_rows, as_of_date, 182),
        return_12m=_return_since(weekly_rows, as_of_date, 365),
        # 컨센서스
        analyst_target_price=None,
        eps_estimate=_num(q.get("estimatedEPS")),
        eps_actual=_num(q.get("reportedEPS")),
        eps_surprise_pct=_num(q.get("surprisePercentage")),
    )
