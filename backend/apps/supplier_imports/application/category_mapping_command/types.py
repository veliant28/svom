from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CategoryMappingCommandOptions:
    supplier_codes: tuple[str, ...]
    batch_size: int
    limit: int | None
    dry_run: bool
    overwrite_manual: bool
    force_map_all: bool
    recheck_risky_mappings: bool
    recheck_guardrail_codes: tuple[str, ...]
    recheck_reasons: tuple[str, ...]
    recheck_category_names: tuple[str, ...]
    recheck_title_patterns: tuple[str, ...]

    @property
    def has_selective_guardrail_recheck(self) -> bool:
        return bool(
            self.recheck_guardrail_codes
            or self.recheck_reasons
            or self.recheck_category_names
            or self.recheck_title_patterns
        )


@dataclass(frozen=True)
class CommandOutput:
    write: Callable[[str], None]
    success: Callable[[str], str]
    warning: Callable[[str], str]

    def write_success(self, message: str) -> None:
        self.write(self.success(message))

    def write_warning(self, message: str) -> None:
        self.write(self.warning(message))
