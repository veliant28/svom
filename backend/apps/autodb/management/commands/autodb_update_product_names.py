from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.product_name_enrichment import AutoDbProductNameEnrichmentService, ProductNameEnrichmentResult
from apps.catalog.models import Product
from apps.search.services.product_indexer import ProductIndexer


@dataclass
class NameUpdateSummary:
    processed: int = 0
    updated: int = 0
    skipped_manual_locked: int = 0
    skipped_no_autodb_link: int = 0
    skipped_no_source_title: int = 0
    skipped_hash_unchanged: int = 0
    skipped_translations_present: int = 0
    skipped_other: int = 0
    translation_pending: int = 0
    translation_failed: int = 0


class Command(BaseCommand):
    help = "Update Product names from local Auto_DB_Pro article titles (uk/ru/en) with safe dry-run support."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--product-id", type=str, default="", help="Update one Product UUID")
        parser.add_argument("--only-missing-translations", action="store_true", help="Process only products with missing name_uk/name_ru/name_en")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
        parser.add_argument("--update-search-index", action="store_true", help="Reindex updated products in search backend")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        product_id = str(options.get("product_id") or "").strip()
        only_missing_translations = bool(options.get("only_missing_translations"))
        only_linked = bool(options.get("only_linked"))
        update_search_index = bool(options.get("update_search_index"))
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

        service = AutoDbProductNameEnrichmentService()
        qs = self._build_queryset(
            product_id=product_id,
            only_linked=only_linked,
            only_missing_translations=only_missing_translations,
        )
        if limit > 0:
            qs = qs[:limit]

        summary = NameUpdateSummary()
        updated_product_ids: list[str] = []

        self.stdout.write(
            "Auto_DB_Pro product name update started "
            f"dry_run={dry_run} only_linked={only_linked} only_missing_translations={only_missing_translations} "
            f"wait_for_autodb={wait_for_autodb}"
        )

        for product in qs.iterator(chunk_size=200):
            result = service.enrich_product(
                product=product,
                dry_run=dry_run,
                only_missing_translations=only_missing_translations,
            )
            summary.processed += 1
            self._print_result(result)
            self._accumulate(summary, result)
            if result.status == "updated":
                updated_product_ids.append(result.product_id)

        if update_search_index and updated_product_ids and not dry_run:
            reindex_stats = ProductIndexer().reindex_products(product_ids=updated_product_ids)
            self.stdout.write(
                "search reindex: "
                f"indexed={reindex_stats.get('indexed', 0)} errors={reindex_stats.get('errors', 0)} "
                f"total={reindex_stats.get('total', 0)} backend={reindex_stats.get('backend', 'unknown')}"
            )
        elif update_search_index and dry_run:
            self.stdout.write("search reindex: skipped (dry-run)")

        self.stdout.write("Auto_DB_Pro product name update summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- updated: {summary.updated}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- skipped_no_autodb_link: {summary.skipped_no_autodb_link}")
        self.stdout.write(f"- skipped_no_source_title: {summary.skipped_no_source_title}")
        self.stdout.write(f"- skipped_hash_unchanged: {summary.skipped_hash_unchanged}")
        self.stdout.write(f"- skipped_translations_present: {summary.skipped_translations_present}")
        self.stdout.write(f"- skipped_other: {summary.skipped_other}")
        self.stdout.write(f"- translation_pending: {summary.translation_pending}")
        self.stdout.write(f"- translation_failed: {summary.translation_failed}")
        self.stdout.write("- UTR calls: 0")

    def _build_queryset(self, *, product_id: str, only_linked: bool, only_missing_translations: bool):
        qs = Product.objects.select_related("category").order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if only_missing_translations:
            qs = qs.filter(
                Q(name_uk="")
                | Q(name_ru="")
                | Q(name_en="")
                | Q(name_translation_status__in=["", Product.NAME_TRANSLATION_PENDING, Product.NAME_TRANSLATION_FAILED])
            )
        if product_id:
            qs = qs.filter(pk=product_id)
        return qs

    def _print_result(self, result: ProductNameEnrichmentResult) -> None:
        self.stdout.write(
            f"- product_id={result.product_id} status={result.status} "
            f"old_name={result.old_name or '-'} supplier_raw_name={result.supplier_raw_name or '-'} "
            f"autodb_source_title={result.autodb_source_title or '-'} "
            f"name_uk={result.new_name_uk or '-'} name_ru={result.new_name_ru or '-'} name_en={result.new_name_en or '-'} "
            f"name_source={result.name_source or '-'} translation_status={result.translation_status or '-'} "
            f"source_hash={result.name_source_hash or '-'}"
        )
        if result.translation_error:
            self.stdout.write(f"  translation_error={result.translation_error}")

    def _accumulate(self, summary: NameUpdateSummary, result: ProductNameEnrichmentResult) -> None:
        if result.status == "updated":
            summary.updated += 1
        elif result.status == "skipped_manual_locked":
            summary.skipped_manual_locked += 1
        elif result.status == "skipped_no_autodb_link":
            summary.skipped_no_autodb_link += 1
        elif result.status == "skipped_no_source_title":
            summary.skipped_no_source_title += 1
        elif result.status == "skipped_hash_unchanged":
            summary.skipped_hash_unchanged += 1
        elif result.status == "skipped_translations_present":
            summary.skipped_translations_present += 1
        else:
            summary.skipped_other += 1

        if result.translation_status == Product.NAME_TRANSLATION_PENDING:
            summary.translation_pending += 1
        if result.translation_status == Product.NAME_TRANSLATION_FAILED:
            summary.translation_failed += 1
