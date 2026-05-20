from __future__ import annotations

import re

FOOTER_PHONE_DIGITS_COUNT = 10
FOOTER_PHONE_FORMAT_MOBILE = "mobile"
FOOTER_PHONE_FORMAT_TOLL_FREE_0800 = "toll_free_0800"
FOOTER_PHONE_FORMAT_EXAMPLE_MOBILE = "38 (0XX) XXX-XX-XX"
FOOTER_PHONE_FORMAT_EXAMPLE_0800 = "0 (800) XXX-XXX"


def normalize_footer_phone(value: str, phone_format: str = FOOTER_PHONE_FORMAT_MOBILE) -> str:
    normalized_format = _normalize_phone_format(phone_format)
    digits = _normalize_footer_phone_digits(value, normalized_format)
    if not digits:
        return ""
    if normalized_format == FOOTER_PHONE_FORMAT_TOLL_FREE_0800:
        if len(digits) != FOOTER_PHONE_DIGITS_COUNT or not digits.startswith("0800"):
            raise ValueError(f"Phone must match format {FOOTER_PHONE_FORMAT_EXAMPLE_0800}.")
        return _format_footer_phone_0800_from_digits(digits)
    if len(digits) != FOOTER_PHONE_DIGITS_COUNT:
        raise ValueError(f"Phone must match format {FOOTER_PHONE_FORMAT_EXAMPLE_MOBILE}.")
    return _format_footer_phone_mobile_from_digits(digits)


def format_footer_phone(value: str, phone_format: str = FOOTER_PHONE_FORMAT_MOBILE) -> str:
    normalized_format = _normalize_phone_format(phone_format)
    digits = _normalize_footer_phone_digits(value, normalized_format)
    if normalized_format == FOOTER_PHONE_FORMAT_TOLL_FREE_0800:
        if len(digits) == FOOTER_PHONE_DIGITS_COUNT and digits.startswith("0800"):
            return _format_footer_phone_0800_from_digits(digits)
        return str(value or "").strip()
    if len(digits) == FOOTER_PHONE_DIGITS_COUNT:
        return _format_footer_phone_mobile_from_digits(digits)
    return str(value or "").strip()


def _normalize_phone_format(phone_format: str) -> str:
    normalized = str(phone_format or "").strip().lower()
    if normalized == FOOTER_PHONE_FORMAT_TOLL_FREE_0800:
        return FOOTER_PHONE_FORMAT_TOLL_FREE_0800
    return FOOTER_PHONE_FORMAT_MOBILE


def _normalize_footer_phone_digits(value: str, phone_format: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if not digits:
        return ""
    if phone_format == FOOTER_PHONE_FORMAT_TOLL_FREE_0800:
        return _normalize_0800_digits(digits)
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


def _normalize_0800_digits(digits: str) -> str:
    if digits.startswith("380800"):
        return f"0{digits[3:]}"[:FOOTER_PHONE_DIGITS_COUNT]
    if digits.startswith("800"):
        return f"0{digits}"[:FOOTER_PHONE_DIGITS_COUNT]
    if digits.startswith("0800"):
        return digits[:FOOTER_PHONE_DIGITS_COUNT]
    if len(digits) >= 6:
        return f"0800{digits[-6:]}"[:FOOTER_PHONE_DIGITS_COUNT]
    return f"0800{digits}"[:FOOTER_PHONE_DIGITS_COUNT]


def _format_footer_phone_mobile_from_digits(digits: str) -> str:
    operator = digits[:3]
    left = digits[3:6]
    middle = digits[6:8]
    right = digits[8:10]
    return f"38 ({operator}) {left}-{middle}-{right}"


def _format_footer_phone_0800_from_digits(digits: str) -> str:
    return f"{digits[0]} ({digits[1:4]}) {digits[4:7]}-{digits[7:10]}"
