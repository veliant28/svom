from __future__ import annotations

from django.utils import timezone

from apps.supplier_imports.models import ImportSource, SupplierIntegration
from apps.supplier_imports.selectors import get_supplier_integration_for_source


class SupplierIntegrationStateService:
    def get_for_source(self, *, source: ImportSource) -> SupplierIntegration:
        return get_supplier_integration_for_source(source=source)

    def mark_import_success(self, *, integration: SupplierIntegration) -> None:
        integration.last_successful_import_at = timezone.now()
        integration.last_import_error_message = ""
        integration.save(update_fields=("last_successful_import_at", "last_import_error_message", "updated_at"))

    def mark_import_failure(self, *, integration: SupplierIntegration, message: str) -> None:
        integration.last_failed_import_at = timezone.now()
        integration.last_import_error_message = message[:2000]
        integration.save(update_fields=("last_failed_import_at", "last_import_error_message", "updated_at"))

    def mark_connection_status(self, *, integration: SupplierIntegration, status: str) -> None:
        integration.last_connection_check_at = timezone.now()
        integration.last_connection_status = status[:32]
        integration.save(update_fields=("last_connection_check_at", "last_connection_status", "updated_at"))

    def mark_brands_import_success(self, *, integration: SupplierIntegration, imported_count: int) -> None:
        integration.last_brands_import_at = timezone.now()
        integration.last_brands_import_count = max(int(imported_count), 0)
        integration.last_brands_import_error_at = None
        integration.last_brands_import_error_message = ""
        integration.save(
            update_fields=(
                "last_brands_import_at",
                "last_brands_import_count",
                "last_brands_import_error_at",
                "last_brands_import_error_message",
                "updated_at",
            )
        )

    def mark_brands_import_failure(self, *, integration: SupplierIntegration, message: str) -> None:
        integration.last_brands_import_error_at = timezone.now()
        integration.last_brands_import_error_message = message[:2000]
        integration.save(update_fields=("last_brands_import_error_at", "last_brands_import_error_message", "updated_at"))
