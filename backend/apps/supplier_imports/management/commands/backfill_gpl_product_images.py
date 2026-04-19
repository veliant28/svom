from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.supplier_imports.services.mapped_offer_publish.backfill import backfill_gpl_product_images


class Command(BaseCommand):
    help = "Backfill missing product images for GPL-published catalog products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate image backfill without writing ProductImage records.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional max count of candidate products to process.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=400,
            help="Download batch size per iteration.",
        )
        parser.add_argument(
            "--max-workers",
            type=int,
            default=10,
            help="Parallel download workers.",
        )
        parser.add_argument(
            "--include-needs-review",
            action="store_true",
            help="Include raw offers in needs_review mapping status as fallback candidates.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        limit = options.get("limit")
        batch_size = options.get("batch_size", 400)
        max_workers = options.get("max_workers", 10)
        include_needs_review = options.get("include_needs_review", False)

        self.stdout.write(
            "Starting GPL image backfill "
            f"(dry_run={dry_run}, limit={limit}, batch_size={batch_size}, max_workers={max_workers})..."
        )

        def report_progress(payload: dict[str, int | str]) -> None:
            self.stdout.write(
                "  - progress: "
                f"{payload.get('processed_candidates', 0)}/{payload.get('total_candidates', 0)} "
                f"created={payload.get('created_images', 0)} "
                f"failed={payload.get('failed_downloads', 0)} "
                f"skipped_existing={payload.get('skipped_existing', 0)}"
            )

        result = backfill_gpl_product_images(
            dry_run=dry_run,
            limit=limit,
            batch_size=batch_size,
            max_workers=max_workers,
            include_needs_review=include_needs_review,
            progress_callback=report_progress,
        )

        summary = result.as_dict()
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(style("GPL image backfill finished."))
        for key in (
            "rows_scanned",
            "unique_latest_rows",
            "eligible_rows",
            "initial_missing_products",
            "products_considered",
            "candidates_collected",
            "created_images",
            "failed_downloads",
            "skipped_existing",
            "skipped_no_product",
            "missing_image_url",
            "remaining_missing_products",
        ):
            self.stdout.write(f"  - {key}: {summary[key]}")

        if summary["error_types"]:
            self.stdout.write(f"  - error_types: {summary['error_types']}")
        if summary["skip_reasons"]:
            self.stdout.write(f"  - skip_reasons: {summary['skip_reasons']}")
