from __future__ import annotations

from typing import Any


class VchasnoKasaError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "VCHASNO_KASA_ERROR",
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = int(status_code)
        self.details = details or {}

    def as_api_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }


class VchasnoKasaConfigError(VchasnoKasaError):
    def __init__(self, message: str, *, code: str = "VCHASNO_KASA_CONFIG_INVALID", details: dict[str, Any] | None = None) -> None:
        super().__init__(message, code=code, status_code=422, details=details)


class VchasnoKasaDisabledError(VchasnoKasaError):
    def __init__(self, message: str = "Вчасно.Каса выключена.") -> None:
        super().__init__(message, code="VCHASNO_KASA_DISABLED", status_code=409)


class VchasnoKasaApiError(VchasnoKasaError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code="VCHASNO_KASA_ERROR", status_code=status_code, details=details)
