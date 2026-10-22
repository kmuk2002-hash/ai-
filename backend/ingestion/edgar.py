"""
SEC EDGAR에서 최신 10-K를 받아 Item 1, 1A, 7을 잘라낸다.

SEC는 연락처가 들어간 User-Agent가 없으면 요청을 막는다 (.env의 SEC_EDGAR_USER_AGENT).
초당 10회 제한이 있어서 요청 사이에 잠깐 쉰다.
"""

import re
import time
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from agent import config

TARGET_ITEMS = {
    "1": "Item 1",      # Business
    "1A": "Item 1A",    # Risk Factors
    "7": "Item 7",      # MD&A
}
# 각 Item이 끝나는 지점 = 다음에 나오는 Item 제목
_NEXT_ITEMS = {"1": {"1A", "1B", "1C", "2"}, "1A": {"1B", "1C", "2"}, "7": {"7A", "8"}}
_HEADING = re.compile(r"(?im)^[ \t]*item[ \t]*(1a|1b|1c|7a|1|2|7|8)(?![0-9a-z])")


@dataclass
class TenK:
    ticker: str
    cik: int
    filing_date: str        # 공시일 YYYY-MM-DD
    fiscal_year: str        # 회계연도 (보고 기준일의 연도)
    url: str
    sections: dict[str, str]   # {"Item 1": 본문, ...}


def _client() -> httpx.Client:
    ua = config.require("SEC_EDGAR_USER_AGENT", config.SEC_EDGAR_USER_AGENT)
    return httpx.Client(headers={"User-Agent": ua}, timeout=30, follow_redirects=True)


def _get(client: httpx.Client, url: str) -> httpx.Response:
    time.sleep(0.2)
    r = client.get(url)
    r.raise_for_status()
    return r


def _cik(client: httpx.Client, ticker: str) -> int:
    data = _get(client, "https://www.sec.gov/files/company_tickers.json").json()
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"])
    raise ValueError(f"[EDGAR] 티커를 찾을 수 없습니다: {ticker}")


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n\s*", "\n\n", text)
    return text.strip()


def extract_items(text: str) -> dict[str, str]:
    """목차에도 같은 제목이 있어서, 각 Item 제목 후보 중 '다음 Item까지 가장 긴 구간'을 본문으로 고른다."""
    heads = [(m.start(), m.group(1).upper()) for m in _HEADING.finditer(text)]
    out = {}
    for item, name in TARGET_ITEMS.items():
        best = ""
        for i, (pos, label) in enumerate(heads):
            if label != item:
                continue
            end = next((p for p, lab in heads[i + 1:] if lab in _NEXT_ITEMS[item]), None)
            body = text[pos:end] if end else text[pos:pos + 300_000]
            if len(body) > len(best):
                best = body
        if len(best) > 500:
            out[name] = best.strip()
    return out


def fetch_latest_10k(ticker: str) -> TenK:
    with _client() as client:
        cik = _cik(client, ticker)
        subs = _get(client, f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
        recent = subs["filings"]["recent"]
        for i, form in enumerate(recent["form"]):
            if form == "10-K":
                acc = recent["accessionNumber"][i].replace("-", "")
                doc = recent["primaryDocument"][i]
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"
                html = _get(client, url).text
                return TenK(
                    ticker=ticker.upper(),
                    cik=cik,
                    filing_date=recent["filingDate"][i],
                    fiscal_year=(recent.get("reportDate", [""] * (i + 1))[i] or recent["filingDate"][i])[:4],
                    url=url,
                    sections=extract_items(html_to_text(html)),
                )
    raise ValueError(f"[EDGAR] {ticker}의 10-K를 찾을 수 없습니다.")
