from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand

from apps.autodb.services.local_db_readiness import is_local_autodb_unavailable_error, wait_for_local_autodb_ready
from apps.autodb.services.product_fitment_enrichment import AutoDbProductFitmentEnrichmentService


@dataclass
class ProductFitmentUpdateSummary:
    processed: int = 0
    products_with_fitments: int = 0
    fitments_created: int = 0
    fitments_updated: int = 0
    stale_marked: int = 0
    skipped_no_autodb_link: int = 0
    skipped_no_article_li: int = 0
    skipped_non_passenger_car: int = 0
    skipped_missing_passanger_car: int = 0
    skipped_manual_locked: int = 0
    failed: int = 0
    aborted: bool = False
    abort_reason: str = ""
    db_error: str = ""


class Command(BaseCommand):
    help = "Update Product fitments from local Auto_DB_Pro article_li for linked products."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--product-id", type=str, default="", help="Process one Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
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
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)
        limit = max(int(options.get("limit") or 0), 0)

        service = AutoDbProductFitmentEnrichmentService()
        qs = service.build_queryset(product_id=product_id, only_linked=only_linked)
        if limit > 0:
            qs = qs[:limit]

        summary = ProductFitmentUpdateSummary()
        self.stdout.write(
            "Auto_DB_Pro product fitment update started "
            f"dry_run={dry_run} only_linked={only_linked} wait_for_autodb={wait_for_autodb}"
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
                result = service.enrich_product(product=product, dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001
                summary.processed += 1
                summary.failed += 1
                if not summary.db_error and is_local_autodb_unavailable_error(str(exc)):
                    summary.db_error = str(exc)
                self.stdout.write(f"- product_id={product.id} status=failed error={exc}")
                continue

            summary.processed += 1
            if result.has_fitments:
                summary.products_with_fitments += 1
            summary.fitments_created += result.fitments_created
            summary.fitments_updated += result.fitments_updated
            summary.stale_marked += result.stale_marked
            if result.skipped_no_autodb_link:
                summary.skipped_no_autodb_link += 1
            if result.skipped_no_article_li:
                summary.skipped_no_article_li += 1
            if result.skipped_non_passenger_car:
                summary.skipped_non_passenger_car += 1
            if result.skipped_missing_passanger_car:
                summary.skipped_missing_passanger_car += 1
            if result.skipped_manual_locked:
                summary.skipped_manual_locked += 1

            self.stdout.write(
                f"- product_id={product.id} status={result.status} "
                f"has_fitments={result.has_fitments} fitments_created={result.fitments_created} "
                f"fitments_updated={result.fitments_updated} stale_marked={result.stale_marked} "
                f"skipped_manual_locked={result.skipped_manual_locked}"
            )

        self._print_summary(summary)

    def _print_summary(self, summary: ProductFitmentUpdateSummary) -> None:
        self.stdout.write("Auto_DB_Pro product fitment update summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- products_with_fitments: {summary.products_with_fitments}")
        self.stdout.write(f"- fitments_created: {summary.fitments_created}")
        self.stdout.write(f"- fitments_updated: {summary.fitments_updated}")
        self.stdout.write(f"- stale_marked: {summary.stale_marked}")
        self.stdout.write(f"- skipped_no_autodb_link: {summary.skipped_no_autodb_link}")
        self.stdout.write(f"- skipped_no_article_li: {summary.skipped_no_article_li}")
        self.stdout.write(f"- skipped_non_passenger_car: {summary.skipped_non_passenger_car}")
        self.stdout.write(f"- skipped_missing_passanger_car: {summary.skipped_missing_passanger_car}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write(f"- aborted: {summary.aborted}")
        self.stdout.write(f"- abort_reason: {summary.abort_reason or '-'}")
        self.stdout.write(f"- db_error: {summary.db_error or '-'}")
        self.stdout.write("- UTR calls: 0")
