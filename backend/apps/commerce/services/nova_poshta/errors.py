from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class NovaPoshtaErrorContext:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)
    warning_codes: list[str] = field(default_factory=list)
    info_codes: list[str] = field(default_factory=list)
    raw_response: dict = field(default_factory=dict)


class NovaPoshtaIntegrationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        context: NovaPoshtaErrorContext | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.context = context or NovaPoshtaErrorContext()


class NovaPoshtaBusinessRuleError(NovaPoshtaIntegrationError):
    pass


def format_context_message(message: str, *, context: NovaPoshtaErrorContext) -> str:
    if context.errors:
        return f"{message} ({'; '.join(context.errors[:2])})"
    if context.warnings:
        return f"{message} ({'; '.join(context.warnings[:2])})"
    return message
