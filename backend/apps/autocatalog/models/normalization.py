from __future__ import annotations


def collapse_spaces(value: str) -> str:
    return " ".join((value or "").split())


def normalize_name(value: str) -> str:
    return collapse_spaces(value).casefold()
