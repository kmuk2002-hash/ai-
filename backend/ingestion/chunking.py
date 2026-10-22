"""
긴 본문을 검색하기 좋은 크기로 자른다. 문단 경계를 유지하고, 조각끼리 조금씩 겹친다.
"""

CHUNK_CHARS = 1500
OVERLAP_CHARS = 200


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = OVERLAP_CHARS) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paragraphs:
        while len(p) > size:                      # 문단 하나가 너무 길면 강제로 자른다
            if buf:
                chunks.append(buf); buf = ""
            chunks.append(p[:size]); p = p[size - overlap:]
        if len(buf) + len(p) + 2 > size and buf:
            chunks.append(buf)
            buf = buf[-overlap:] + "\n\n" + p      # 앞 조각의 끝부분을 이어 붙여 문맥 유지
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    return [c for c in chunks if len(c) > 100]
