"""
여러 프롬프트가 같이 쓰는 자료 정리 함수.
"""

from agent import schemas

# QuantSnapshot 필드 → 프롬프트에 보여줄 이름과 단위
_QUANT_LABELS = [
    ("price", "현재가", ""),
    ("change_pct", "전일 대비", "%"),
    ("per", "PER(최근 4분기 EPS 기준)", "배"),
    ("forward_per", "Forward PER", "배"),
    ("pbr", "PBR", "배"),
    ("roe", "ROE", "%"),
    ("profit_margin", "순이익률", "%"),
    ("ma_50", "50일 이동평균", ""),
    ("ma_200", "40주 이동평균", ""),
    ("return_6m", "6개월 수익률", "%"),
    ("return_12m", "12개월 수익률", "%"),
    ("volatility_60d", "60일 변동성(연율)", "%"),
    ("analyst_target_price", "애널리스트 목표주가", ""),
    ("eps_estimate", "직전 분기 예상 EPS", ""),
    ("eps_actual", "직전 분기 실제 EPS", ""),
    ("eps_surprise_pct", "직전 분기 EPS 서프라이즈", "%"),
]


def quant_lines(s: schemas.QuantSnapshot) -> str:
    """값이 있는 지표만 한 줄씩. None인 지표는 아예 보여주지 않는다.
    (LLM이 없는 지표를 언급하거나 추측할 근거를 주지 않기 위해)"""
    lines = []
    for field, label, unit in _QUANT_LABELS:
        v = getattr(s, field)
        if v is not None:
            lines.append(f"{label}: {v:,.2f}{unit}")
    return "\n".join(lines) if lines else "데이터 없음"