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