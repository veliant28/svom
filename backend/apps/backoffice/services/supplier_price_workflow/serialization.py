from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.supplier_imports.models import SupplierPriceList


def serialize_price_list(*, row: SupplierPriceList, cooldown_wait_seconds: int) -> dict[str, Any]:
    generation_wait_seconds = 0
    if row.status == SupplierPriceList.STATUS_GENERATING and row.expected_ready_at:
        generation_wait_seconds = max(int((row.expected_ready_at - timezone.now()).total_seconds()), 0)

    download_available = row.status in {
        SupplierPriceList.STATUS_READY,
        SupplierPriceList.STATUS_DOWNLOADED,
        SupplierPriceList.STATUS_IMPORTED,
    }
    has_downloaded_file = bool(row.downloaded_file_path)
    import_available = has_downloaded_file and row.status in {
        SupplierPriceList.STATUS_DOWNLOADED,
        SupplierPriceList.STATUS_IMPORTED,
    }

    return {
        "id": str(row.id),
        "supplier_code": row.source.code,
        "supplier_name": row.supplier.name,
        "status": row.status,
        "remote_status": row.remote_status,
        "request_mode": row.request_mode,
        "requested_at": row.requested_at,
        "expected_ready_at": row.expected_ready_at,
        "generated_at": row.generated_at,
        "downloaded_at": row.downloaded_at,
        "imported_at": row.imported_at,
        "imported_run_id": str(row.imported_run_id) if row.imported_run_id else None,
        "requested_format": row.requested_format,
        "original_format": row.original_format,
        "locale": row.locale,
        "is_in_stock": row.is_in_stock,
        "show_scancode": row.show_scancode,
        "utr_article": row.utr_article,
        "visible_brands": row.visible_brands,
        "categories": row.categories,
        "models_filter": row.models_filter,
        "remote_id": row.remote_id,
        "source_file_name": row.source_file_name,
        "source_file_path": row.source_file_path,
        "downloaded_file_path": row.downloaded_file_path,
        "file_size_label": row.file_size_label,
        "file_size_bytes": row.file_size_bytes,
        "row_count": row.row_count,
        "price_columns": row.price_columns,
        "warehouse_columns": row.warehouse_columns,
        "has_multiple_prices": len(row.price_columns) > 1,
        "has_warehouses": len(row.warehouse_columns) > 0,
        "generation_wait_seconds": generation_wait_seconds,
        "download_available": download_available,
        "import_available": import_available,
        "last_error_at": row.last_error_at,
        "last_error_message": row.last_error_message,
        "cooldown_wait_seconds": cooldown_wait_seconds,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
