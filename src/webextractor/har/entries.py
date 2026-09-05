from __future__ import annotations

import base64
from typing import Any


class HAREntryExtractor:
    """Helper to extract and decode data from HAR entries."""

    @staticmethod
    def get_url(entry: dict[str, Any]) -> str:
        return entry.get("request", {}).get("url", "")

    @staticmethod
    def get_method(entry: dict[str, Any]) -> str:
        return entry.get("request", {}).get("method", "GET")

    @staticmethod
    def get_status(entry: dict[str, Any]) -> int | None:
        return entry.get("response", {}).get("status")

    @staticmethod
    def get_mime_type(entry: dict[str, Any]) -> str:
        response = entry.get("response", {})
        content = response.get("content", {})
        return content.get("mimeType") or response.get("mimeType", "")

    @staticmethod
    def get_response_body(entry: dict[str, Any]) -> str | bytes | None:
        content = entry.get("response", {}).get("content", {})
        text = content.get("text")
        if text is None:
            return None

        if content.get("encoding") == "base64":
            try:
                return base64.b64decode(text)
            except Exception:
                return text
        return text

    @staticmethod
    def get_size(entry: dict[str, Any]) -> int:
        response = entry.get("response", {})
        content = response.get("content", {})
        size = content.get("size")
        if size is not None:
            return int(size)
        return int(response.get("bodySize", 0))
