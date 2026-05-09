from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready
from apps.autodb.services.product_category_enrichment import AutoDbProductCategoryEnrichmentService, ProductCategoryEnrichmentResult
from apps.catalog.models import Product


@dataclass
class CategoryUpdateSummary:
    processed: int = 0
    updated: int = 0
    created_categories: int = 0
    reused_categories: int = 0
    skipped_no_autodb_link: int = 0
    skipped_no_autodb_category: int = 0
    skipped_manual_locked: int = 0
    skipped_suspicious_link: int = 0
    skipped_no_root_mapping: int = 0
    skipped_parent_missing: int = 0
    translation_pending: int = 0
    root_mapping_stats: dict[str, int] | None = None
    child_categories_created: int = 0
    child_categories_reused: int = 0
    autodb_root_category_creation_blocked: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Update Product.category from local Auto_DB_Pro prd mapping for linked products."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--product-id", type=str, default="", help="Update one Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
        parser.add_argument("--only-missing", action="store_true", help="Process only products with non-Auto_DB category")
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

        service = AutoDbProductCategoryEnrichmentService()
        qs = self._build_queryset(
            service=service,
            product_id=product_id,
            only_linked=only_linked,
            only_missing=only_missing,
        )
        if limit > 0:
            qs = qs[:limit]

        summary = CategoryUpdateSummary()

        self.stdout.write(
            "Auto_DB_Pro product category update started "
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
            self._print_result(result)
            self._accumulate(summary, result)

        self.stdout.write("Auto_DB_Pro product category update summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- updated: {summary.updated}")
        self.stdout.write(f"- created_categories: {summary.created_categories}")
        self.stdout.write(f"- reused_categories: {summary.reused_categories}")
        self.stdout.write(f"- skipped_no_autodb_link: {summary.skipped_no_autodb_link}")
        self.stdout.write(f"- skipped_no_autodb_category: {summary.skipped_no_autodb_category}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- skipped_suspicious_link: {summary.skipped_suspicious_link}")
        self.stdout.write(f"- skipped_no_root_mapping: {summary.skipped_no_root_mapping}")
        self.stdout.write(f"- skipped_parent_missing: {summary.skipped_parent_missing}")
        self.stdout.write(f"- translation_pending: {summary.translation_pending}")
        self.stdout.write(f"- child_categories_created: {summary.child_categories_created}")
        self.stdout.write(f"- child_categories_reused: {summary.child_categories_reused}")
        self.stdout.write(f"- autodb_root_category_creation_blocked: {summary.autodb_root_category_creation_blocked}")
        if summary.root_mapping_stats:
            self.stdout.write("- root_mapping_stats:")
            for root_name, count in sorted(summary.root_mapping_stats.items()):
                self.stdout.write(f"  - {root_name}: {count}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- UTR calls: 0")

    def _build_queryset(
        self,
        *,
        service: AutoDbProductCategoryEnrichmentService,
        product_id: str,
        only_linked: bool,
        only_missing: bool,
    ):
        return service.build_queryset(
            product_id=product_id,
            only_linked=only_linked,
            only_missing=only_missing,
        )

    def _print_result(self, result: ProductCategoryEnrichmentResult) -> None:
        self.stdout.write(
            f"- product_id={result.product_id} status={result.status} "
            f"old_category={result.old_category_name or '-'}({result.old_category_id or '-'}) "
            f"new_category={result.new_category_name or '-'}({result.new_category_id or '-'}) "
            f"prd_id={result.chosen_prd_id or '-'} source={result.chosen_source or '-'} "
            f"mapped_root={result.mapped_root_name or '-'}({result.mapped_root_slug or '-'}) "
            f"article_title={result.autodb_article_title or '-'} prd_title={result.autodb_prd_title or '-'} "
            f"created_category={result.created_category} reused_category={result.reused_category} "
            f"parent_missing={result.parent_missing} translation_pending={result.translation_pending} suspicious_link={result.suspicious_link}"
        )
        if result.warning:
            self.stdout.write(f"  warning={result.warning}")
        if result.error:
            self.stdout.write(f"  error={result.error}")

    def _accumulate(self, summary: CategoryUpdateSummary, result: ProductCategoryEnrichmentResult) -> None:
        if result.status == "updated":
            summary.updated += 1
        elif result.status == "skipped_no_autodb_link":
            summary.skipped_no_autodb_link += 1
        elif result.status == "skipped_no_autodb_category":
            summary.skipped_no_autodb_category += 1
        elif result.status == "skipped_manual_locked":
            summary.skipped_manual_locked += 1
        elif result.status == "skipped_suspicious_link":
            summary.skipped_suspicious_link += 1
        elif result.status == "skipped_no_root_mapping":
            summary.skipped_no_root_mapping += 1
            summary.autodb_root_category_creation_blocked += 1

        if result.created_category:
            summary.created_categories += 1
            summary.child_categories_created += 1
        if result.reused_category:
            summary.reused_categories += 1
            summary.child_categories_reused += 1
        if result.parent_missing:
            summary.skipped_parent_missing += 1
        if result.translation_pending:
            summary.translation_pending += 1
        root_name = str(result.mapped_root_name or "").strip()
        if root_name:
            if summary.root_mapping_stats is None:
                summary.root_mapping_stats = {}
            summary.root_mapping_stats[root_name] = int(summary.root_mapping_stats.get(root_name, 0)) + 1
