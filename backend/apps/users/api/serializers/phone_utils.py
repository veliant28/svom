from __future__ import annotations

import re

from rest_framework import serializers

PHONE_FORMAT_REGEX = re.compile(r"^38\(0\d{2}\)\d{3}-\d{2}-\d{2}$")


def normalize_profile_phone(value: str) -> str:
    normalized_value = value.strip()
    compact_value = re.sub(r"\s+", "", normalized_value)
    if compact_value.startswith("+"):
        compact_value = compact_value[1:]
    if compact_value and not PHONE_FORMAT_REGEX.fullmatch(compact_value):
        raise serializers.ValidationError("Phone must match format 38(0XX)XXX-XX-XX.")
    return compact_value
