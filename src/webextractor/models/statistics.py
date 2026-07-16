from dataclasses import dataclass


@dataclass(slots=True)
class Statistics:

    total: int = 0

    html: int = 0

    css: int = 0

    js: int = 0

    images: int = 0

    fonts: int = 0

    videos: int = 0

    json: int = 0

    svg: int = 0

    wasm: int = 0

    other: int = 0