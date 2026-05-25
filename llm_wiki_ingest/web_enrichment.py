from __future__ import annotations

from typing import Mapping


ALLOWED_WEB_SOURCE_TYPES = {
    "museum",
    "library",
    "university",
    "government",
    "encyclopedia",
    "publisher",
}
WEB_SOURCE_REQUIRED_FIELDS = ("title", "url", "source_type", "accessed_at")


def web_source_identity(source: Mapping[str, str]) -> tuple[str, str, str, str]:
    return (
        str(source.get("title", "")),
        str(source.get("url", "")),
        str(source.get("source_type", "")),
        str(source.get("accessed_at", "")),
    )
