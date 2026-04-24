from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.pricing.models import SupplierOffer
from apps.search.services import ProductIndexer
from apps.supplier_imports.models import ImportRun
from apps.supplier_imports.selectors import ensure_default_import_sources, get_import_source_by_code, get_supplier_integration_by_code
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierCooldownError, SupplierIntegrationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduledPipelineResult:
    source_code: str
    status: str
    detail: str
    payload: dict[str, Any]


class ScheduledSupplierImportPipelineService:
    DOWNLOAD_POLL_SECONDS = 12
    DOWNLOAD_MAX_WAIT_SECONDS = 240
    REQUEST_MAX_ATTEMPTS = 3
    UTR_PRICE_COOLDOWN_SECONDS = 61

    def run(self, *, source_code: str) -> ScheduledPipelineResult:
        from apps.backoffice.services.supplier_price_workflow_service import SupplierPriceWorkflowService
        from apps.backoffice.services.supplier_workspace_service import SupplierWorkspaceService

        ensure_default_import_sources()
        source = get_import_source_by_code(source_code)
        integration = get_supplier_integration_by_code(source_code=source_code)

        if not source.is_active:
            return ScheduledPipelineResult(
                source_code=source_code,
                status="skipped",
                detail="source_inactive",
                payload={},
            )
        if not source.is_auto_import_enabled:
            return ScheduledPipelineResult(
                source_code=source_code,
                status="skipped",
                detail="auto_import_disabled",
                payload={},
            )
        if not integration.is_enabled:
            return ScheduledPipelineResult(
                source_code=source_code,
                status="skipped",
                detail="integration_disabled",
                payload={},
            )

        started_at = timezone.now()
        workspace_service = SupplierWorkspaceService()
        price_workflow = SupplierPriceWorkflowService()

        token_step = self._ensure_token(
            source_code=source_code,
            workspace_service=workspace_service,
        )

        params = price_workflow.get_request_params(supplier_code=source_code)
        defaults = params.get("defaults", {}) if isinstance(params, dict) else {}
        requested = self._request_with_cooldown_retry(
            price_workflow=price_workflow,
            source_code=source_code,
            requested_format="xlsx",
            in_stock=bool(defaults.get("in_stock", True)),
            show_scancode=bool(defaults.get("show_scancode", False)),
            utr_article=bool(defaults.get("utr_article", source_code == "utr")),
        )
        price_list_id = str(requested.get("id", "")).strip()
        if not price_list_id:
            raise SupplierIntegrationError("Не удалось получить идентификатор запрошенного прайса.")

        self._wait_utr_price_cooldown(source_code=source_code)
        downloaded = self._download_with_polling(
            price_workflow=price_workflow,
            source_code=source_code,
            price_list_id=price_list_id,
        )

        self._wait_utr_price_cooldown(source_code=source_code)
        imported = self._import_with_cooldown_retry(
            price_workflow=price_workflow,
            source_code=source_code,
            price_list_id=price_list_id,
        )
        run_id = str(imported.get("run_id", "")).strip()
        if not run_id:
            raise SupplierIntegrationError("Импорт завершился без run_id.")

        published = workspace_service.publish_mapped_products(
            supplier_code=source_code,
            run_id=run_id,
            include_needs_review=False,
            dry_run=False,
            reprice_after_publish=True,
        )

        product_ids = self._collect_reindex_product_ids(
            source_code=source_code,
            run_id=run_id,
            started_at=started_at,
        )
        reindex_summary: dict[str, Any]
        if product_ids:
            reindex_summary = ProductIndexer().reindex_products(product_ids=product_ids)
        else:
            reindex_summary = {"indexed": 0, "errors": 0, "total": 0, "backend": "none"}

        return ScheduledPipelineResult(
            source_code=source_code,
            status="success",
            detail="pipeline_completed",
            payload={
                "token": token_step,
                "request": requested,
                "download": downloaded,
                "import": imported,
                "publish": published,
                "reindex": reindex_summary,
                "reindexed_product_ids": len(product_ids),
            },
        )

    def _download_with_polling(
        self,
        *,
        price_workflow,
        source_code: str,
        price_list_id: str,
    ) -> dict[str, Any]:
        attempts = max(1, self.DOWNLOAD_MAX_WAIT_SECONDS // self.DOWNLOAD_POLL_SECONDS)
        poll_delay_seconds = self.UTR_PRICE_COOLDOWN_SECONDS if source_code == "utr" else self.DOWNLOAD_POLL_SECONDS
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                return price_workflow.download_price_list(
                    supplier_code=source_code,
                    price_list_id=price_list_id,
                )
            except SupplierCooldownError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    time.sleep(exc.retry_after_seconds + 1)
                    continue
                raise
            except SupplierIntegrationError as exc:
                last_error = exc
                message = str(exc).lower()
                if "формируется" in message and attempt < attempts - 1:
                    time.sleep(poll_delay_seconds)
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise SupplierIntegrationError("Не удалось скачать прайс.")

    def _import_with_cooldown_retry(
        self,
        *,
        price_workflow,
        source_code: str,
        price_list_id: str,
    ) -> dict[str, Any]:
        for attempt in range(3):
            try:
                return price_workflow.import_price_list_to_raw(
                    supplier_code=source_code,
                    price_list_id=price_list_id,
                )
            except SupplierCooldownError as exc:
                if attempt == 2:
                    raise
                time.sleep(exc.retry_after_seconds + 1)
        raise SupplierIntegrationError("Не удалось импортировать прайс после повторных попыток.")

    def _wait_utr_price_cooldown(self, *, source_code: str) -> None:
        if source_code != "utr":
            return
        time.sleep(self.UTR_PRICE_COOLDOWN_SECONDS)

    def _request_with_cooldown_retry(
        self,
        *,
        price_workflow,
        source_code: str,
        requested_format: str,
        in_stock: bool,
        show_scancode: bool,
        utr_article: bool,
    ) -> dict[str, Any]:
        for attempt in range(self.REQUEST_MAX_ATTEMPTS):
            try:
                return price_workflow.request_price_list(
                    supplier_code=source_code,
                    requested_format=requested_format,
                    in_stock=in_stock,
                    show_scancode=show_scancode,
                    utr_article=utr_article,
                    visible_brands=[],
                    categories=[],
                    models_filter=[],
                )
            except SupplierCooldownError as exc:
                if attempt == self.REQUEST_MAX_ATTEMPTS - 1:
                    raise
                time.sleep(exc.retry_after_seconds + 1)
        raise SupplierIntegrationError("Не удалось запросить прайс после повторных попыток.")

    def _ensure_token(
        self,
        *,
        source_code: str,
        workspace_service,
    ) -> dict[str, Any]:
        integration = get_supplier_integration_by_code(source_code=source_code)
        now = timezone.now()

        if source_code == "utr":
            if integration.refresh_token:
                try:
                    result = workspace_service.utr_client.refresh_token(
                        refresh_token=integration.refresh_token,
                        browser_fingerprint=integration.browser_fingerprint or "svom-backoffice",
                    )
                    workspace_service.token_storage.store_tokens(
                        integration=integration,
                        access_token=result.access_token,
                        refresh_token=result.refresh_token,
                        access_expires_at=result.access_expires_at,
                        refresh_expires_at=result.refresh_expires_at,
                        refreshed=True,
                    )
                    workspace_service.integration_state.mark_connection_status(integration=integration, status="connected")
                    return {"mode": "refresh", "status": "ok"}
                except SupplierClientError:
                    logger.warning("Scheduled token refresh failed for UTR; falling back to obtain.", exc_info=True)

            self._require_credentials(integration=integration)
            result = workspace_service.utr_client.obtain_token(
                login=integration.login,
                password=integration.password,
                browser_fingerprint=integration.browser_fingerprint or "svom-backoffice",
            )
            workspace_service.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                access_expires_at=result.access_expires_at,
                refresh_expires_at=result.refresh_expires_at,
                refreshed=False,
            )
            workspace_service.integration_state.mark_connection_status(integration=integration, status="connected")
            return {"mode": "obtain", "status": "ok"}

        if source_code == "gpl":
            # GPL does not support stable refresh flow in production. Obtain a new token every run.
            self._require_credentials(integration=integration)
            result = workspace_service.gpl_client.obtain_token(
                login=integration.login,
                password=integration.password,
            )
            workspace_service.token_storage.store_tokens(
                integration=integration,
                access_token=result.access_token,
                refresh_token=integration.refresh_token,
                access_expires_in_seconds=result.expires_in,
                refreshed=False,
            )
            workspace_service.integration_state.mark_connection_status(integration=integration, status="connected")
            return {"mode": "obtain", "status": "ok"}

        if integration.access_token and (integration.access_token_expires_at is None or integration.access_token_expires_at > now):
            return {"mode": "noop", "status": "ok"}
        raise SupplierIntegrationError("Поставщик не поддерживается для автосценария расписания.")

    def _collect_reindex_product_ids(self, *, source_code: str, run_id: str, started_at: datetime) -> list[str]:
        source = get_import_source_by_code(source_code)
        run_product_ids = list(
            ImportRun.objects.filter(id=run_id)
            .values_list("raw_offers__matched_product_id", flat=True)
            .distinct()
        )
        supplier_offer_product_ids = list(
            SupplierOffer.objects.filter(supplier=source.supplier, updated_at__gte=started_at)
            .values_list("product_id", flat=True)
            .distinct()
        )
        normalized = {
            str(item)
            for item in [*run_product_ids, *supplier_offer_product_ids]
            if item
        }
        return sorted(normalized)

    @staticmethod
    def _require_credentials(*, integration) -> None:
        if not integration.login or not integration.password:
            raise SupplierIntegrationError("Укажите логин и пароль поставщика для запуска расписания.")
