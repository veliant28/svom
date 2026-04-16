from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True)
class CronExpression:
    minute: set[int]
    hour: set[int]
    day: set[int]
    month: set[int]
    weekday: set[int]

    @classmethod
    def parse(cls, expression: str) -> "CronExpression":
        parts = expression.split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 fields.")

        minute = _parse_field(parts[0], minimum=0, maximum=59)
        hour = _parse_field(parts[1], minimum=0, maximum=23)
        day = _parse_field(parts[2], minimum=1, maximum=31)
        month = _parse_field(parts[3], minimum=1, maximum=12)
        weekday = _parse_field(parts[4], minimum=0, maximum=7, remap_weekday=True)
        return cls(minute=minute, hour=hour, day=day, month=month, weekday=weekday)

    def matches(self, value: datetime) -> bool:
        cron_weekday = (value.weekday() + 1) % 7
        return (
            value.minute in self.minute
            and value.hour in self.hour
            and value.day in self.day
            and value.month in self.month
            and cron_weekday in self.weekday
        )


def compute_next_run(*, cron_expression: str, timezone_name: str, now: datetime | None = None) -> datetime | None:
    if not cron_expression:
        return None
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None

    try:
        cron = CronExpression.parse(cron_expression)
    except ValueError:
        return None

    current = (now or datetime.now(tz=timezone)).astimezone(timezone).replace(second=0, microsecond=0)
    probe = current + timedelta(minutes=1)
    horizon = probe + timedelta(days=60)
    while probe <= horizon:
        if cron.matches(probe):
            return probe.astimezone(timezone)
        probe += timedelta(minutes=1)

    return None


def _parse_field(raw: str, *, minimum: int, maximum: int, remap_weekday: bool = False) -> set[int]:
    values: set[int] = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.update(_parse_chunk(chunk, minimum=minimum, maximum=maximum, remap_weekday=remap_weekday))

    if not values:
        raise ValueError("Empty cron field.")
    return values


def _parse_chunk(raw: str, *, minimum: int, maximum: int, remap_weekday: bool) -> set[int]:
    if raw == "*":
        return set(range(minimum, maximum + 1))

    step = 1
    base = raw
    if "/" in raw:
        base, step_raw = raw.split("/", maxsplit=1)
        try:
            step = int(step_raw)
        except ValueError as error:
            raise ValueError("Invalid cron step.") from error
        if step <= 0:
            raise ValueError("Cron step should be positive.")

    if base == "*":
        start, end = minimum, maximum
    elif "-" in base:
        start_raw, end_raw = base.split("-", maxsplit=1)
        start = int(start_raw)
        end = int(end_raw)
    else:
        start = int(base)
        end = start

    if start < minimum or end > maximum or start > end:
        raise ValueError("Cron field out of range.")

    values = set(range(start, end + 1, step))
    if remap_weekday and 7 in values:
        values.remove(7)
        values.add(0)
    return values
