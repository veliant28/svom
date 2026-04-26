from __future__ import annotations

from celery import shared_task

from apps.supplier_imports.services.price_list_file_cleanup import SupplierPriceListFileCleanupService


@shared_task(name="supplier_imports.cleanup_price_list_files")
def cleanup_price_list_files_task() -> dict:
    return SupplierPriceListFileCleanupService().cleanup().as_dict()
