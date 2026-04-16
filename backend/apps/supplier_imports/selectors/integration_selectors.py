from __future__ import annotations

from apps.supplier_imports.models import ImportSource, SupplierIntegration
from apps.supplier_imports.selectors.import_source_selectors import ensure_default_import_sources, get_import_source_by_code


def get_supplier_integration_by_code(*, source_code: str) -> SupplierIntegration:
    ensure_default_import_sources()
    source = get_import_source_by_code(source_code)
    integration, _ = SupplierIntegration.objects.get_or_create(
        supplier=source.supplier,
        defaults={
            "source": source,
        },
    )
    if integration.source_id != source.id:
        integration.source = source
        integration.save(update_fields=("source", "updated_at"))
    return integration


def get_supplier_integration_for_source(*, source: ImportSource) -> SupplierIntegration:
    integration, _ = SupplierIntegration.objects.get_or_create(
        supplier=source.supplier,
        defaults={
            "source": source,
        },
    )
    if integration.source_id != source.id:
        integration.source = source
        integration.save(update_fields=("source", "updated_at"))
    return integration
