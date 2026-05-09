from __future__ import annotations

import time
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Product
from apps.supplier_imports.models import ImportArtifact, ImportRun, ImportSource
from apps.supplier_imports.parsers import ParseResult, get_parser
from apps.supplier_imports.selectors import get_supplier_integration_for_source
from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError, SupplierIntegrationError
from apps.supplier_imports.services.integrations.integration_state_service import SupplierIntegrationStateService
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.normalization import ArticleNormalizerService, BrandAliasResolverService
from apps.supplier_imports.services.product_matcher import ProductMatcher
from apps.supplier_imports.services.quality import ImportQualityService
from apps.supplier_imports.services.supplier_offer_sync import SupplierOfferSyncService

from . import artifacts, autodb_postprocess, diagnostics, followup, parsing, persistence, preparation
from .types import ImportExecutionResult


class SupplierImportRunner:
    def run_source(
        self,
        *,
        source: ImportSource,
        trigger: str = "manual",
        dry_run: bool = False,
        file_paths: list[str] | None = None,
        reprice: bool | None = None,
        reindex: bool | None = None,
        autodb_enrich: bool | None = None,
        update_product_names: bool | None = None,
        update_product_images: bool | None = None,
        autodb_limit: int = 0,
        autodb_allow_remote: bool | None = None,
        row_limit: int = 0,
    ) -> ImportExecutionResult:
        integration = get_supplier_integration_for_source(source=source)
        if not integration.is_enabled:
            raise SupplierIntegrationError("Интеграция поставщика отключена.")

        # Guard is enforced in backend for both manual and scheduled flows.
        SupplierRateLimitGuardService().acquire_or_raise(
            integration_id=str(integration.id),
            action_key="import_run",
        )

        integration_state = SupplierIntegrationStateService()
        perform_reprice = source.auto_reprice_after_import if reprice is None else reprice
        perform_reindex = source.auto_reindex_after_import if reindex is None else reindex
        perform_autodb_enrich = self._resolve_autodb_enrich_enabled(override=autodb_enrich)
        perform_autodb_name_update = self._resolve_autodb_name_update_enabled(override=update_product_names)
        perform_autodb_image_update = self._resolve_autodb_image_update_enabled(override=update_product_images)
        autodb_limit = max(int(autodb_limit or 0), 0)
        row_limit = max(int(row_limit or 0), 0)
        remaining_row_limit = row_limit
        started_at = timezone.now()
        run_timer_started = time.perf_counter()
        timings: dict[str, float | list[dict[str, object]]] = {}

        source.last_started_at = started_at
        source.save(update_fields=("last_started_at", "updated_at"))

        run = ImportRun.objects.create(
            source=source,
            status=ImportRun.STATUS_RUNNING,
            trigger=trigger,
            dry_run=dry_run,
            started_at=started_at,
        )

        parser = get_parser(source.parser_type)
        supplier_offer_sync = SupplierOfferSyncService()
        quality_service = ImportQualityService()
        article_normalizer = ArticleNormalizerService()
        brand_resolver = BrandAliasResolverService()

        matcher_started = time.perf_counter()
        matcher = ProductMatcher(
            article_normalizer=article_normalizer,
            brand_resolver=brand_resolver,
            lightweight_products=persistence.uses_current_offer_persistence(source=source),
        )
        timings["matcher_init_sec"] = self._elapsed_seconds(matcher_started)

        affected_products: set[str] = set()

        try:
            collect_started = time.perf_counter()
            files = self._collect_files(source=source, file_paths=file_paths)
            timings["collect_files_sec"] = self._elapsed_seconds(collect_started)
            if not files:
                self._create_row_error(
                    run=run,
                    source=source,
                    message="No input files found for import source.",
                    error_code="no_files",
                )
                run.errors_count = 1
                run.status = ImportRun.STATUS_FAILED
                run.finished_at = timezone.now()
                timings["total_sec"] = self._elapsed_seconds(run_timer_started)
                run.summary = {"files_processed": 0, "timings": timings}
                run.save(update_fields=("errors_count", "status", "finished_at", "summary", "updated_at"))
                self._finalize_source_timestamps(source=source, run=run)
                integration_state.mark_import_failure(
                    integration=integration,
                    message="No input files found for import source.",
                )
                quality_service.refresh_for_run(run=run)
                return self._as_result(run)

            file_timings: list[dict[str, object]] = []
            for file_path in files:
                if row_limit > 0 and remaining_row_limit <= 0:
                    break
                file_timing: dict[str, object] = {"path": str(file_path)}
                artifact_started = time.perf_counter()
                artifact = self._create_artifact(run=run, source=source, file_path=file_path)
                file_timing["artifact_sec"] = self._elapsed_seconds(artifact_started)

                parse_started = time.perf_counter()
                parse_result = self._parse_artifact(source=source, artifact=artifact, parser=parser)
                file_timing["parsed_offers_total"] = len(parse_result.offers)
                file_timing["parse_issues_total"] = len(parse_result.issues)
                if row_limit > 0:
                    parse_result = self._apply_row_limit_to_parse_result(
                        parse_result=parse_result,
                        remaining_row_limit=remaining_row_limit,
                    )
                    consumed = len(parse_result.offers) + len(parse_result.issues)
                    remaining_row_limit = max(remaining_row_limit - consumed, 0)
                file_timing["parse_sec"] = self._elapsed_seconds(parse_started)
                file_timing["parsed_offers"] = len(parse_result.offers)
                file_timing["parse_issues"] = len(parse_result.issues)

                persist_started = time.perf_counter()
                created, updated, skipped, artifact_errors, product_ids = self._persist_parsed_rows(
                    run=run,
                    source=source,
                    artifact=artifact,
                    parse_result=parse_result,
                    dry_run=dry_run,
                    matcher=matcher,
                    supplier_offer_sync=supplier_offer_sync,
                    article_normalizer=article_normalizer,
                    brand_resolver=brand_resolver,
                )
                file_timing["persist_sec"] = self._elapsed_seconds(persist_started)
                file_timing["offers_created"] = created
                file_timing["offers_updated"] = updated
                file_timing["offers_skipped"] = skipped
                file_timing["errors"] = artifact_errors
                file_timing["affected_products"] = len(product_ids)
                file_timings.append(file_timing)

                affected_products.update(product_ids)

                run.parsed_rows += len(parse_result.offers)
                run.processed_rows += len(parse_result.offers) + len(parse_result.issues)
                run.offers_created += created
                run.offers_updated += updated
                run.offers_skipped += skipped
                run.errors_count += artifact_errors
                run.save(
                    update_fields=(
                        "parsed_rows",
                        "processed_rows",
                        "offers_created",
                        "offers_updated",
                        "offers_skipped",
                        "errors_count",
                        "updated_at",
                    )
                )
            timings["files"] = file_timings

            autodb_started = time.perf_counter()
            try:
                autodb_summary = autodb_postprocess.SupplierImportAutoDbPostProcessor().run_for_import(
                    run=run,
                    dry_run=dry_run,
                    autodb_enrich=perform_autodb_enrich,
                    update_product_names=perform_autodb_name_update,
                    update_product_images=perform_autodb_image_update,
                    limit=autodb_limit,
                    allow_remote_lookup=autodb_allow_remote,
                )
            except Exception as exc:  # noqa: BLE001
                autodb_summary = autodb_postprocess.SupplierImportAutoDbSummary(
                    enabled=perform_autodb_enrich,
                    name_update_enabled=perform_autodb_name_update,
                    limit=autodb_limit,
                    dry_run=dry_run,
                    failed=1,
                    remote_config_error=f"postprocess_failed:{exc}",
                )
            timings["autodb_postprocess_sec"] = self._elapsed_seconds(autodb_started)
            run.summary = {
                **(run.summary or {}),
                "autodb_supplier_import": autodb_summary.to_dict(),
            }

            if not dry_run and affected_products and perform_reprice:
                reprice_started = time.perf_counter()
                repricing_stats = self._reprice_products(affected_product_ids=list(affected_products), source=source, run=run)
                timings["reprice_sec"] = self._elapsed_seconds(reprice_started)
                run.repriced_products = int(repricing_stats.get("repriced", 0))

            if not dry_run and affected_products and perform_reindex:
                reindex_started = time.perf_counter()
                reindex_stats = followup.reindex_products(affected_product_ids=list(affected_products))
                timings["reindex_sec"] = self._elapsed_seconds(reindex_started)
                run.reindexed_products = int(reindex_stats.get("indexed", 0))
                run.summary["reindex"] = reindex_stats

            run.status = self._resolve_run_status(run)
            run.finished_at = timezone.now()
            timings["total_sec"] = self._elapsed_seconds(run_timer_started)
            run.summary = {
                **run.summary,
                "files_processed": len(files),
                "affected_products": len(affected_products),
                "dry_run": dry_run,
                "row_limit": row_limit,
                "timings": timings,
                "cache_stats": matcher.cache_stats(),
            }
            run.save(update_fields=("status", "finished_at", "summary", "repriced_products", "reindexed_products", "updated_at"))
        except SupplierCooldownError:
            raise
        except Exception as exc:
            run.status = ImportRun.STATUS_FAILED
            run.finished_at = timezone.now()
            run.note = str(exc)[:1000]
            timings["total_sec"] = self._elapsed_seconds(run_timer_started)
            run.summary = {
                **(run.summary or {}),
                "exception": str(exc),
                "timings": timings,
                "cache_stats": matcher.cache_stats(),
            }
            run.save(update_fields=("status", "finished_at", "note", "summary", "updated_at"))
            self._finalize_source_timestamps(source=source, run=run)
            integration_state.mark_import_failure(integration=integration, message=str(exc))
            quality_service.refresh_for_run(run=run)
            raise

        self._finalize_source_timestamps(source=source, run=run)
        integration_state.mark_import_success(integration=integration)
        quality_result = quality_service.refresh_for_run(run=run)
        run.summary = {
            **(run.summary or {}),
            "quality": {
                "match_rate": float(quality_result.quality.match_rate),
                "error_rate": float(quality_result.quality.error_rate),
                "requires_operator_attention": quality_result.quality.requires_operator_attention,
                "flags": quality_result.flags,
            },
        }
        run.save(update_fields=("summary", "updated_at"))
        return self._as_result(run)

    @staticmethod
    def _elapsed_seconds(started_at: float) -> float:
        return round(time.perf_counter() - started_at, 3)

    @staticmethod
    def _apply_row_limit_to_parse_result(*, parse_result: ParseResult, remaining_row_limit: int) -> ParseResult:
        if remaining_row_limit <= 0:
            return ParseResult(offers=[], issues=[])
        if len(parse_result.offers) + len(parse_result.issues) <= remaining_row_limit:
            return parse_result

        limited_offers = list(parse_result.offers[:remaining_row_limit])
        remaining_for_issues = max(remaining_row_limit - len(limited_offers), 0)
        limited_issues = list(parse_result.issues[:remaining_for_issues])
        return ParseResult(offers=limited_offers, issues=limited_issues)

    # Back-compat wrappers
    def _collect_files(self, *, source: ImportSource, file_paths: list[str] | None) -> list[Path]:
        return preparation.collect_files(source=source, file_paths=file_paths)

    def _create_artifact(self, *, run: ImportRun, source: ImportSource, file_path: Path) -> ImportArtifact:
        return artifacts.create_artifact(run=run, source=source, file_path=file_path)

    def _parse_artifact(self, *, source: ImportSource, artifact: ImportArtifact, parser) -> ParseResult:
        return parsing.parse_artifact(source=source, artifact=artifact, parser=parser)

    def _persist_parsed_rows(
        self,
        *,
        run: ImportRun,
        source: ImportSource,
        artifact: ImportArtifact,
        parse_result: ParseResult,
        dry_run: bool,
        matcher: ProductMatcher,
        supplier_offer_sync: SupplierOfferSyncService,
        article_normalizer: ArticleNormalizerService,
        brand_resolver: BrandAliasResolverService,
    ) -> tuple[int, int, int, int, set[str]]:
        return persistence.persist_parsed_rows(
            self,
            run=run,
            source=source,
            artifact=artifact,
            parse_result=parse_result,
            dry_run=dry_run,
            matcher=matcher,
            supplier_offer_sync=supplier_offer_sync,
            article_normalizer=article_normalizer,
            brand_resolver=brand_resolver,
        )

    def _extract_utr_detail_id(self, *, source: ImportSource, raw_payload: dict) -> str:
        return preparation.extract_utr_detail_id(source=source, raw_payload=raw_payload)

    def _attach_utr_detail_id(self, *, product: Product, utr_detail_id: str) -> None:
        return persistence.attach_utr_detail_id(product=product, utr_detail_id=utr_detail_id)

    def _create_row_error(
        self,
        *,
        run: ImportRun,
        source: ImportSource,
        message: str,
        artifact: ImportArtifact | None = None,
        row_number: int | None = None,
        external_sku: str = "",
        error_code: str = "import_error",
        raw_payload: dict | None = None,
    ) -> None:
        return persistence.create_row_error(
            run=run,
            source=source,
            message=message,
            artifact=artifact,
            row_number=row_number,
            external_sku=external_sku,
            error_code=error_code,
            raw_payload=raw_payload,
        )

    def _reprice_products(self, *, affected_product_ids: list[str], source: ImportSource, run: ImportRun) -> dict[str, int]:
        return followup.reprice_products(affected_product_ids=affected_product_ids, source=source, run=run)

    def _resolve_run_status(self, run: ImportRun) -> str:
        return diagnostics.resolve_run_status(run=run)

    def _as_result(self, run: ImportRun) -> ImportExecutionResult:
        return diagnostics.as_result(run=run)

    def _finalize_source_timestamps(self, *, source: ImportSource, run: ImportRun) -> None:
        return diagnostics.finalize_source_timestamps(source=source, run=run)

    @staticmethod
    def _resolve_autodb_enrich_enabled(*, override: bool | None) -> bool:
        if override is not None:
            return bool(override)
        return bool(getattr(settings, "AUTODB_PRO_SUPPLIER_IMPORT_ENRICHMENT_ENABLED", False))

    @staticmethod
    def _resolve_autodb_name_update_enabled(*, override: bool | None) -> bool:
        if override is not None:
            return bool(override)
        return bool(getattr(settings, "AUTODB_PRO_SUPPLIER_IMPORT_NAME_UPDATE_ENABLED", False))

    @staticmethod
    def _resolve_autodb_image_update_enabled(*, override: bool | None) -> bool:
        if override is not None:
            return bool(override)
        return bool(getattr(settings, "AUTODB_PRO_SUPPLIER_IMPORT_IMAGE_UPDATE_ENABLED", False))
