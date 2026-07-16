from dataclasses import dataclass, field

from webextractor.models.asset import Asset


@dataclass(slots=True)
class Result:

    success: list[Asset] = field(default_factory=list)

    failed: list[Asset] = field(default_factory=list)