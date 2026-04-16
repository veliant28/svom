from __future__ import annotations

import mimetypes
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from apps.backoffice.selectors import get_supplier_source_by_code
from apps.supplier_imports.models import SupplierPriceList
from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows
from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.import_runner import SupplierImportRunner
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierIntegrationError
from apps.supplier_imports.services.integrations.gpl_client import GplClient
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.integrations.utr_client import UtrClient


class SupplierPriceWorkflowService:
    UTR_EXPECTED_GENERATION_SECONDS = 180
    PARAM_OPTIONS_LIMIT = 5000

    def __init__(self):
        self.guard = SupplierRateLimitGuardService()
        self.utr_client = UtrClient()
        self.gpl_client = GplClient()

    def list_price_lists(self, *, supplier_code: str) -> list[dict]:
        source = get_supplier_source_by_code(supplier_code=supplier_code)
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        cooldown = self.guard.get_status(integration=integration)

        if supplier_code == "utr" and integration.access_token:
            self._sync_utr_remote_price_lists(source=source, integration=integration)

        rows = (
            SupplierPriceList.objects.select_related("imported_run")
            .filter(source=source)
            .order_by("-created_at")
        )

        payload: list[dict] = []
        for row in rows:
            self._refresh_generating_state(row=row, supplier_code=supplier_code, integration=integration)
            payload.append(self._serialize_price_list(row=row, cooldown_wait_seconds=cooldown.wait_seconds))
        return payload

    def _sync_utr_remote_price_lists(self, *, source, integration) -> None:
        try:
            remote_items = self.utr_client.list_pricelists(access_token=integration.access_token)
        except SupplierClientError:
            return

        now = timezone.now()
        for item in remote_items:
            if not isinstance(item, dict):
                continue

            remote_id = str(item.get("id", "")).strip()
            if not remote_id:
                continue

            remote_status = self._normalize_status_value(item.get("status", ""))
            next_status = SupplierPriceList.STATUS_GENERATING
            if self._is_ready_status(remote_status):
                next_status = SupplierPriceList.STATUS_READY
            elif self._is_failed_status(remote_status):
                next_status = SupplierPriceList.STATUS_FAILED

            requested_at = parse_datetime(str(item.get("createdAt", "")).strip() or "") or None
            finished_at = parse_datetime(str(item.get("finishedAt", "")).strip() or "") or None
            expected_ready_at = requested_at + timedelta(seconds=self.UTR_EXPECTED_GENERATION_SECONDS) if requested_at else None
            generated_at = finished_at if self._is_ready_status(remote_status) else None

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

    def get_request_params(self, *, supplier_code: str) -> dict[str, Any]:
        source = get_supplier_source_by_code(supplier_code=supplier_code)
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        source_file = self._resolve_source_file_path(source.input_path)
        file_meta = self._extract_file_metadata(source_file=source_file, supplier_code=supplier_code)

        default_formats = ["xlsx", "csv", "txt"] if supplier_code == "utr" else ["xlsx"]
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
            "price_columns": file_meta["price_columns"],
            "warehouse_columns": file_meta["warehouse_columns"],
            "last_error_message": "",
        }

        if supplier_code == "utr" and integration.access_token:
            try:
                api_payload = self.utr_client.get_pricelist_export_params(access_token=integration.access_token)
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
                        "visible_brands_truncated": len(visible_brands_values) > self.PARAM_OPTIONS_LIMIT,
                        "categories_truncated": len(categories_values) > self.PARAM_OPTIONS_LIMIT,
                        "models_truncated": len(models_values) > self.PARAM_OPTIONS_LIMIT,
                        "visible_brands": visible_brands_values[: self.PARAM_OPTIONS_LIMIT],
                        "categories": categories_values[: self.PARAM_OPTIONS_LIMIT],
                        "models": models_values[: self.PARAM_OPTIONS_LIMIT],
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

        if supplier_code == "gpl" and integration.access_token:
            try:
                page_payload = self.gpl_client.fetch_prices_page(access_token=integration.access_token, page=1)
                titles = page_payload.get("data", {}).get("titles", {})
                if isinstance(titles, dict):
                    title_keys = [str(key) for key in titles.keys()]
                    payload.update(
                        {
                            "source": "gpl_api",
                            "price_columns": self._detect_price_columns(headers=title_keys) or file_meta["price_columns"],
                            "warehouse_columns": self._detect_warehouse_columns(
                                headers=title_keys,
                                supplier_code="gpl",
                                price_columns=self._detect_price_columns(headers=title_keys),
                            )
                            or file_meta["warehouse_columns"],
                        }
                    )
            except SupplierClientError as exc:
                payload["last_error_message"] = str(exc)

        return payload

    def request_price_list(
        self,
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
        source = get_supplier_source_by_code(supplier_code=supplier_code)
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        if not integration.is_enabled:
            raise SupplierIntegrationError("Интеграция поставщика отключена.")

        if supplier_code == "utr":
            self.guard.acquire_or_raise(integration_id=str(integration.id), action_key="price_request")

        now = timezone.now()
        source_file = self._resolve_source_file_path(source.input_path)
        metadata = self._extract_file_metadata(source_file=source_file, supplier_code=supplier_code)

        request_payload = {
            "format": requested_format,
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
        original_format = requested_format
        locale = ""
        expected_ready_at = None
        generated_at = None
        response_payload: dict[str, Any] = {}
        last_error_message = ""
        last_error_at = None

        if supplier_code == "utr":
            expected_ready_at = now + timedelta(seconds=self.UTR_EXPECTED_GENERATION_SECONDS)
            if integration.access_token:
                try:
                    api_payload = self.utr_client.request_pricelist_export(
                        access_token=integration.access_token,
                        payload=request_payload,
                    )
                    response_payload = api_payload
                    request_mode = "utr_api"
                    remote_id = str(api_payload.get("id", "")).strip()
                    remote_status = self._normalize_status_value(api_payload.get("status", ""))
                    original_format = str(api_payload.get("originalFormat", requested_format)).strip() or requested_format
                    locale = str(api_payload.get("locale", "")).strip()
                    remote_token = str(api_payload.get("token", "")).strip()
                    if self._is_ready_status(remote_status):
                        status = SupplierPriceList.STATUS_READY
                        generated_at = now
                        expected_ready_at = now
                    else:
                        status = SupplierPriceList.STATUS_GENERATING
                except SupplierClientError as exc:
                    # Keep the operator flow usable with local root files even when remote API is unavailable.
                    last_error_message = str(exc)
                    last_error_at = now
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
            requested_format=requested_format,
            original_format=original_format,
            locale=locale,
            is_in_stock=bool(in_stock),
            show_scancode=bool(show_scancode),
            utr_article=bool(utr_article),
            visible_brands=visible_brands or [],
            categories=categories or [],
            models_filter=models_filter or [],
            source_file_name=metadata["file_name"],
            source_file_path=metadata["file_path"],
            file_size_label=metadata["file_size_label"],
            file_size_bytes=metadata["file_size_bytes"],
            warehouse_columns=metadata["warehouse_columns"],
            price_columns=metadata["price_columns"],
            row_count=metadata["row_count"],
            requested_at=now,
            expected_ready_at=expected_ready_at,
            generated_at=generated_at,
            request_payload=request_payload,
            response_payload=response_payload,
            last_error_at=last_error_at,
            last_error_message=last_error_message,
        )

        cooldown = self.guard.get_status(integration=integration)
        return self._serialize_price_list(row=created, cooldown_wait_seconds=cooldown.wait_seconds)

    def download_price_list(self, *, supplier_code: str, price_list_id: str) -> dict:
        source = get_supplier_source_by_code(supplier_code=supplier_code)
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        row = self._get_price_list(price_list_id=price_list_id, source_id=str(source.id))

        self._refresh_generating_state(row=row, supplier_code=supplier_code, integration=integration)
        if row.status == SupplierPriceList.STATUS_GENERATING:
            wait_seconds = self._generation_wait_seconds(row=row)
            raise SupplierIntegrationError(
                f"Прайс еще формируется. Повторите скачивание через {wait_seconds} сек."
            )
        if row.status == SupplierPriceList.STATUS_FAILED:
            raise SupplierIntegrationError("Прайс находится в статусе ошибки. Выполните новый запрос.")

        target_dir = Path(settings.MEDIA_ROOT) / "supplier_price_lists" / supplier_code
        target_dir.mkdir(parents=True, exist_ok=True)

        file_ext = self._resolve_extension(
            requested_format=row.requested_format,
            source_file_name=row.source_file_name,
        )
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        target_file = target_dir / f"{supplier_code}_price_{timestamp}_{str(row.id)[:8]}.{file_ext}"

        if row.request_mode == "utr_api" and row.remote_id and integration.access_token:
            self._hydrate_utr_remote_fields(row=row, access_token=integration.access_token)
            if not row.remote_token:
                raise SupplierIntegrationError("UTR еще не выдал export token для скачивания прайса.")
            body, content_type = self.utr_client.download_pricelist(
                access_token=integration.access_token,
                export_token=row.remote_token,
            )
            if body:
                target_file.write_bytes(body)
            else:
                raise SupplierIntegrationError("UTR вернул пустой файл прайса.")
            if row.requested_format == "" and content_type:
                guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
                if guessed and guessed != target_file.suffix:
                    corrected = target_file.with_suffix(guessed)
                    target_file.rename(corrected)
                    target_file = corrected
        else:
            source_file = Path(row.source_file_path) if row.source_file_path else self._resolve_source_file_path(source.input_path)
            if not source_file or not source_file.exists():
                raise SupplierIntegrationError("Не найден локальный файл прайса для скачивания.")
            shutil.copy2(source_file, target_file)

        downloaded_meta = self._extract_file_metadata(source_file=target_file, supplier_code=supplier_code)
        now = timezone.now()
        row.downloaded_file_path = str(target_file)
        row.source_file_name = downloaded_meta["file_name"]
        row.file_size_label = downloaded_meta["file_size_label"]
        row.file_size_bytes = downloaded_meta["file_size_bytes"]
        row.warehouse_columns = downloaded_meta["warehouse_columns"]
        row.price_columns = downloaded_meta["price_columns"]
        row.row_count = downloaded_meta["row_count"]
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

        cooldown = self.guard.get_status(integration=integration)
        return self._serialize_price_list(row=row, cooldown_wait_seconds=cooldown.wait_seconds)

    def import_price_list_to_raw(self, *, supplier_code: str, price_list_id: str) -> dict:
        source = get_supplier_source_by_code(supplier_code=supplier_code)
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        row = self._get_price_list(price_list_id=price_list_id, source_id=str(source.id))

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

        cooldown = self.guard.get_status(integration=integration)
        return {
            "mode": "sync",
            "run_id": result.run_id,
            "status": result.status,
            "result": result.summary,
            "price_list": self._serialize_price_list(row=row, cooldown_wait_seconds=cooldown.wait_seconds),
        }

    def delete_price_list(self, *, supplier_code: str, price_list_id: str) -> dict[str, Any]:
        source = get_supplier_source_by_code(supplier_code=supplier_code)
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        row = self._get_price_list(price_list_id=price_list_id, source_id=str(source.id))

        deleted_remote = False
        remote_delete_error = ""
        if supplier_code == "utr" and row.request_mode == "utr_api" and row.remote_id:
            if not integration.access_token:
                raise SupplierIntegrationError("Нельзя удалить прайс в UTR: отсутствует access token.")
            try:
                self.utr_client.delete_pricelist(
                    access_token=integration.access_token,
                    pricelist_id=row.remote_id,
                )
                deleted_remote = True
            except SupplierClientError as exc:
                if self._is_utr_nonfatal_delete_error(exc):
                    remote_delete_error = str(exc)
                else:
                    raise SupplierIntegrationError(f"Не удалось удалить прайс в UTR: {exc}") from exc

        deleted_file = False
        if row.downloaded_file_path:
            file_path = Path(row.downloaded_file_path)
            if file_path.exists() and file_path.is_file():
                try:
                    file_path.unlink()
                    deleted_file = True
                except OSError:
                    deleted_file = False

        payload = {
            "deleted": True,
            "deleted_remote": deleted_remote,
            "deleted_file": deleted_file,
            "price_list_id": str(row.id),
            "remote_id": row.remote_id,
            "remote_delete_error": remote_delete_error,
        }
        row.delete()
        return payload

    def _get_price_list(self, *, price_list_id: str, source_id: str) -> SupplierPriceList:
        try:
            return SupplierPriceList.objects.select_related("imported_run").get(id=price_list_id, source_id=source_id)
        except SupplierPriceList.DoesNotExist as exc:
            raise SupplierIntegrationError("Прайс не найден.") from exc

    def _refresh_generating_state(self, *, row: SupplierPriceList, supplier_code: str, integration) -> None:
        if row.status != SupplierPriceList.STATUS_GENERATING:
            return

        changed_fields: set[str] = set()
        now = timezone.now()

        if (
            supplier_code == "utr"
            and row.request_mode == "utr_api"
            and row.remote_id
            and integration.access_token
        ):
            try:
                status_payload = self.utr_client.get_pricelist_status(
                    access_token=integration.access_token,
                    pricelist_id=row.remote_id,
                )
                remote_status = self._extract_remote_status(status_payload)
                if remote_status and row.remote_status != remote_status:
                    row.remote_status = remote_status
                    changed_fields.add("remote_status")
                if self._is_ready_status(remote_status):
                    row.status = SupplierPriceList.STATUS_READY
                    row.generated_at = row.generated_at or now
                    changed_fields.update({"status", "generated_at"})
                elif self._is_failed_status(remote_status):
                    row.status = SupplierPriceList.STATUS_FAILED
                    row.last_error_at = now
                    row.last_error_message = "Поставщик вернул ошибочный статус прайса."
                    changed_fields.update({"status", "last_error_at", "last_error_message"})
            except SupplierClientError:
                # Keep local ETA-driven state; do not fail listing on transient API errors.
                pass

        if row.status == SupplierPriceList.STATUS_GENERATING and row.expected_ready_at and row.expected_ready_at <= now:
            row.status = SupplierPriceList.STATUS_READY
            row.generated_at = row.generated_at or now
            changed_fields.update({"status", "generated_at"})

        if changed_fields:
            row.save(update_fields=tuple(sorted({*changed_fields, "updated_at"})))

    def _hydrate_utr_remote_fields(self, *, row: SupplierPriceList, access_token: str) -> None:
        if row.remote_token:
            return
        if not row.remote_id:
            return

        try:
            price_lists = self.utr_client.list_pricelists(access_token=access_token)
        except SupplierClientError:
            return

        for item in price_lists:
            item_id = str(item.get("id", "")).strip()
            if item_id != row.remote_id:
                continue

            row.remote_token = str(item.get("token", "")).strip()
            remote_status = self._normalize_status_value(item.get("status", ""))
            if remote_status:
                row.remote_status = remote_status
            row.file_size_label = str(item.get("fileSize", row.file_size_label)).strip()
            size = item.get("size")
            if isinstance(size, int):
                row.file_size_bytes = size
            elif isinstance(size, str) and size.isdigit():
                row.file_size_bytes = int(size)
            if self._is_ready_status(row.remote_status):
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

    def _extract_file_metadata(self, *, source_file: Path | None, supplier_code: str) -> dict[str, Any]:
        if source_file is None or not source_file.exists() or not source_file.is_file():
            return {
                "file_name": "",
                "file_path": "",
                "file_size_bytes": 0,
                "file_size_label": "",
                "warehouse_columns": [],
                "price_columns": [],
                "row_count": 0,
            }

        headers: list[str] = []
        row_count = 0
        suffix = source_file.suffix.lower()

        if suffix == ".xlsx":
            rows = parse_xlsx_rows(source_file)
            row_count = len(rows)
            headers = list(rows[0][1].keys()) if rows else []
        else:
            content = source_file.read_text(encoding="utf-8", errors="ignore")
            rows = parse_table_rows(content)
            row_count = len(rows)
            headers = list(rows[0][1].keys()) if rows else []

        price_columns = self._detect_price_columns(headers=headers)
        warehouse_columns = self._detect_warehouse_columns(
            headers=headers,
            supplier_code=supplier_code,
            price_columns=price_columns,
        )
        file_size_bytes = source_file.stat().st_size

        return {
            "file_name": source_file.name,
            "file_path": str(source_file),
            "file_size_bytes": file_size_bytes,
            "file_size_label": self._human_size(file_size_bytes),
            "warehouse_columns": warehouse_columns,
            "price_columns": price_columns,
            "row_count": row_count,
        }

    def _detect_price_columns(self, *, headers: list[str]) -> list[str]:
        columns: list[str] = []
        for header in headers:
            key = header.lower()
            if (
                "ціна" in key
                or "price" in key
                or "ррц" in key
                or key.startswith("price_")
            ):
                columns.append(header)
        return columns

    def _detect_warehouse_columns(self, *, headers: list[str], supplier_code: str, price_columns: list[str]) -> list[str]:
        if supplier_code == "utr":
            core = {
                "артикул utr",
                "артикул",
                "найменування",
                "бренд",
                "валюта",
                "ціна",
                "код",
                "категорія",
                "опис",
                "група тд",
                "артикул тд",
                "зображення товару",
            }
            return [
                header
                for header in headers
                if header.lower() not in core and header not in price_columns
            ]

        return [
            header
            for header in headers
            if "склад" in header.lower()
            or "warehouse" in header.lower()
            or header.lower().startswith("count_warehouse_")
        ]

    def _resolve_source_file_path(self, raw_path: str) -> Path | None:
        if not raw_path.strip():
            return None
        path = Path(raw_path).expanduser()
        if not path.exists():
            return None
        if path.is_file():
            return path.resolve()
        if path.is_dir():
            candidates = sorted(
                [item for item in path.rglob("*") if item.is_file()],
                key=lambda item: item.stat().st_mtime,
            )
            return candidates[-1].resolve() if candidates else None
        return None

    def _resolve_extension(self, *, requested_format: str, source_file_name: str) -> str:
        format_key = requested_format.strip().lower()
        if format_key in {"xlsx", "csv", "txt", "json"}:
            return format_key
        if source_file_name and "." in source_file_name:
            return source_file_name.rsplit(".", 1)[-1].lower()
        return "xlsx"

    def _extract_remote_status(self, payload: dict | str) -> str:
        if isinstance(payload, str):
            return self._normalize_status_value(payload)
        if not isinstance(payload, dict):
            return ""
        for key in ("status", "data", "state"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return self._normalize_status_value(value)
        return ""

    def _normalize_status_value(self, value: Any) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip().lower().replace(" ", "_")

    def _is_ready_status(self, status: str) -> bool:
        return status in {"ready", "complete", "completed", "downloaded", "uploaded"}

    def _is_failed_status(self, status: str) -> bool:
        return status in {"failed", "error", "cancelled", "canceled"}

    def _is_utr_nonfatal_delete_error(self, exc: SupplierClientError) -> bool:
        status_code = exc.status_code or 0
        message = str(exc).strip().lower()
        if not message:
            return False
        if status_code == 404:
            return True
        if status_code not in {400, 409}:
            return False
        markers = (
            "not found",
            "not ready",
            "already deleted",
            "не найден",
            "не готов",
            "ще не готов",
        )
        return any(marker in message for marker in markers)

    def _generation_wait_seconds(self, *, row: SupplierPriceList) -> int:
        if not row.expected_ready_at:
            return 1
        delta = int((row.expected_ready_at - timezone.now()).total_seconds())
        return max(delta, 1)

    def _serialize_price_list(self, *, row: SupplierPriceList, cooldown_wait_seconds: int) -> dict[str, Any]:
        generation_wait_seconds = 0
        if row.status == SupplierPriceList.STATUS_GENERATING and row.expected_ready_at:
            generation_wait_seconds = max(int((row.expected_ready_at - timezone.now()).total_seconds()), 0)

        download_available = row.status in {
            SupplierPriceList.STATUS_READY,
            SupplierPriceList.STATUS_DOWNLOADED,
            SupplierPriceList.STATUS_IMPORTED,
        }
        import_available = row.status in {
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

    def _human_size(self, size: int) -> str:
        if size <= 0:
            return ""
        steps = ["B", "KB", "MB", "GB"]
        value = float(size)
        step = 0
        while value >= 1024 and step < len(steps) - 1:
            value /= 1024
            step += 1
        if step == 0:
            return f"{int(value)} {steps[step]}"
        return f"{value:.1f} {steps[step]}"
