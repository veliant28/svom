from __future__ import annotations

import argparse
from dataclasses import dataclass

from django.core.management.base import BaseCommand

from apps.autodb.services.local_db_readiness import is_local_autodb_unavailable_error, wait_for_local_autodb_ready
from apps.autodb.services.product_image_enrichment import AutoDbProductImageEnrichmentService
from apps.catalog.models import Product
from apps.supplier_imports.services.gpl_images import GplProductImageService


@dataclass
class ProductImageUpdateSummary:
    processed: int = 0
    products_with_gpl_images: int = 0
    gpl_images_created: int = 0
    gpl_images_reused: int = 0
    products_with_autodb_images: int = 0
    autodb_images_created: int = 0
    autodb_images_reused: int = 0
    skipped_manual_primary: int = 0
    skipped_no_images: int = 0
    skipped_no_autodb_link: int = 0
    stale_marked: int = 0
    failed: int = 0
    aborted: bool = False
    abort_reason: str = ""
    db_error: str = ""


class Command(BaseCommand):
    help = "Update Product images from GPL raw payload and Auto_DB_Pro article_images."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--product-id", type=str, default="", help="Process one Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
        parser.add_argument(
            "--prefer-gpl",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="Prefer GPL images for GPL products.",
        )
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
        prefer_gpl = bool(options.get("prefer_gpl", True))
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        limit = max(int(options.get("limit") or 0), 0)

        gpl_service = GplProductImageService()
        autodb_service = AutoDbProductImageEnrichmentService()

        qs = Product.objects.select_related("brand", "category").prefetch_related("images").order_by("id")
        if only_linked:
            qs = qs.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if product_id:
            qs = qs.filter(pk=product_id)
        if limit > 0:
            qs = qs[:limit]

        summary = ProductImageUpdateSummary()
        self.stdout.write(
            "Auto_DB_Pro product image update started "
            f"dry_run={dry_run} only_linked={only_linked} prefer_gpl={prefer_gpl} wait_for_autodb={wait_for_autodb}"
        )

        readiness = wait_for_local_autodb_ready(timeout_seconds=wait_for_autodb, interval_seconds=2.0)
        if not readiness.ready:
            summary.aborted = True
            summary.abort_reason = "local_autodb_not_ready"
            summary.db_error = readiness.error_message
            self.stdout.write(
                "Auto_DB_Pro local DB is not ready/recovering. Retry later. "
                f"host={readiness.host} port={readiness.port} database={readiness.database} "
                f"reason={readiness.reason} attempts={readiness.attempts} waited_seconds={readiness.waited_seconds}"
            )
            if readiness.error_message:
                self.stdout.write(f"- db_error: {readiness.error_message}")
            self._print_summary(summary)
            return

        for product in qs.iterator(chunk_size=200):
            try:
                gpl_result = gpl_service.sync_product_images(product=product, dry_run=dry_run)
                autodb_result = autodb_service.sync_product_images(
                    product=product,
                    dry_run=dry_run,
                    prefer_gpl=prefer_gpl,
                )
            except Exception as exc:  # noqa: BLE001
                summary.processed += 1
                summary.failed += 1
                if not summary.db_error and is_local_autodb_unavailable_error(str(exc)):
                    summary.db_error = str(exc)
                self.stdout.write(f"- product_id={product.id} status=failed error={exc}")
                continue

            summary.processed += 1
            if gpl_result.has_candidates:
                summary.products_with_gpl_images += 1
            summary.gpl_images_created += gpl_result.created
            summary.gpl_images_reused += gpl_result.reused

            if autodb_result.has_candidates:
                summary.products_with_autodb_images += 1
            summary.autodb_images_created += autodb_result.created
            summary.autodb_images_reused += autodb_result.reused

            if gpl_result.skipped_manual_primary or autodb_result.skipped_manual_primary:
                summary.skipped_manual_primary += 1
            if autodb_result.skipped_no_autodb_link:
                summary.skipped_no_autodb_link += 1

            stale_for_product = gpl_result.stale_marked + autodb_result.stale_marked
            summary.stale_marked += stale_for_product

            if not gpl_result.has_candidates and not autodb_result.has_candidates:
                summary.skipped_no_images += 1

            status = "updated" if (gpl_result.created + autodb_result.created + stale_for_product) > 0 else "skipped_hash_unchanged"
            self.stdout.write(
                f"- product_id={product.id} status={status} "
                f"gpl_candidates={gpl_result.has_candidates} gpl_created={gpl_result.created} gpl_reused={gpl_result.reused} "
                f"autodb_candidates={autodb_result.has_candidates} autodb_created={autodb_result.created} autodb_reused={autodb_result.reused} "
                f"stale_marked={stale_for_product} skipped_manual_primary={gpl_result.skipped_manual_primary or autodb_result.skipped_manual_primary}"
            )

        self._print_summary(summary)

    def _print_summary(self, summary: ProductImageUpdateSummary) -> None:
        self.stdout.write("Auto_DB_Pro product image update summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- products_with_gpl_images: {summary.products_with_gpl_images}")
        self.stdout.write(f"- gpl_images_created: {summary.gpl_images_created}")
        self.stdout.write(f"- gpl_images_reused: {summary.gpl_images_reused}")
        self.stdout.write(f"- products_with_autodb_images: {summary.products_with_autodb_images}")
        self.stdout.write(f"- autodb_images_created: {summary.autodb_images_created}")
        self.stdout.write(f"- autodb_images_reused: {summary.autodb_images_reused}")
        self.stdout.write(f"- skipped_manual_primary: {summary.skipped_manual_primary}")
        self.stdout.write(f"- skipped_no_images: {summary.skipped_no_images}")
        self.stdout.write(f"- skipped_no_autodb_link: {summary.skipped_no_autodb_link}")
        self.stdout.write(f"- stale_marked: {summary.stale_marked}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write(f"- aborted: {summary.aborted}")
        self.stdout.write(f"- abort_reason: {summary.abort_reason or '-'}")
        self.stdout.write(f"- db_error: {summary.db_error or '-'}")
        self.stdout.write("- UTR calls: 0")
