from __future__ import annotations

import hashlib
import re


def slugify(value: str, fallback_prefix: str = "page") -> str:
    ascii_value = _to_ascii(value)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_value).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    if slug:
        return slug
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{fallback_prefix}-{digest}"


def _to_ascii(value: str) -> str:
    if value.isascii():
        return value
    try:
        from pypinyin import lazy_pinyin  # type: ignore
    except Exception:
        return value.encode("ascii", errors="ignore").decode("ascii")
    converted = []
    for char in value:
        if char.isascii():
            converted.append(char)
        else:
            converted.extend(lazy_pinyin(char))
    return " ".join(part for part in converted if part)
