from pathlib import Path

PROJECT_NAME = "WebExtractor"

ROOT = Path(__file__).resolve().parent.parent.parent

OUTPUT_DIR = ROOT / "output"
SAMPLES_DIR = ROOT / "samples"

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 3
MAX_CONNECTIONS = 20

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/138.0 Safari/537.36"
)

DEFAULT_VIEWPORTS = {
    "mobile": {"width": 375, "height": 812},
    "tablet": {"width": 768, "height": 1024},
    "laptop": {"width": 1024, "height": 768},
    "desktop": {"width": 1440, "height": 900},
    "widescreen": {"width": 1920, "height": 1080},
}