import sys

from webextractor.config import config
from webextractor.utils.logger import logger
from webextractor.utils.validator import valid_url


def main() -> None:

    if len(sys.argv) < 2:
        logger.error("Usage: python src/main.py <url>")
        return

    url = sys.argv[1]

    if not valid_url(url):
        logger.error("Invalid URL")
        return

    logger.info(f"Target : {url}")
    logger.info(f"Output : {config.output_dir}")


if __name__ == "__main__":
    main()