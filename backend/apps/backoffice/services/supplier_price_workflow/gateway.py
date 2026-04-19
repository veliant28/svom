from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.supplier_imports.models import SupplierPriceList
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError

from .analyzers import detect_price_columns, detect_warehouse_columns
from .status import is_failed_status, is_ready_status, normalize_status_value
from .types import FileMetadata


def sync_utr_remote_price_lists(service, *, source, integration) -> None:
    try:
        remote_items = service.utr_client.list_pricelists(access_token=integration.access_token)
    except SupplierClientError:
        return

    for item in remote_items:
        if not isinstance(item, dict):
            continue

        remote_id = str(item.get("id", "")).strip()
        if not remote_id:
            continue

        remote_status = normalize_status_value(item.get("status", ""))
        next_status = SupplierPriceList.STATUS_GENERATING
        if is_ready_status(remote_status):
            next_status = SupplierPriceList.STATUS_READY
        elif is_failed_status(remote_status):
            next_status = SupplierPriceList.STATUS_FAILED

        requested_at = parse_datetime(str(item.get("createdAt", "")).strip() or "") or None
        finished_at = parse_datetime(str(item.get("finishedAt", "")).strip() or "") or None
        expected_ready_at = requested_at + timedelta(seconds=service.UTR_EXPECTED_GENERATION_SECONDS) if requested_at else None
        generated_at = finished_at if is_ready_status(remote_status) else None

        requested_format = str(item.get("format", "")).strip()
        original_format = str(item.get("originalFormat", "")).strip() or requested_format
        remote_token = str(item.get("token", "")).strip()
        locale = str(item.get("locale", "")).strip()
        file_size_label = str(item.get("fileSize", "")).strip()
        size_raw = item.get("size")
        if isinstance(size_raw, int):
            file_size_bytes = size_raw
        elif isinstance(size_raw, str) and size_raw.isdigit():
            file_size_bytes = int(size_raw)
        else:
            file_size_bytes = 0

        visible_brands = [str(value) for value in (item.get("visibleBrands", []) or [])]
        categories = [str(value) for value in (item.get("categories", []) or [])]
        models_filter = [str(value) for value in (item.get("models", []) or [])]

        row = SupplierPriceList.objects.filter(source=source, remote_id=remote_id).first()
        if row is None:
            SupplierPriceList.objects.create(
                supplier=source.supplier,
                source=source,
                integration=integration,
                status=next_status,
                request_mode="utr_api",
                remote_id=remote_id,
                remote_token=remote_token,
                remote_status=remote_status,
                requested_format=requested_format,
                original_format=original_format,
                locale=locale,
                is_in_stock=bool(item.get("isInStock", True)),
                show_scancode=bool(item.get("showScancode", False)),
                utr_article=bool(item.get("utrArticle", False)),
                visible_brands=visible_brands,
                categories=categories,
                models_filter=models_filter,
                file_size_label=file_size_label,
                file_size_bytes=file_size_bytes,
                requested_at=requested_at,
                expected_ready_at=expected_ready_at,
                generated_at=generated_at,
                response_payload=item,
            )
            continue

        changed_fields: set[str] = set()
        if row.request_mode != "utr_api":
            row.request_mode = "utr_api"
            changed_fields.add("request_mode")
        if row.integration_id != integration.id:
            row.integration = integration
            changed_fields.add("integration")
        if row.remote_token != remote_token:
            row.remote_token = remote_token
            changed_fields.add("remote_token")
        if row.remote_status != remote_status:
            row.remote_status = remote_status
            changed_fields.add("remote_status")
        if row.requested_format != requested_format:
            row.requested_format = requested_format
            changed_fields.add("requested_format")
        if row.original_format != original_format:
            row.original_format = original_format
            changed_fields.add("original_format")
        if row.locale != locale:
            row.locale = locale
            changed_fields.add("locale")
        if row.is_in_stock != bool(item.get("isInStock", True)):
            row.is_in_stock = bool(item.get("isInStock", True))
            changed_fields.add("is_in_stock")
        if row.show_scancode != bool(item.get("showScancode", False)):
            row.show_scancode = bool(item.get("showScancode", False))
            changed_fields.add("show_scancode")
        if row.utr_article != bool(item.get("utrArticle", False)):
            row.utr_article = bool(item.get("utrArticle", False))
            changed_fields.add("utr_article")
        if row.visible_brands != visible_brands:
            row.visible_brands = visible_brands
            changed_fields.add("visible_brands")
        if row.categories != categories:
            row.categories = categories
            changed_fields.add("categories")
        if row.models_filter != models_filter:
            row.models_filter = models_filter
            changed_fields.add("models_filter")
        if row.file_size_label != file_size_label:
            row.file_size_label = file_size_label
            changed_fields.add("file_size_label")
        if row.file_size_bytes != file_size_bytes:
            row.file_size_bytes = file_size_bytes
            changed_fields.add("file_size_bytes")
        if requested_at and row.requested_at != requested_at:
            row.requested_at = requested_at
            changed_fields.add("requested_at")
        if expected_ready_at and row.expected_ready_at != expected_ready_at:
            row.expected_ready_at = expected_ready_at
            changed_fields.add("expected_ready_at")
        if generated_at and row.generated_at != generated_at:
            row.generated_at = generated_at
            changed_fields.add("generated_at")
        if row.response_payload != item:
            row.response_payload = item
            changed_fields.add("response_payload")

        if row.status not in {SupplierPriceList.STATUS_DOWNLOADED, SupplierPriceList.STATUS_IMPORTED}:
            if row.status != next_status:
                row.status = next_status
                changed_fields.add("status")

        if changed_fields:
            row.save(update_fields=tuple(sorted({*changed_fields, "updated_at"})))


def enrich_request_params_from_utr(
    service,
    *,
    integration,
    payload: dict[str, Any],
    default_formats: list[str],
) -> None:
    try:
        api_payload = service.utr_client.get_pricelist_export_params(access_token=integration.access_token)
        formats = [str(item).strip() for item in api_payload.get("supportedFormats", []) if str(item).strip()]
        format_options = [
            {
                "format": str(item.get("format", "")).strip(),
                "caption": str(item.get("caption", "")).strip(),
            }
            for item in (api_payload.get("supportedFormatsExt", []) or [])
            if isinstance(item, dict) and str(item.get("format", "")).strip()
        ]

        visible_brands_raw = [item for item in (api_payload.get("visibleBrands", []) or []) if isinstance(item, dict)]
        categories_raw = [item for item in (api_payload.get("categories", []) or []) if isinstance(item, dict)]
        models_raw = [item for item in (api_payload.get("models", []) or [])]

        visible_brands_values = [
            {
                "id": item.get("id"),
                "title": item.get("title") or item.get("name") or "",
            }
            for item in visible_brands_raw
        ]
        categories_values = [
            {
                "id": str(item.get("id", "")).strip(),
                "title": item.get("title") or item.get("name") or "",
                "quantity": str(item.get("quantity", "")).strip(),
            }
            for item in categories_raw
        ]
        models_values = [
            {
                "name": str(item.get("name", "")).strip() if isinstance(item, dict) else str(item).strip(),
            }
            for item in models_raw
        ]

        payload.update(
            {
                "source": "utr_api",
                "formats": formats or default_formats,
                "format_options": format_options or [{"format": item, "caption": item} for item in (formats or default_formats)],
                "visible_brands_count": len(visible_brands_values),
                "categories_count": len(categories_values),
                "models_count": len(models_values),
                "visible_brands_truncated": len(visible_brands_values) > service.PARAM_OPTIONS_LIMIT,
                "categories_truncated": len(categories_values) > service.PARAM_OPTIONS_LIMIT,
                "models_truncated": len(models_values) > service.PARAM_OPTIONS_LIMIT,
                "visible_brands": visible_brands_values[: service.PARAM_OPTIONS_LIMIT],
                "categories": categories_values[: service.PARAM_OPTIONS_LIMIT],
                "models": models_values[: service.PARAM_OPTIONS_LIMIT],
                "visible_brands_preview": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title") or item.get("name") or "",
                    }
                    for item in visible_brands_values[:24]
                ],
                "categories_preview": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                    }
                    for item in categories_values[:24]
                ],
                "models_preview": [
                    {
                        "name": item.get("name"),
                    }
                    for item in models_values[:24]
                    if item.get("name")
                ],
            }
        )
    except SupplierClientError as exc:
        payload["last_error_message"] = str(exc)


def enrich_request_params_from_gpl(
    service,
    *,
    integration,
    payload: dict[str, Any],
    file_meta: FileMetadata,
) -> None:
    try:
        page_payload = service.gpl_client.fetch_prices_page(access_token=integration.access_token, page=1)
        titles = page_payload.get("data", {}).get("titles", {})
        if isinstance(titles, dict):
            title_keys = [str(key) for key in titles.keys()]
            detected_prices = detect_price_columns(headers=title_keys)
            payload.update(
                {
                    "source": "gpl_api",
                    "price_columns": detected_prices or file_meta.price_columns,
                    "warehouse_columns": detect_warehouse_columns(
                        headers=title_keys,
                        supplier_code="gpl",
                        price_columns=detected_prices,
                    )
                    or file_meta.warehouse_columns,
                }
            )
    except SupplierClientError as exc:
        payload["last_error_message"] = str(exc)


def hydrate_utr_remote_fields(service, *, row: SupplierPriceList, access_token: str) -> None:
    if row.remote_token:
        return
    if not row.remote_id:
        return

    try:
        price_lists = service.utr_client.list_pricelists(access_token=access_token)
    except SupplierClientError:
        return

    for item in price_lists:
        item_id = str(item.get("id", "")).strip()
        if item_id != row.remote_id:
            continue

        row.remote_token = str(item.get("token", "")).strip()
        remote_status = normalize_status_value(item.get("status", ""))
        if remote_status:
            row.remote_status = remote_status
        row.file_size_label = str(item.get("fileSize", row.file_size_label)).strip()
        size = item.get("size")
        if isinstance(size, int):
            row.file_size_bytes = size
        elif isinstance(size, str) and size.isdigit():
            row.file_size_bytes = int(size)
        if is_ready_status(row.remote_status):
            row.status = SupplierPriceList.STATUS_READY
            row.generated_at = row.generated_at or timezone.now()
        row.save(
            update_fields=(
                "remote_token",
                "remote_status",
                "file_size_label",
                "file_size_bytes",
                "status",
                "generated_at",
                "updated_at",
            )
        )
        return
