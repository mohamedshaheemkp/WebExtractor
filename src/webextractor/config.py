from dataclasses import dataclass

from webextractor.constants import (
    OUTPUT_DIR,
    DEFAULT_TIMEOUT,
    MAX_CONNECTIONS,
    MAX_RETRIES,
    USER_AGENT,
)


@dataclass(slots=True)
class Config:

    output_dir = OUTPUT_DIR

    timeout: int = DEFAULT_TIMEOUT

    retries: int = MAX_RETRIES

    connections: int = MAX_CONNECTIONS

    verify_ssl: bool = True

    overwrite: bool = False

    user_agent: str = USER_AGENT


config = Config()