from __future__ import annotations

import re

_INTERVAL_PATTERN = re.compile(r"^\s*(\d{2})\.(\d{4})\s*-\s*(?:(\d{2})\.(\d{4}))?\s*$")
_YEAR_INTERVAL_PATTERN = re.compile(r"^\s*(\d{4})\s*-\s*(\d{4})?\s*$")


def parse_construction_interval(value: str | None) -> tuple[int | None, int | None, int | None, int | None]:
    raw = str(value or "").strip()
    if not raw:
        return None, None, None, None

    match = _INTERVAL_PATTERN.match(raw)
    if match:
        start_month = int(match.group(1))
        start_year = int(match.group(2))
        end_month = int(match.group(3)) if match.group(3) else None
        end_year = int(match.group(4)) if match.group(4) else None
        return start_year, start_month, end_year, end_month

    year_match = _YEAR_INTERVAL_PATTERN.match(raw)
    if year_match:
        start_year = int(year_match.group(1))
        end_year = int(year_match.group(2)) if year_match.group(2) else None
        return start_year, None, end_year, None

    return None, None, None, None
