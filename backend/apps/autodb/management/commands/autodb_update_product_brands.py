from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbProductBrandEnrichmentService
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready


@dataclass
class ProductBrandUpdateSummary:
    processed: int = 0
    updated: int = 0
    skipped_hash_unchanged: int = 0
    skipped_no_autodb_link: int = 0
    skipped_no_autodb_supplier_id: int = 0
    skipped_supplier_missing_local: int = 0
    skipped_manual_locked: int = 0
    skipped_no_source_brand: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Update Product display brand from local Auto_DB_Pro suppliers by autodb_supplier_id."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--product-id", type=str, default="", help="Process one Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
        parser.add_argument("--all", dest="all_products", action="store_true", help="Process all products")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        only_linked = bool(options.get("only_linked"))
        all_products = bool(options.get("all_products"))
        product_id = str(options.get("product_id") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        limit = max(int(options.get("limit") or 0), 0)
        if only_linked and all_products:
            raise CommandError("Use either --only-linked or --all, not both.")

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            raise CommandError(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds} "
                f"error={readiness.error_message or '-'}"
            )

        service = AutoDbProductBrandEnrichmentService()
        include_all = all_products or (not only_linked)
        qs = service.build_queryset(only_linked=only_linked, include_all=include_all, product_id=product_id)
        if limit > 0:
            qs = qs[:limit]
        products = list(qs.iterator(chunk_size=500))
        supplier_ids = {
            int(item.autodb_supplier_id)
            for item in products
            if getattr(item, "autodb_supplier_id", None) not in (None, "")
        }
        service.prime_supplier_cache(supplier_ids=supplier_ids)

        summary = ProductBrandUpdateSummary()
        self.stdout.write(
            "Auto_DB_Pro product brand update started "
            f"dry_run={dry_run} only_linked={only_linked} all_products={all_products} wait_for_autodb={wait_for_autodb}"
        )

        for product in products:
            try:
                result = service.enrich_product(product=product, dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001
                summary.processed += 1
                summary.failed += 1
                self.stdout.write(f"- product_id={getattr(product, 'id', '-')} status=failed error={exc}")
                continue

            summary.processed += 1
            self.stdout.write(
                f"- product_id={result.product_id} status={result.status} autodb_supplier_id={result.autodb_supplier_id or '-'} "
                f"old_brand={result.old_brand_name or '-'} new_brand={result.new_brand_name or '-'} "
                f"brand_source={result.brand_source or '-'} reason={result.reason or '-'} "
                f"raw_supplier_brand_examples={' | '.join(result.raw_supplier_brand_examples) or '-'}"
            )
            self._accumulate(summary=summary, status=result.status)

        self.stdout.write("Auto_DB_Pro product brand update summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- updated: {summary.updated}")
        self.stdout.write(f"- skipped_hash_unchanged: {summary.skipped_hash_unchanged}")
        self.stdout.write(f"- skipped_no_autodb_link: {summary.skipped_no_autodb_link}")
        self.stdout.write(f"- skipped_no_autodb_supplier_id: {summary.skipped_no_autodb_supplier_id}")
        self.stdout.write(f"- skipped_supplier_missing_local: {summary.skipped_supplier_missing_local}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- skipped_no_source_brand: {summary.skipped_no_source_brand}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _accumulate(self, *, summary: ProductBrandUpdateSummary, status: str) -> None:
        if status == "updated":
            summary.updated += 1
        elif status == "skipped_hash_unchanged":
            summary.skipped_hash_unchanged += 1
        elif status == "skipped_no_autodb_link":
            summary.skipped_no_autodb_link += 1
        elif status == "skipped_no_autodb_supplier_id":
            summary.skipped_no_autodb_supplier_id += 1
        elif status == "skipped_supplier_missing_local":
            summary.skipped_supplier_missing_local += 1
        elif status == "skipped_manual_locked":
            summary.skipped_manual_locked += 1
        elif status == "skipped_no_source_brand":
            summary.skipped_no_source_brand += 1
