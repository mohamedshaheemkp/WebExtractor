from webextractor.verification.report import VerificationReport
from webextractor.verification.screenshots import ScreenshotComparator
from webextractor.verification.visual_diff import VisualDiffScorer
from webextractor.verification.spatial_tree import SpatialTreeExtractor
from webextractor.verification.spatial_comparator import SpatialComparator, LayoutViolation
from webextractor.verification.auto_repair import LayoutAutoRepair

__all__ = [
    "VerificationReport",
    "ScreenshotComparator",
    "VisualDiffScorer",
    "SpatialTreeExtractor",
    "SpatialComparator",
    "LayoutViolation",
    "LayoutAutoRepair",
]
