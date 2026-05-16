from __future__ import annotations

import re

FOOTER_PHONE_DIGITS_COUNT = 10
FOOTER_PHONE_FORMAT_EXAMPLE = "38 (0XX) XXX-XX-XX"


def normalize_footer_phone(value: str) -> str:
    digits = _normalize_footer_phone_digits(value)
    if not digits:
        return ""
    if len(digits) != FOOTER_PHONE_DIGITS_COUNT:
        raise ValueError(f"Phone must match format {FOOTER_PHONE_FORMAT_EXAMPLE}.")
    return _format_footer_phone_from_digits(digits)


def format_footer_phone(value: str) -> str:
    digits = _normalize_footer_phone_digits(value)
    if len(digits) == FOOTER_PHONE_DIGITS_COUNT:
        return _format_footer_phone_from_digits(digits)
    return str(value or "").strip()


def _normalize_footer_phone_digits(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if not digits:
        return ""
    if digits.startswith("380"):
        return digits[2:12]
    if digits.startswith("38"):
        rest = digits[2:]
        if not rest:
            return ""
        if rest.startswith("0"):
            return rest[:FOOTER_PHONE_DIGITS_COUNT]
        return f"0{rest}"[:FOOTER_PHONE_DIGITS_COUNT]
    if digits.startswith("0"):
        return digits[:FOOTER_PHONE_DIGITS_COUNT]
    if len(digits) >= FOOTER_PHONE_DIGITS_COUNT:
        tail = digits[-FOOTER_PHONE_DIGITS_COUNT:]
        if tail.startswith("0"):
            return tail
        return f"0{tail}"[:FOOTER_PHONE_DIGITS_COUNT]
    return f"0{digits}"[:FOOTER_PHONE_DIGITS_COUNT]


def _format_footer_phone_from_digits(digits: str) -> str:
    operator = digits[:3]
    left = digits[3:6]
    middle = digits[6:8]
    right = digits[8:10]
    return f"38 ({operator}) {left}-{middle}-{right}"
