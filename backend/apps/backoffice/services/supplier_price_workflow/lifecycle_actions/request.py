from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from django.utils import timezone

from apps.supplier_imports.models import SupplierPriceList
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierIntegrationError

from ..analyzers import extract_file_metadata, resolve_source_file_path
from ..gateway import enrich_request_params_from_gpl, enrich_request_params_from_utr, sync_utr_remote_price_lists
from ..serialization import serialize_price_list
from ..status import is_ready_status, normalize_status_value
from .diagnostics import resolve_source_and_integration
from .state_sync import refresh_generating_state


def list_price_lists(service, *, supplier_code: str) -> list[dict]:
    source, integration = resolve_source_and_integration(supplier_code=supplier_code)
    cooldown = service.guard.get_status(integration=integration)

    if supplier_code == "utr" and integration.access_token:
        sync_utr_remote_price_lists(service, source=source, integration=integration)

    rows = (
        SupplierPriceList.objects.select_related("imported_run")
        .filter(source=source)
        .order_by("-created_at")
    )

    payload: list[dict] = []
    for row in rows:
        refresh_generating_state(service, row=row, supplier_code=supplier_code, integration=integration)
        payload.append(serialize_price_list(row=row, cooldown_wait_seconds=cooldown.wait_seconds))
    return payload


def get_request_params(service, *, supplier_code: str) -> dict[str, Any]:
    source, integration = resolve_source_and_integration(supplier_code=supplier_code)
    source_file = resolve_source_file_path(source.input_path, preferred_extension="xlsx")
    if supplier_code == "gpl" and source_file is None:
        source_file = _resolve_gpl_source_file(source=source)
    file_meta = extract_file_metadata(source_file=source_file, supplier_code=supplier_code)

    default_formats = ["xlsx"]
    payload: dict[str, Any] = {
        "supplier_code": supplier_code,
        "source": "fallback",
        "formats": default_formats,
        "format_options": [{"format": item, "caption": item} for item in default_formats],
        "supports": {
            "in_stock": supplier_code == "utr",
            "show_scancode": supplier_code == "utr",
            "utr_article": supplier_code == "utr",
        },
        "filter_rule": "one_of_three" if supplier_code == "utr" else "none",
        "defaults": {
            "format": "xlsx",
            "in_stock": True,
            "show_scancode": False,
            "utr_article": supplier_code == "utr",
        },
        "visible_brands_count": 0,
        "categories_count": 0,
        "models_count": 0,
        "visible_brands_truncated": False,
        "categories_truncated": False,
        "models_truncated": False,
        "visible_brands": [],
        "categories": [],
        "models": [],
        "visible_brands_preview": [],
        "categories_preview": [],
        "models_preview": [],
        "price_columns": file_meta.price_columns,
        "warehouse_columns": file_meta.warehouse_columns,
        "last_error_message": "",
    }

    if supplier_code == "utr" and integration.access_token:
        enrich_request_params_from_utr(service, integration=integration, payload=payload, default_formats=default_formats)

    if supplier_code == "gpl" and integration.access_token:
        enrich_request_params_from_gpl(service, integration=integration, payload=payload, file_meta=file_meta)

    return payload


def request_price_list(
    service,
    *,
    supplier_code: str,
    requested_format: str,
    in_stock: bool,
    show_scancode: bool,
    utr_article: bool,
    visible_brands: list[int] | None = None,
    categories: list[str] | None = None,
    models_filter: list[str] | None = None,
) -> dict:
    source, integration = resolve_source_and_integration(supplier_code=supplier_code)
    if not integration.is_enabled:
        raise SupplierIntegrationError("Интеграция поставщика отключена.")

    normalized_format = "xlsx"
    if requested_format.strip().lower() not in {"", "xlsx"}:
        raise SupplierIntegrationError("Разрешен только формат XLSX.")

    if supplier_code == "utr":
        service.guard.acquire_or_raise(integration_id=str(integration.id), action_key="price_request")
        if not integration.access_token:
            raise SupplierIntegrationError("UTR access token отсутствует. Выполните проверку/обновление токена.")

    now = timezone.now()
    source_file = resolve_source_file_path(source.input_path, preferred_extension="xlsx")
    if supplier_code == "gpl":
        source_file = _resolve_gpl_source_file(source=source)
    if supplier_code == "gpl" and source_file is None:
        raise SupplierIntegrationError("Для GPL источник прайса должен быть XLSX-файлом.")
    if supplier_code == "gpl" and source_file is not None:
        resolved_path = str(source_file)
        if (source.input_path or "").strip() != resolved_path:
            source.input_path = resolved_path
            source.save(update_fields=("input_path", "updated_at"))
    metadata = extract_file_metadata(source_file=source_file, supplier_code=supplier_code)

    request_payload = {
        "format": normalized_format,
        "inStock": bool(in_stock),
        "showScancode": bool(show_scancode),
        "utrArticle": bool(utr_article),
        "visibleBrandsId": visible_brands or [],
        "categoriesId": categories or [],
        "modelsId": models_filter or [],
    }

    if supplier_code == "utr":
        selected_filters_count = int(bool(visible_brands)) + int(bool(categories)) + int(bool(models_filter))
        if selected_filters_count > 1:
            raise SupplierIntegrationError(
                "UTR допускает только один тип фильтра за запрос: бренды, категории или модели."
            )

    status = SupplierPriceList.STATUS_READY if supplier_code == "gpl" else SupplierPriceList.STATUS_GENERATING
    request_mode = "local"
    remote_id = ""
    remote_status = ""
    remote_token = ""
    original_format = normalized_format
    locale = ""
    expected_ready_at = None
    generated_at = None
    response_payload: dict[str, Any] = {}
    last_error_message = ""
    last_error_at = None

    if supplier_code == "utr":
        expected_ready_at = now + timedelta(seconds=service.UTR_EXPECTED_GENERATION_SECONDS)
        try:
            api_payload = service.utr_client.request_pricelist_export(
                access_token=integration.access_token,
                payload=request_payload,
            )
            response_payload = api_payload
            request_mode = "utr_api"
            remote_id = str(api_payload.get("id", "")).strip()
            remote_status = normalize_status_value(api_payload.get("status", ""))
            original_format = str(api_payload.get("originalFormat", normalized_format)).strip() or normalized_format
            locale = str(api_payload.get("locale", "")).strip()
            remote_token = str(api_payload.get("token", "")).strip()
            if original_format.lower() != "xlsx":
                raise SupplierIntegrationError("UTR вернул не-XLSX прайс. Разрешен только XLSX.")
            if is_ready_status(remote_status):
                status = SupplierPriceList.STATUS_READY
                generated_at = now
                expected_ready_at = now
            else:
                status = SupplierPriceList.STATUS_GENERATING
        except SupplierClientError as exc:
            raise SupplierIntegrationError(str(exc)) from exc
    else:
        generated_at = now
        expected_ready_at = now

    created = SupplierPriceList.objects.create(
        supplier=source.supplier,
        source=source,
        integration=integration,
        status=status,
        request_mode=request_mode,
        remote_id=remote_id,
        remote_token=remote_token,
        remote_status=remote_status,
        requested_format=normalized_format,
        original_format=original_format,
        locale=locale,
        is_in_stock=bool(in_stock),
        show_scancode=bool(show_scancode),
        utr_article=bool(utr_article),
        visible_brands=visible_brands or [],
        categories=categories or [],
        models_filter=models_filter or [],
        source_file_name=metadata.file_name,
        source_file_path=metadata.file_path,
        file_size_label=metadata.file_size_label,
        file_size_bytes=metadata.file_size_bytes,
        warehouse_columns=metadata.warehouse_columns,
        price_columns=metadata.price_columns,
        row_count=metadata.row_count,
        requested_at=now,
        expected_ready_at=expected_ready_at,
        generated_at=generated_at,
        request_payload=request_payload,
        response_payload=response_payload,
        last_error_at=last_error_at,
        last_error_message=last_error_message,
    )

    cooldown = service.guard.get_status(integration=integration)
    return serialize_price_list(row=created, cooldown_wait_seconds=cooldown.wait_seconds)


def _resolve_gpl_source_file(*, source) -> Path | None:
    primary = resolve_source_file_path(source.input_path, preferred_extension="xlsx")
    if primary is not None:
        return primary

    historical_rows = (
        SupplierPriceList.objects.filter(source=source)
        .order_by("-created_at")
        .only("downloaded_file_path", "source_file_path")[:50]
    )
    for row in historical_rows:
        for raw_path in (row.downloaded_file_path, row.source_file_path):
            candidate = resolve_source_file_path(str(raw_path or ""), preferred_extension="xlsx")
            if candidate is not None:
                return candidate
    return None
