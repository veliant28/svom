from __future__ import annotations

from pathlib import Path

from django.utils import timezone

from apps.supplier_imports.models import SupplierPriceList
from apps.supplier_imports.services.import_runner import SupplierImportRunner
from apps.supplier_imports.services.integrations.exceptions import SupplierIntegrationError

from .diagnostics import get_price_list_for_source, resolve_source_and_integration, serialize_with_cooldown


def import_price_list_to_raw(service, *, supplier_code: str, price_list_id: str) -> dict:
    source, integration = resolve_source_and_integration(supplier_code=supplier_code)
    row = get_price_list_for_source(price_list_id=price_list_id, source_id=str(source.id))

    if row.status not in {
        SupplierPriceList.STATUS_DOWNLOADED,
        SupplierPriceList.STATUS_IMPORTED,
    }:
        raise SupplierIntegrationError("Сначала скачайте прайс, затем запускайте импорт в таблицу товаров.")

    if not row.downloaded_file_path:
        raise SupplierIntegrationError("У прайса отсутствует путь к скачанному файлу.")

    file_path = Path(row.downloaded_file_path)
    if not file_path.exists() or not file_path.is_file():
        raise SupplierIntegrationError("Скачанный файл прайса не найден на диске.")
    if file_path.suffix.lower() != ".xlsx":
        raise SupplierIntegrationError("Разрешен импорт только XLSX-прайса.")

    result = SupplierImportRunner().run_source(
        source=source,
        trigger="backoffice:price_list_import_raw_table",
        dry_run=False,
        file_paths=[str(file_path)],
        reprice=False,
        reindex=False,
    )

    now = timezone.now()
    row.status = SupplierPriceList.STATUS_IMPORTED
    row.imported_at = now
    row.imported_run_id = result.run_id
    row.last_error_at = None
    row.last_error_message = ""
    row.save(
        update_fields=(
            "status",
            "imported_at",
            "imported_run",
            "last_error_at",
            "last_error_message",
            "updated_at",
        )
    )

    return {
        "mode": "sync",
        "run_id": result.run_id,
        "status": result.status,
        "result": result.summary,
        "price_list": serialize_with_cooldown(service, integration=integration, row=row),
    }
