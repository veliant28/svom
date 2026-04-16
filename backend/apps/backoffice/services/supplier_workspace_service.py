from __future__ import annotations

from pathlib import Path

from django.utils import timezone

from apps.backoffice.selectors import (
    get_supplier_errors_queryset,
    get_supplier_runs_queryset,
    get_supplier_source_by_code,
    get_supplier_workspace_sources_queryset,
)
from apps.supplier_imports.selectors import get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierCooldownError, SupplierIntegrationError
from apps.supplier_imports.services.integrations.gpl_client import GplClient
from apps.supplier_imports.services.integrations.import_orchestration_service import SupplierImportOrchestrationService
from apps.supplier_imports.services.integrations.integration_state_service import SupplierIntegrationStateService
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.integrations.token_storage_service import SupplierTokenStorageService
from apps.supplier_imports.services.integrations.utr_client import UtrClient
from apps.supplier_imports.services.integrations.utr_brand_import_service import UtrBrandImportService
from apps.supplier_imports.services.mapped_offer_publish_service import SupplierMappedOffersPublishService
from apps.supplier_imports.parsers import ParserContext, UTRParser
from apps.supplier_imports.parsers.utils import parse_table_rows, parse_xlsx_rows, rows_to_csv_content


class SupplierWorkspaceService:
    def __init__(self):
        self.guard = SupplierRateLimitGuardService()
        self.token_storage = SupplierTokenStorageService()
        self.integration_state = SupplierIntegrationStateService()
        self.utr_client = UtrClient()
        self.utr_brand_import = UtrBrandImportService()
        self.gpl_client = GplClient()
        self.import_orchestration = SupplierImportOrchestrationService()

    def list_suppliers(self) -> list[dict]:
        rows: list[dict] = []
        for source in get_supplier_workspace_sources_queryset():
            integration = get_supplier_integration_by_code(source_code=source.code)
            cooldown = self.guard.get_status(integration=integration)
            rows.append(
                {
                    "code": source.code,
                    "name": source.name,
                    "supplier_name": source.supplier.name,
                    "is_enabled": integration.is_enabled,
                    "connection_status": self._resolve_connection_status(integration=integration),
                    "last_successful_import_at": integration.last_successful_import_at or source.last_success_at,
                    "last_failed_import_at": integration.last_failed_import_at or source.last_failed_at,
                    "can_run_now": cooldown.can_run,
                    "cooldown_wait_seconds": cooldown.wait_seconds,
                }
            )
        return rows

    def get_workspace(self, *, supplier_code: str) -> dict:
        source = get_supplier_source_by_code(supplier_code=supplier_code)
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        latest_run = get_supplier_runs_queryset(supplier_code=supplier_code).first()
        latest_error = get_supplier_errors_queryset(supplier_code=supplier_code).first()
        cooldown = self.guard.get_status(integration=integration)

        return {
            "supplier": {
                "code": source.code,
                "name": source.name,
                "supplier_name": source.supplier.name,
                "is_enabled": integration.is_enabled,
            },
            "connection": {
                "login": integration.login,
                "has_password": bool(integration.password),
                "access_token_masked": integration.masked_access_token,
                "refresh_token_masked": integration.masked_refresh_token,
                "access_token_expires_at": integration.access_token_expires_at,
                "refresh_token_expires_at": integration.refresh_token_expires_at,
                "token_obtained_at": integration.token_obtained_at,
                "last_token_refresh_at": integration.last_token_refresh_at,
                "last_token_error_at": integration.last_token_error_at,
                "last_token_error_message": integration.last_token_error_message,
                "credentials_updated_at": integration.credentials_updated_at,
                "status": self._resolve_connection_status(integration=integration),
                "last_connection_check_at": integration.last_connection_check_at,
                "last_connection_status": integration.last_connection_status,
            },
            "import": {
                "last_run_status": latest_run.status if latest_run else "",
                "last_run_at": latest_run.created_at if latest_run else None,
                "last_successful_import_at": integration.last_successful_import_at or source.last_success_at,
                "last_failed_import_at": integration.last_failed_import_at or source.last_failed_at,
                "last_import_error_message": integration.last_import_error_message
                or (latest_error.message if latest_error else ""),
                "last_run_summary": latest_run.summary if latest_run else {},
                "last_run_processed_rows": latest_run.processed_rows if latest_run else 0,
                "last_run_errors_count": latest_run.errors_count if latest_run else 0,
            },
            "cooldown": {
                "last_request_at": cooldown.last_request_at,
                "next_allowed_request_at": cooldown.next_allowed_request_at,
                "can_run": cooldown.can_run,
                "wait_seconds": cooldown.wait_seconds,
                "cooldown_seconds": cooldown.cooldown_seconds,
                "status_label": "Можно запускать" if cooldown.can_run else f"Подождите {cooldown.wait_seconds} сек.",
            },
            "utr": {
                "available": source.code == "utr",
                "last_brands_import_at": integration.last_brands_import_at,
                "last_brands_import_count": integration.last_brands_import_count,
                "last_brands_import_error_at": integration.last_brands_import_error_at,
                "last_brands_import_error_message": integration.last_brands_import_error_message,
            },
        }

    def update_settings(
        self,
        *,
        supplier_code: str,
        login: str | None = None,
        password: str | None = None,
        browser_fingerprint: str | None = None,
        is_enabled: bool | None = None,
    ) -> dict:
        integration = get_supplier_integration_by_code(source_code=supplier_code)

        if login is not None or password is not None or browser_fingerprint is not None:
            self.token_storage.update_credentials(
                integration=integration,
                login=login if login is not None else integration.login,
                password=password if password is not None else integration.password,
                browser_fingerprint=browser_fingerprint if browser_fingerprint is not None else integration.browser_fingerprint,
            )

        if is_enabled is not None:
            integration.is_enabled = bool(is_enabled)
            integration.save(update_fields=("is_enabled", "updated_at"))

        return self.get_workspace(supplier_code=supplier_code)

    def obtain_token(self, *, supplier_code: str) -> dict:
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        self._guard_and_validate_enabled(integration=integration, action_key="token_obtain")
        self._require_credentials(integration=integration)

        try:
            if supplier_code == "utr":
                result = self.utr_client.obtain_token(
                    login=integration.login,
                    password=integration.password,
                    browser_fingerprint=integration.browser_fingerprint or "svom-backoffice",
                )
                self.token_storage.store_tokens(
                    integration=integration,
                    access_token=result.access_token,
                    refresh_token=result.refresh_token,
                    access_expires_at=result.access_expires_at,
                    refresh_expires_at=result.refresh_expires_at,
                    refreshed=False,
                )
            elif supplier_code == "gpl":
                result = self.gpl_client.obtain_token(
                    login=integration.login,
                    password=integration.password,
                )
                self.token_storage.store_tokens(
                    integration=integration,
                    access_token=result.access_token,
                    refresh_token=integration.refresh_token,
                    access_expires_in_seconds=result.expires_in,
                    refreshed=False,
                )
            else:
                raise SupplierIntegrationError("Поставщик не поддерживается.")
            self.integration_state.mark_connection_status(integration=integration, status="connected")
        except SupplierClientError as exc:
            self.token_storage.mark_token_error(integration=integration, message=str(exc))
            self.integration_state.mark_connection_status(integration=integration, status="error")
            raise

        return self.get_workspace(supplier_code=supplier_code)

    def refresh_token(self, *, supplier_code: str) -> dict:
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        self._guard_and_validate_enabled(integration=integration, action_key="token_refresh")

        if supplier_code == "utr":
            if not integration.refresh_token:
                raise SupplierIntegrationError("Отсутствует refresh token. Сначала выполните получение токена.")
            try:
                result = self.utr_client.refresh_token(
                    refresh_token=integration.refresh_token,
                    browser_fingerprint=integration.browser_fingerprint or "svom-backoffice",
                )
                self.token_storage.store_tokens(
                    integration=integration,
                    access_token=result.access_token,
                    refresh_token=result.refresh_token,
                    access_expires_at=result.access_expires_at,
                    refresh_expires_at=result.refresh_expires_at,
                    refreshed=True,
                )
                self.integration_state.mark_connection_status(integration=integration, status="connected")
            except SupplierClientError as exc:
                self.token_storage.mark_token_error(integration=integration, message=str(exc))
                self.integration_state.mark_connection_status(integration=integration, status="error")
                raise
        elif supplier_code == "gpl":
            if not integration.access_token:
                raise SupplierIntegrationError("Отсутствует access token. Сначала выполните получение токена.")
            try:
                result = self.gpl_client.refresh_token(access_token=integration.access_token)
                self.token_storage.store_tokens(
                    integration=integration,
                    access_token=result.access_token,
                    refresh_token=integration.refresh_token,
                    access_expires_in_seconds=result.expires_in,
                    refreshed=True,
                )
                self.integration_state.mark_connection_status(integration=integration, status="connected")
            except SupplierClientError as exc:
                self.token_storage.mark_token_error(integration=integration, message=str(exc))
                self.integration_state.mark_connection_status(integration=integration, status="error")
                raise
        else:
            raise SupplierIntegrationError("Поставщик не поддерживается.")

        return self.get_workspace(supplier_code=supplier_code)

    def check_connection(self, *, supplier_code: str) -> dict:
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        self._guard_and_validate_enabled(integration=integration, action_key="connection_check")
        self._require_access_token(integration=integration)

        try:
            if supplier_code == "utr":
                details = self.utr_client.check_connection(access_token=integration.access_token)
            elif supplier_code == "gpl":
                details = self.gpl_client.check_connection(access_token=integration.access_token)
            else:
                raise SupplierIntegrationError("Поставщик не поддерживается.")
            self.integration_state.mark_connection_status(integration=integration, status="connected")
        except SupplierClientError as exc:
            self.integration_state.mark_connection_status(integration=integration, status="error")
            raise

        return {
            "ok": True,
            "details": details,
            "workspace": self.get_workspace(supplier_code=supplier_code),
        }

    def run_import(self, *, supplier_code: str, dry_run: bool = False, dispatch_async: bool = False) -> dict:
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        if not integration.is_enabled:
            raise SupplierIntegrationError("Интеграция поставщика отключена.")
        result = self.import_orchestration.run_import(
            source_code=supplier_code,
            dry_run=dry_run,
            dispatch_async=dispatch_async,
            trigger="backoffice:supplier_workspace_import",
        )
        return {"mode": result.mode, **result.payload}

    def sync_prices(self, *, supplier_code: str, dispatch_async: bool = False) -> dict:
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        if not integration.is_enabled:
            raise SupplierIntegrationError("Интеграция поставщика отключена.")
        result = self.import_orchestration.sync_prices(source_code=supplier_code, dispatch_async=dispatch_async)
        return {"mode": result.mode, **result.payload}

    def import_utr_brands(self) -> dict:
        supplier_code = "utr"
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        self._guard_and_validate_enabled(integration=integration, action_key="utr_brands_import")

        try:
            rows, import_source = self._fetch_utr_brand_rows(integration=integration, supplier_code=supplier_code)
            summary = self.utr_brand_import.import_rows(rows=rows, source_code=supplier_code)
            imported_count = summary.created + summary.updated
            self.integration_state.mark_brands_import_success(
                integration=integration,
                imported_count=imported_count,
            )
        except Exception as exc:
            self.integration_state.mark_brands_import_failure(integration=integration, message=str(exc))
            raise SupplierIntegrationError("Не удалось сохранить бренды UTR.") from exc

        return {
            "imported_count": imported_count,
            "source": import_source,
            "summary": summary.as_dict(),
            "workspace": self.get_workspace(supplier_code=supplier_code),
        }

    def publish_mapped_products(
        self,
        *,
        supplier_code: str,
        include_needs_review: bool = False,
        dry_run: bool = False,
        reprice_after_publish: bool = True,
    ) -> dict:
        # Ensure supplier/source exists and is supported by workspace.
        get_supplier_source_by_code(supplier_code=supplier_code)
        result = SupplierMappedOffersPublishService().publish_for_supplier(
            supplier_code=supplier_code,
            include_needs_review=include_needs_review,
            dry_run=dry_run,
            reprice_after_publish=reprice_after_publish,
        )
        return {
            "mode": "sync",
            "result": result.as_dict(),
        }

    def _fetch_utr_brand_rows(self, *, integration, supplier_code: str) -> tuple[list[dict], str]:
        if integration.access_token:
            try:
                return self.utr_client.fetch_brands(access_token=integration.access_token), "utr_api"
            except SupplierClientError:
                # Fallback to local UTR source file when API token is invalid/expired.
                pass

        source = get_supplier_source_by_code(supplier_code=supplier_code)
        file_path = Path(source.input_path).expanduser()
        if not file_path.exists() or not file_path.is_file():
            raise SupplierIntegrationError("Нет access token и отсутствует доступный UTR-файл для импорта брендов.")

        if file_path.suffix.lower() == ".xlsx":
            rows = parse_xlsx_rows(file_path)
            content = rows_to_csv_content(rows)
        else:
            content = file_path.read_text(encoding="utf-8", errors="ignore")

        parser = UTRParser()
        parse_result = parser.parse_content(
            content,
            file_name=file_path.name,
            context=ParserContext(
                source_code=source.code,
                mapping_config=source.mapping_config,
                default_currency=source.default_currency,
            ),
        )

        brands = [{"name": offer.brand_name} for offer in parse_result.offers if offer.brand_name.strip()]
        if brands:
            return brands, "utr_file"

        # Secondary extraction for edge-case files that parser cannot map to ParsedOffer.
        fallback_rows = parse_table_rows(content)
        extracted: list[dict] = []
        for _, row in fallback_rows:
            brand_name = (
                row.get("Бренд")
                or row.get("бренд")
                or row.get("brand")
                or row.get("Brand")
                or row.get("displayBrand")
                or row.get("brand_name")
                or ""
            ).strip()
            if brand_name:
                extracted.append({"name": brand_name})

        if not extracted:
            raise SupplierIntegrationError("UTR-файл не содержит брендов для импорта.")
        return extracted, "utr_file"

    def get_cooldown(self, *, supplier_code: str) -> dict:
        integration = get_supplier_integration_by_code(source_code=supplier_code)
        cooldown = self.guard.get_status(integration=integration)
        return {
            "supplier_code": supplier_code,
            "last_request_at": cooldown.last_request_at,
            "next_allowed_request_at": cooldown.next_allowed_request_at,
            "can_run": cooldown.can_run,
            "wait_seconds": cooldown.wait_seconds,
            "cooldown_seconds": cooldown.cooldown_seconds,
            "status_label": "Можно запускать" if cooldown.can_run else f"Подождите {cooldown.wait_seconds} сек.",
        }

    def _guard_and_validate_enabled(self, *, integration, action_key: str) -> None:
        if not integration.is_enabled:
            raise SupplierIntegrationError("Интеграция поставщика отключена.")
        self.guard.acquire_or_raise(integration_id=str(integration.id), action_key=action_key)

    def _require_credentials(self, *, integration) -> None:
        if not integration.login or not integration.password:
            raise SupplierIntegrationError("Укажите логин и пароль поставщика.")

    def _require_access_token(self, *, integration) -> None:
        if not integration.access_token:
            raise SupplierIntegrationError("Отсутствует access token. Получите токен в блоке подключения.")

    def _resolve_connection_status(self, *, integration) -> str:
        if integration.last_connection_status:
            return integration.last_connection_status

        if integration.access_token and integration.access_token_expires_at and integration.access_token_expires_at <= timezone.now():
            return "expired"
        if integration.access_token:
            return "connected"
        if integration.last_token_error_message:
            return "error"
        return "disconnected"
