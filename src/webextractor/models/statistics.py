from dataclasses import dataclass, field
from webextractor.models.asset import AssetType


@dataclass(slots=True)
class Statistics:

    total: int = 0

    downloaded: int = 0

    failed: int = 0

    skipped: int = 0

    by_type: dict[AssetType, int] = field(default_factory=lambda: {t: 0 for t in AssetType})