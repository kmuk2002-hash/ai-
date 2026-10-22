"""
서버 설정. 키와 DB 주소는 agent.config가 .env에서 읽은 값을 그대로 쓴다.
"""

import logging


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
