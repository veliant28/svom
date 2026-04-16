from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Product
from apps.pricing.models import PriceHistory, SupplierOffer
from apps.pricing.services import ProductRepricer
from apps.search.services import ProductIndexer
from apps.supplier_imports.models import ImportArtifact, ImportRowError, ImportRun, ImportSource, OfferMatchReview, SupplierRawOffer
from apps.supplier_imports.parsers import ParseIssue, ParseResult, ParserContext, ParsedOffer, get_parser
from apps.supplier_imports.parsers.utils import parse_xlsx_rows, rows_to_csv_content
from apps.supplier_imports.selectors import get_supplier_integration_for_source
from apps.supplier_imports.services.integrations.exceptions import SupplierCooldownError, SupplierIntegrationError
from apps.supplier_imports.services.integrations.integration_state_service import SupplierIntegrationStateService
from apps.supplier_imports.services.integrations.rate_limit_guard_service import SupplierRateLimitGuardService
from apps.supplier_imports.services.normalization import ArticleNormalizerService, BrandAliasResolverService
from apps.supplier_imports.services.product_matcher import ProductMatcher
from apps.supplier_imports.services.quality import ImportQualityService
from apps.supplier_imports.services.supplier_offer_sync import SupplierOfferSyncService


@dataclass(frozen=True)
class ImportExecutionResult:
    run_id: str
    source_code: str
    status: str
    summary: dict[str, int | str | dict]


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
                reindex_stats = ProductIndexer().reindex_products(product_ids=list(affected_products))
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

    def _collect_files(self, *, source: ImportSource, file_paths: list[str] | None) -> list[Path]:
        if file_paths:
            return sorted({Path(path).expanduser().resolve() for path in file_paths if path and Path(path).exists()})

        if not source.input_path:
            return []

        root = Path(source.input_path).expanduser()
        if not root.exists():
            return []

        if root.is_file():
            return [root.resolve()]

        patterns = source.file_patterns or ["*.json", "*.csv", "*.txt"]
        candidates: set[Path] = set()
        for pattern in patterns:
            for candidate in root.rglob(pattern):
                if candidate.is_file():
                    candidates.add(candidate.resolve())

        return sorted(candidates)

    def _create_artifact(self, *, run: ImportRun, source: ImportSource, file_path: Path) -> ImportArtifact:
        file_bytes = file_path.read_bytes()
        checksum = hashlib.sha1(file_bytes).hexdigest()  # noqa: S324

        return ImportArtifact.objects.create(
            run=run,
            source=source,
            file_name=file_path.name,
            file_path=str(file_path),
            file_format=file_path.suffix.lstrip(".").lower(),
            file_size=len(file_bytes),
            checksum_sha1=checksum,
            status=ImportArtifact.STATUS_PENDING,
        )

    def _parse_artifact(self, *, source: ImportSource, artifact: ImportArtifact, parser) -> ParseResult:
        file_path = Path(artifact.file_path)
        if file_path.suffix.lower() == ".xlsx":
            rows = parse_xlsx_rows(file_path)
            content = rows_to_csv_content(rows)
        else:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        context = ParserContext(
            source_code=source.code,
            mapping_config=source.mapping_config,
            default_currency=source.default_currency,
        )

        parse_result = parser.parse_content(content, file_name=artifact.file_name, context=context)
        artifact.parsed_rows = len(parse_result.offers)
        artifact.errors_count = len(parse_result.issues)
        artifact.status = ImportArtifact.STATUS_PROCESSED if parse_result.offers else ImportArtifact.STATUS_SKIPPED
        if parse_result.issues and not parse_result.offers:
            artifact.status = ImportArtifact.STATUS_FAILED
        artifact.save(update_fields=("parsed_rows", "errors_count", "status", "updated_at"))
        return parse_result

    @transaction.atomic
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
        created = 0
        updated = 0
        skipped = 0
        errors_count = 0
        affected_products: set[str] = set()

        for issue in parse_result.issues:
            self._create_row_error(
                run=run,
                source=source,
                artifact=artifact,
                message=issue.message,
                row_number=issue.row_number,
                external_sku=issue.external_sku,
                error_code=issue.error_code,
                raw_payload=issue.raw_payload,
            )
            errors_count += 1

        for row_index, offer in enumerate(parse_result.offers, start=1):
            article_result = article_normalizer.normalize(article=offer.article or offer.external_sku, source=source)
            brand_result = brand_resolver.resolve(brand_name=offer.brand_name, source=source, supplier=source.supplier)

            decision = matcher.evaluate_offer(
                article=offer.article,
                external_sku=offer.external_sku,
                brand_name=brand_result.canonical_brand or offer.brand_name,
                source=source,
                supplier=source.supplier,
            )
            product = decision.matched_product
            candidate_product_ids = [str(item.id) for item in decision.candidate_products]
            skip_reason = ""
            is_valid = True

            if offer.price is None:
                is_valid = False
                skip_reason = "missing_price"
            elif decision.status != SupplierRawOffer.MATCH_STATUS_AUTO_MATCHED:
                is_valid = False
                skip_reason = decision.reason or decision.status
            elif product is None:
                is_valid = False
                skip_reason = decision.reason or "product_not_found"

            now = timezone.now()
            raw_offer = SupplierRawOffer.objects.create(
                run=run,
                source=source,
                supplier=source.supplier,
                artifact=artifact,
                row_number=row_index,
                external_sku=offer.external_sku[:128],
                article=offer.article[:128],
                normalized_article=article_result.normalized_article[:128],
                brand_name=offer.brand_name[:180],
                normalized_brand=brand_result.normalized_brand[:180],
                product_name=offer.product_name[:255],
                currency=offer.currency[:3],
                price=offer.price,
                stock_qty=offer.stock_qty,
                lead_time_days=offer.lead_time_days,
                matched_product=product,
                match_status=decision.status,
                match_reason=decision.reason,
                match_candidate_product_ids=candidate_product_ids,
                matching_attempts=1,
                last_matched_at=now,
                article_normalization_trace=article_result.trace,
                brand_normalization_trace=brand_result.trace,
                is_valid=is_valid,
                skip_reason=skip_reason,
                raw_payload=offer.raw_payload,
            )
            OfferMatchReview.objects.create(
                raw_offer=raw_offer,
                action=OfferMatchReview.ACTION_AUTO_ATTEMPT,
                status_before="",
                status_after=decision.status,
                reason=decision.reason,
                candidate_product_ids=candidate_product_ids,
                selected_product=product,
            )

            utr_detail_id = self._extract_utr_detail_id(source=source, raw_payload=offer.raw_payload)
            if not dry_run and product is not None and utr_detail_id:
                self._attach_utr_detail_id(product=product, utr_detail_id=utr_detail_id)

            if not is_valid or product is None or offer.price is None:
                skipped += 1
                self._create_row_error(
                    run=run,
                    source=source,
                    artifact=artifact,
                    row_number=row_index,
                    external_sku=offer.external_sku,
                    error_code=skip_reason or "invalid_row",
                    message=f"Offer skipped: {skip_reason or 'invalid_row'}.",
                    raw_payload=offer.raw_payload,
                )
                errors_count += 1
                continue

            if not dry_run:
                _, was_created = supplier_offer_sync.upsert_from_raw_offer(raw_offer)
                if was_created:
                    created += 1
                else:
                    updated += 1
                affected_products.add(str(product.id))
            else:
                supplier_sku = (offer.external_sku or offer.article)[:128]
                existing = SupplierOffer.objects.filter(
                    supplier=source.supplier,
                    product=product,
                    supplier_sku=supplier_sku,
                ).first()
                if existing is None:
                    created += 1
                else:
                    updated += 1

        return created, updated, skipped, errors_count, affected_products

    def _extract_utr_detail_id(self, *, source: ImportSource, raw_payload: dict) -> str:
        if source.code != "utr":
            return ""
        # UTR detail id must come from detail payload (details[].id), not from SKU/article/table rows.
        if not isinstance(raw_payload.get("brand"), dict):
            return ""

        detail_id = raw_payload.get("id")
        text = str(detail_id or "").strip()
        if not text.isdigit():
            return ""
        return text

    def _attach_utr_detail_id(self, *, product: Product, utr_detail_id: str) -> None:
        if product.utr_detail_id == utr_detail_id:
            return
        if product.utr_detail_id:
            return
        product.utr_detail_id = utr_detail_id
        product.save(update_fields=("utr_detail_id", "updated_at"))

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
        ImportRowError.objects.create(
            run=run,
            source=source,
            artifact=artifact,
            row_number=row_number,
            external_sku=external_sku[:128],
            error_code=error_code[:64],
            message=message,
            raw_payload=raw_payload or {},
        )

    def _reprice_products(self, *, affected_product_ids: list[str], source: ImportSource, run: ImportRun) -> dict[str, int]:
        queryset = Product.objects.filter(id__in=affected_product_ids).select_related("brand", "category")
        stats = ProductRepricer().recalculate_products(
            queryset,
            source=PriceHistory.SOURCE_IMPORT,
            trigger_note=f"import:{source.code}:run:{run.id}",
        )
        run.summary["repricing"] = stats
        return stats

    def _resolve_run_status(self, run: ImportRun) -> str:
        if run.parsed_rows == 0 and run.errors_count > 0:
            return ImportRun.STATUS_FAILED
        if run.parsed_rows == 0:
            return ImportRun.STATUS_FAILED
        if run.errors_count > 0:
            return ImportRun.STATUS_PARTIAL
        return ImportRun.STATUS_SUCCESS

    def _as_result(self, run: ImportRun) -> ImportExecutionResult:
        summary = {
            "processed_rows": run.processed_rows,
            "parsed_rows": run.parsed_rows,
            "offers_created": run.offers_created,
            "offers_updated": run.offers_updated,
            "offers_skipped": run.offers_skipped,
            "errors_count": run.errors_count,
            "repriced_products": run.repriced_products,
            "reindexed_products": run.reindexed_products,
            "dry_run": run.dry_run,
            **(run.summary or {}),
        }
        return ImportExecutionResult(
            run_id=str(run.id),
            source_code=run.source.code,
            status=run.status,
            summary=summary,
        )

    def _finalize_source_timestamps(self, *, source: ImportSource, run: ImportRun) -> None:
        finished_at = run.finished_at or timezone.now()
        source.last_finished_at = finished_at
        if run.status in {ImportRun.STATUS_SUCCESS, ImportRun.STATUS_PARTIAL}:
            source.last_success_at = finished_at
        if run.status == ImportRun.STATUS_FAILED:
            source.last_failed_at = finished_at
        source.save(
            update_fields=(
                "last_finished_at",
                "last_success_at",
                "last_failed_at",
                "updated_at",
            )
        )
