from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbProductBrandEnrichmentService
from apps.autodb.services.local_db_readiness import wait_for_local_autodb_ready


@dataclass
class BrandDiagnoseSummary:
    processed: int = 0
    linked_products: int = 0
    products_with_autodb_supplier_id: int = 0
    products_missing_autodb_supplier_id: int = 0
    products_with_current_brand: int = 0
    products_with_raw_brand_only: int = 0
    products_where_current_brand_differs_from_autodb: int = 0
    products_where_autodb_supplier_missing_local: int = 0
    products_where_brand_would_update: int = 0
    manual_locked_brands_count: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Diagnose Product brand source and canonical Auto_DB_Pro supplier brand mapping."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100, help="Limit products count")
        parser.add_argument("--product-id", type=str, default="", help="Inspect one Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Inspect only linked products")
        parser.add_argument("--all", dest="all_products", action="store_true", help="Inspect all products")
        parser.add_argument("--export-csv", type=str, default="", help="Export diagnostics rows to CSV path")
        parser.add_argument(
            "--wait-for-autodb",
            type=int,
            default=0,
            help="Wait up to N seconds for local Auto_DB_Pro DB readiness before processing.",
        )

    def handle(self, *args, **options):
        limit = max(int(options.get("limit") or 0), 0)
        only_linked = bool(options.get("only_linked"))
        all_products = bool(options.get("all_products"))
        product_id = str(options.get("product_id") or "").strip()
        export_csv = str(options.get("export_csv") or "").strip()
        wait_for_autodb = max(int(options.get("wait_for_autodb") or 0), 0)

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
        qs = service.build_queryset(only_linked=only_linked, include_all=all_products, product_id=product_id)
        if limit > 0:
            qs = qs[:limit]
        products = list(qs.iterator(chunk_size=500))

        supplier_ids = {
            int(item.autodb_supplier_id)
            for item in products
            if getattr(item, "autodb_supplier_id", None) not in (None, "")
        }
        service.prime_supplier_cache(supplier_ids=supplier_ids)

        rows: list[dict[str, str]] = []
        summary = BrandDiagnoseSummary()
        self.stdout.write(
            "Auto_DB_Pro product brand diagnostics started "
            f"only_linked={only_linked} all_products={all_products} limit={limit or 'none'} wait_for_autodb={wait_for_autodb}"
        )

        for product in products:
            try:
                diagnostics = service.diagnose_product(product=product)
            except Exception as exc:  # noqa: BLE001
                summary.failed += 1
                self.stdout.write(f"- product_id={getattr(product, 'id', '-')}: failed error={exc}")
                continue

            summary.processed += 1
            linked = diagnostics.autodb_supplier_id is not None
            if linked:
                summary.linked_products += 1
                summary.products_with_autodb_supplier_id += 1
            else:
                summary.products_missing_autodb_supplier_id += 1
            if diagnostics.current_brand_name:
                summary.products_with_current_brand += 1
            if (not diagnostics.current_brand_name) and diagnostics.raw_supplier_brand_examples:
                summary.products_with_raw_brand_only += 1
            if diagnostics.autodb_supplier_name and diagnostics.current_brand_name and diagnostics.autodb_supplier_name != diagnostics.current_brand_name:
                summary.products_where_current_brand_differs_from_autodb += 1
            if linked and not diagnostics.autodb_supplier_name:
                summary.products_where_autodb_supplier_missing_local += 1
            if diagnostics.would_update:
                summary.products_where_brand_would_update += 1
            if bool(getattr(product, "brand_manually_locked", False)):
                summary.manual_locked_brands_count += 1

            row = {
                "product_id": diagnostics.product_id,
                "product_name": diagnostics.product_name,
                "current_brand_name": diagnostics.current_brand_name,
                "current_brand_id": diagnostics.current_brand_id,
                "autodb_supplier_id": str(diagnostics.autodb_supplier_id or ""),
                "autodb_article_key": diagnostics.autodb_article_key,
                "autodb_supplier_name": diagnostics.autodb_supplier_name,
                "supplier_raw_brand_examples": " | ".join(diagnostics.raw_supplier_brand_examples),
                "proposed_brand_name": diagnostics.proposed_brand_name,
                "proposed_brand_source": diagnostics.proposed_brand_source,
                "status": diagnostics.status,
                "reason": diagnostics.reason,
                "would_update": "1" if diagnostics.would_update else "0",
            }
            rows.append(row)

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("Auto_DB_Pro product brand diagnostics summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- linked_products: {summary.linked_products}")
        self.stdout.write(f"- products_with_autodb_supplier_id: {summary.products_with_autodb_supplier_id}")
        self.stdout.write(f"- products_missing_autodb_supplier_id: {summary.products_missing_autodb_supplier_id}")
        self.stdout.write(f"- products_with_current_brand: {summary.products_with_current_brand}")
        self.stdout.write(f"- products_with_raw_brand_only: {summary.products_with_raw_brand_only}")
        self.stdout.write(f"- products_where_current_brand_differs_from_autodb: {summary.products_where_current_brand_differs_from_autodb}")
        self.stdout.write(f"- products_where_autodb_supplier_missing_local: {summary.products_where_autodb_supplier_missing_local}")
        self.stdout.write(f"- products_where_brand_would_update: {summary.products_where_brand_would_update}")
        self.stdout.write(f"- manual_locked brands count: {summary.manual_locked_brands_count}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out_path = Path(path)
        if out_path.parent and not out_path.parent.exists():
            out_path.parent.mkdir(parents=True, exist_ok=True)

        headers = [
            "product_id",
            "product_name",
            "current_brand_name",
            "current_brand_id",
            "autodb_supplier_id",
            "autodb_article_key",
            "autodb_supplier_name",
            "supplier_raw_brand_examples",
            "proposed_brand_name",
            "proposed_brand_source",
            "status",
            "reason",
            "would_update",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
