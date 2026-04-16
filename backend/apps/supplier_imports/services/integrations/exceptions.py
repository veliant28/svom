from __future__ import annotations


class SupplierIntegrationError(Exception):
    pass


class SupplierCooldownError(SupplierIntegrationError):
    def __init__(self, *, retry_after_seconds: int):
        self.retry_after_seconds = max(int(retry_after_seconds), 1)
        super().__init__(f"Слишком рано. Следующий запрос можно выполнить через {self.retry_after_seconds} сек.")


class SupplierClientError(SupplierIntegrationError):
    def __init__(self, message: str, *, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)
