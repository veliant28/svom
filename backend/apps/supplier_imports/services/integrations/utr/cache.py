from __future__ import annotations

from urllib.parse import quote

from django.core.cache import cache


def build_cache_key(*parts: str) -> str:
    normalized_parts: list[str] = []
    for part in parts:
        text = str(part or "").strip().lower()
        if not text:
            text = "_"
        normalized_parts.append(quote(text, safe=""))
    return "utr:api:" + ":".join(normalized_parts)


def cache_get(key: str):
    try:
        return cache.get(key)
    except Exception:
        return None


def cache_set(key: str, value, *, timeout: int) -> None:
    try:
        cache.set(key, value, timeout=timeout)
    except Exception:
        return


def cache_delete(key: str) -> None:
    try:
        cache.delete(key)
    except Exception:
        return
