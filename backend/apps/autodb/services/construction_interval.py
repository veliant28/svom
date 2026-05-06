from __future__ import annotations

from dataclasses import dataclass

from apps.autodb.services.intervals import parse_construction_interval


@dataclass(frozen=True)
class ParsedConstructionInterval:
    raw_construction_interval: str
    year_from: int | None
    year_to: int | None


def parse_construction_interval_years(value: str | None) -> ParsedConstructionInterval:
    raw = str(value or "").strip()
    year_from, _month_from, year_to, _month_to = parse_construction_interval(raw)
    return ParsedConstructionInterval(
        raw_construction_interval=raw,
        year_from=year_from,
        year_to=year_to,
    )
