from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.supplier_imports.models import SupplierPriceList
from apps.supplier_imports.services.integrations.exceptions import SupplierIntegrationError

from ..analyzers import extract_file_metadata, resolve_extension, resolve_source_file_path
from ..gateway import hydrate_utr_remote_fields
from ..status import generation_wait_seconds
from .diagnostics import get_price_list_for_source, resolve_source_and_integration, serialize_with_cooldown
from .state_sync import refresh_generating_state


def download_price_list(service, *, supplier_code: str, price_list_id: str) -> dict:
    source, integration = resolve_source_and_integration(supplier_code=supplier_code)
    row = get_price_list_for_source(price_list_id=price_list_id, source_id=str(source.id))

    refresh_generating_state(service, row=row, supplier_code=supplier_code, integration=integration)
    if row.status == SupplierPriceList.STATUS_GENERATING:
        wait_seconds = generation_wait_seconds(expected_ready_at=row.expected_ready_at)
        raise SupplierIntegrationError(
            f"Прайс еще формируется. Повторите скачивание через {wait_seconds} сек."
        )
    if row.status == SupplierPriceList.STATUS_FAILED:
        raise SupplierIntegrationError("Прайс находится в статусе ошибки. Выполните новый запрос.")
    if (row.requested_format or "").strip().lower() not in {"", "xlsx"}:
        raise SupplierIntegrationError("Разрешено скачивание только прайсов в формате XLSX.")

    target_dir = Path(settings.MEDIA_ROOT) / "supplier_price_lists" / supplier_code
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    target_file: Path

    if row.request_mode == "utr_api" and row.remote_id and integration.access_token:
        file_ext = resolve_extension(
            requested_format=row.requested_format,
            source_file_name=row.source_file_name,
        )
        if file_ext.lower() != "xlsx":
            file_ext = "xlsx"
        target_file = target_dir / f"{supplier_code}_price_{timestamp}_{str(row.id)[:8]}.{file_ext}"
        hydrate_utr_remote_fields(service, row=row, access_token=integration.access_token)
        if not row.remote_token:
            raise SupplierIntegrationError("UTR еще не выдал export token для скачивания прайса.")
        body, content_type = service.utr_client.download_pricelist(
            access_token=integration.access_token,
            export_token=row.remote_token,
        )
        if body:
            target_file.write_bytes(body)
        else:
            raise SupplierIntegrationError("UTR вернул пустой файл прайса.")
        if target_file.suffix.lower() != ".xlsx":
            corrected = target_file.with_suffix(".xlsx")
            target_file.rename(corrected)
            target_file = corrected
        if row.requested_format == "" and content_type:
            guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
            if guessed and guessed != target_file.suffix:
                corrected = target_file.with_suffix(guessed)
                target_file.rename(corrected)
                target_file = corrected
        if target_file.suffix.lower() != ".xlsx":
            raise SupplierIntegrationError("UTR вернул не-XLSX файл. Разрешен только XLSX.")
    else:
        source_file = Path(row.source_file_path) if row.source_file_path else None
        if source_file is None or not source_file.exists() or source_file.suffix.lower() != ".xlsx":
            source_file = resolve_source_file_path(source.input_path, preferred_extension="xlsx")
        if not source_file or not source_file.exists():
            raise SupplierIntegrationError("Не найден локальный файл прайса для скачивания.")
        if source_file.suffix.lower() != ".xlsx":
            raise SupplierIntegrationError("Локальный прайс должен быть в формате XLSX.")
        file_ext = "xlsx"
        target_file = target_dir / f"{supplier_code}_price_{timestamp}_{str(row.id)[:8]}.{file_ext}"
        shutil.copy2(source_file, target_file)

    downloaded_meta = extract_file_metadata(source_file=target_file, supplier_code=supplier_code)
    now = timezone.now()
    row.downloaded_file_path = str(target_file)
    row.source_file_name = downloaded_meta.file_name
    row.file_size_label = downloaded_meta.file_size_label
    row.file_size_bytes = downloaded_meta.file_size_bytes
    row.warehouse_columns = downloaded_meta.warehouse_columns
    row.price_columns = downloaded_meta.price_columns
    row.row_count = downloaded_meta.row_count
    row.downloaded_at = now
    row.generated_at = row.generated_at or now
    row.status = SupplierPriceList.STATUS_DOWNLOADED
    row.last_error_at = None
    row.last_error_message = ""
    row.save(
        update_fields=(
            "downloaded_file_path",
            "source_file_name",
            "file_size_label",
            "file_size_bytes",
            "warehouse_columns",
            "price_columns",
            "row_count",
            "downloaded_at",
            "generated_at",
            "status",
            "last_error_at",
            "last_error_message",
            "updated_at",
        )
    )

    return serialize_with_cooldown(service, integration=integration, row=row)
