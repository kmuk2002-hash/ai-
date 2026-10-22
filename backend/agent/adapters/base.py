from datetime import date
from agent.schemas import Market, QuantSnapshot

async def fetch_quant_snapshot(ticker:str, market:Market,as_of_date: date) -> QuantSnapshot:
    if market == "US":
        from agent.adapters import us_alphavantage
        return await us_alphavantage.fetch_snapshot(ticker, as_of_date)

    if market == "KR":
        raise NotImplementedError(
            "국내(KR) 시장은 아직 지원하지 않습니다. KIS(한국투자증권) API 키를 발급받은 뒤 "
            "agent/adapters/kr_kis.py에 어댑터를 구현해야 합니다."
        )

    raise ValueError(f"지원하지 않는 시장: {market}")
