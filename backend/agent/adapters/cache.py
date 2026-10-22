import json
from datetime import date
from pathlib import Path
from typing import Any
from agent import config

def _path(source:str, function:str, symbol:str, day:date) -> Path:
    return config.CACHE_DIR/source/day.isoformat()/f"{function}_{symbol}.json"

def load(source:str, function:str, symbol:str, day:date | None=None) ->Any | None:
    p = _path(source, function, symbol, day or date.today())
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None

def save(source:str, function:str, symbol:str, data:Any, day: date | None = None) -> None:
    p = _path(source, function, symbol, day or date.today())
    p.parent.mkdir(parents=True , exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False),encoding="utf-8")

def load_latest_before(source: str, function: str, symbol: str, before: date) -> tuple[date, Any] | None:
    """before 이전 날짜 폴더 중 가장 최근에 저장된 응답을 (날짜, 데이터)로 반환한다.
    예: 미국 장중이라 오늘 일봉을 못 받으면, 어제 받아 둔 일봉 = 직전 장 마감 기준 데이터"""
    base = config.CACHE_DIR / source
    if not base.exists():
        return None
    days = []
    for p in base.iterdir():
        try:
            day = date.fromisoformat(p.name)
        except ValueError:
            continue
        if day < before and (p / f"{function}_{symbol}.json").exists():
            days.append(day)
    if not days:
        return None
    day = max(days)
    return day, load(source, function, symbol, day)
