import re


INVALID = r'[<>:"\\|?*]'


def filename(name: str) -> str:
    return re.sub(INVALID, "_", name)