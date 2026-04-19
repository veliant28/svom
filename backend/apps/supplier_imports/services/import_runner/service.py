from __future__ import annotations

from pathlib import Path

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

from . import artifacts, diagnostics, followup, parsing, persistence, preparation
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
        started_at = timezone.now()

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
        matcher = ProductMatcher()
        supplier_offer_sync = SupplierOfferSyncService()
        quality_service = ImportQualityService()
        article_normalizer = ArticleNormalizerService()
        brand_resolver = BrandAliasResolverService()
        affected_products: set[str] = set()

        try:
            files = self._collect_files(source=source, file_paths=file_paths)
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
                run.summary = {"files_processed": 0}
                run.save(update_fields=("errors_count", "status", "finished_at", "summary", "updated_at"))
                self._finalize_source_timestamps(source=source, run=run)
                integration_state.mark_import_failure(
                    integration=integration,
                    message="No input files found for import source.",
                )
                quality_service.refresh_for_run(run=run)
                return self._as_result(run)

            for file_path in files:
                artifact = self._create_artifact(run=run, source=source, file_path=file_path)
                parse_result = self._parse_artifact(source=source, artifact=artifact, parser=parser)

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

            if not dry_run and affected_products and perform_reprice:
                repricing_stats = self._reprice_products(affected_product_ids=list(affected_products), source=source, run=run)
                run.repriced_products = int(repricing_stats.get("repriced", 0))

            if not dry_run and affected_products and perform_reindex:
                reindex_stats = followup.reindex_products(affected_product_ids=list(affected_products))
                run.reindexed_products = int(reindex_stats.get("indexed", 0))
                run.summary["reindex"] = reindex_stats

            run.status = self._resolve_run_status(run)
            run.finished_at = timezone.now()
            run.summary = {
                **run.summary,
                "files_processed": len(files),
                "affected_products": len(affected_products),
                "dry_run": dry_run,
            }
            run.save(update_fields=("status", "finished_at", "summary", "repriced_products", "reindexed_products", "updated_at"))
        except SupplierCooldownError:
            raise
        except Exception as exc:
            run.status = ImportRun.STATUS_FAILED
            run.finished_at = timezone.now()
            run.note = str(exc)[:1000]
            run.summary = {**(run.summary or {}), "exception": str(exc)}
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
