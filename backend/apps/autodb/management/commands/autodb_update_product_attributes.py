from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.product_attribute_enrichment import (
    AutoDbProductAttributeEnrichmentService,
    ProductAttributeEnrichmentResult,
)


@dataclass
class AttributeUpdateSummary:
    processed: int = 0
    products_with_attributes: int = 0
    attributes_created: int = 0
    attributes_reused: int = 0
    values_created: int = 0
    product_attributes_created: int = 0
    product_attributes_updated: int = 0
    skipped_no_autodb_link: int = 0
    skipped_no_article_attributes: int = 0
    skipped_manual_locked: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Update Product attributes from local Auto_DB_Pro article_attributes for linked products."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--product-id", type=str, default="", help="Update one Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
        parser.add_argument("--only-missing", action="store_true", help="Process only products with missing ProductAttribute rows")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        product_id = str(options.get("product_id") or "").strip()
        only_linked = bool(options.get("only_linked"))
        only_missing = bool(options.get("only_missing"))
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        limit = max(int(options.get("limit") or 0), 0)

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds} "
                f"error={readiness.error_message or '-'}"
            )

        service = AutoDbProductAttributeEnrichmentService()
        qs = service.build_queryset(
            only_linked=only_linked,
            only_missing=only_missing,
            product_id=product_id,
        )
        if limit > 0:
            qs = qs[:limit]

        summary = AttributeUpdateSummary()

        self.stdout.write(
            "Auto_DB_Pro product attribute update started "
            f"dry_run={dry_run} only_linked={only_linked} only_missing={only_missing} wait_for_autodb={wait_for_autodb}"
        )

        for product in qs.iterator(chunk_size=200):
            try:
                result = service.enrich_product(product=product, dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001
                summary.failed += 1
                summary.processed += 1
                self.stdout.write(f"- product_id={product.id} status=failed error={exc}")
                continue

            summary.processed += 1
            self._accumulate(summary, result)
            self._print_result(result)

        self.stdout.write("Auto_DB_Pro product attribute update summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- products_with_attributes: {summary.products_with_attributes}")
        self.stdout.write(f"- attributes_created: {summary.attributes_created}")
        self.stdout.write(f"- attributes_reused: {summary.attributes_reused}")
        self.stdout.write(f"- values_created: {summary.values_created}")
        self.stdout.write(f"- product_attributes_created: {summary.product_attributes_created}")
        self.stdout.write(f"- product_attributes_updated: {summary.product_attributes_updated}")
        self.stdout.write(f"- skipped_no_autodb_link: {summary.skipped_no_autodb_link}")
        self.stdout.write(f"- skipped_no_article_attributes: {summary.skipped_no_article_attributes}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- UTR calls: 0")

    def _print_result(self, result: ProductAttributeEnrichmentResult) -> None:
        self.stdout.write(
            f"- product_id={result.product_id} status={result.status} "
            f"attributes_found={result.attributes_found} "
            f"attributes_created={result.attributes_created} attributes_reused={result.attributes_reused} "
            f"values_created={result.values_created} "
            f"product_attributes_created={result.product_attributes_created} "
            f"product_attributes_updated={result.product_attributes_updated} "
            f"skipped_manual_locked={result.skipped_manual_locked} translation_pending={result.translation_pending}"
        )
        if result.warning:
            self.stdout.write(f"  warning={result.warning}")
        if result.error:
            self.stdout.write(f"  error={result.error}")

    def _accumulate(self, summary: AttributeUpdateSummary, result: ProductAttributeEnrichmentResult) -> None:
        if result.attributes_found > 0:
            summary.products_with_attributes += 1

        summary.attributes_created += result.attributes_created
        summary.attributes_reused += result.attributes_reused
        summary.values_created += result.values_created
        summary.product_attributes_created += result.product_attributes_created
        summary.product_attributes_updated += result.product_attributes_updated

        if result.status == "skipped_no_autodb_link":
            summary.skipped_no_autodb_link += 1
        elif result.status == "skipped_no_article_attributes":
            summary.skipped_no_article_attributes += 1
        elif result.status == "skipped_manual_locked":
            summary.skipped_manual_locked += 1
