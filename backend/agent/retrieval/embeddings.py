"""
임베딩 모델을 한 곳에서 만든다. (문서 적재와 검색이 같은 모델을 써야 한다)
"""

from functools import lru_cache

from langchain_openai import OpenAIEmbeddings

from agent import config


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL,
        api_key=config.require("OPENAI_API_KEY", config.OPENAI_API_KEY),
    )


def to_pgvector(vec: list[float]) -> str:
    """pgvector 리터럴 '[0.1,0.2,...]'. SQL에서 %s::vector로 캐스팅한다."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
