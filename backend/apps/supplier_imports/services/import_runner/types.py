from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImportExecutionResult:
    run_id: str
    source_code: str
    status: str
    summary: dict[str, int | str | dict]
