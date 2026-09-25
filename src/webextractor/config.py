from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from webextractor.constants import (
    DEFAULT_VIEWPORTS,
    OUTPUT_DIR,
    DEFAULT_TIMEOUT,
    MAX_CONNECTIONS,
    MAX_RETRIES,
    USER_AGENT,
)


@dataclass(slots=True)
class Config:

    output_dir: Path = OUTPUT_DIR

    timeout: int = DEFAULT_TIMEOUT

    retries: int = MAX_RETRIES

    workers: int = 8

    connections: int = MAX_CONNECTIONS

    verify_ssl: bool = True

    overwrite: bool = False

    download_chunk_size: int = 16384

    user_agent: str = USER_AGENT

    target: str = "next"  # "next" or "html"

    audit: bool = True  # Run validation audit

    viewports: dict[str, dict[str, int]] = field(
        default_factory=lambda: dict(DEFAULT_VIEWPORTS)
    )


config = Config()