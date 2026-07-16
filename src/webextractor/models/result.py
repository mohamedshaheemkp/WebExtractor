from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field

from webextractor.models.asset import Asset


@dataclass(slots=True)
class Result:

    downloaded: list[Asset] = field(default_factory=list)

    failed: list[Asset] = field(default_factory=list)

    skipped: list[Asset] = field(default_factory=list)

    bytes_downloaded: int = 0

    @property
    def success(self) -> int:
        return len(self.downloaded)

    @property
    def failures(self) -> int:
        return len(self.failed)

    @property
    def skipped_count(self) -> int:
        return len(self.skipped)