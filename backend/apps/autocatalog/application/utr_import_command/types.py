from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class UtrImportCommandOptions:
    limit: int | None
    offset: int
    resolve_utr_articles: bool
    resolve_limit: int | None
    resolve_offset: int
    resolve_until_empty: bool
    retry_unresolved: bool
    resolve_only: bool
    products_only: bool
    missing_applicability_only: bool
    batch_size: int


@dataclass(frozen=True)
class CommandOutput:
    write: Callable[[str], None]
    success: Callable[[str], str]
    warning: Callable[[str], str]

    def write_success(self, message: str) -> None:
        self.write(self.success(message))

    def write_warning(self, message: str) -> None:
        self.write(self.warning(message))
