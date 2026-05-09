from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db.models import Sum

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer


@dataclass
class RecalculateSummary:
    processed: int = 0
    updated: int = 0
    skipped_unchanged: int = 0
    products_with_offer_stock: int = 0
    total_stock_before: int = 0
    total_stock_after: int = 0
    price_cache_updated: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Recalculate Product.available_stock_qty_cached from active SupplierOffer.stock_qty."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        limit = int(options["limit"] or 0)
        only_linked = bool(options["only_linked"])
        verbosity_raw = options.get("verbosity", 1)
        verbosity = 1 if verbosity_raw is None else int(verbosity_raw)

        queryset = Product.objects.order_by("id")
        if only_linked:
            queryset = queryset.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_number="")
        if limit > 0:
            queryset = queryset[:limit]

        products = list(queryset.only("id", "available_stock_qty_cached"))
        product_ids = [str(product.id) for product in products]

        totals = {
            str(row["product_id"]): int(row["total"] or 0)
            for row in (
                SupplierOffer.objects.filter(
                    product_id__in=product_ids,
                    is_available=True,
                    stock_qty__gt=0,
                )
                .values("product_id")
                .annotate(total=Sum("stock_qty"))
            )
        }

        summary = RecalculateSummary()
        to_update: list[Product] = []

        self.stdout.write(
            f"Product offer stock cache recalculation started dry_run={dry_run} "
            f"only_linked={only_linked} limit={limit if limit > 0 else 'all'}"
        )

        for product in products:
            summary.processed += 1
            before = int(product.available_stock_qty_cached or 0)
            after = int(totals.get(str(product.id), 0))
            summary.total_stock_before += before
            summary.total_stock_after += after
            if after > 0:
                summary.products_with_offer_stock += 1

            if before == after:
                summary.skipped_unchanged += 1
                if verbosity >= 2:
                    self.stdout.write(f"- product_id={product.id} status=skipped_unchanged stock={after}")
                continue

            summary.updated += 1
            if verbosity >= 1:
                self.stdout.write(f"- product_id={product.id} status=updated before={before} after={after}")
            if not dry_run:
                product.available_stock_qty_cached = after
                to_update.append(product)

        if not dry_run and to_update:
            Product.objects.bulk_update(to_update, fields=["available_stock_qty_cached"], batch_size=1000)

        self.stdout.write("Product offer stock cache recalculation summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- updated: {summary.updated}")
        self.stdout.write(f"- skipped_unchanged: {summary.skipped_unchanged}")
        self.stdout.write(f"- products_with_offer_stock: {summary.products_with_offer_stock}")
        self.stdout.write(f"- total_stock_before: {summary.total_stock_before}")
        self.stdout.write(f"- total_stock_after: {summary.total_stock_after}")
        self.stdout.write(f"- price_cache_updated: {summary.price_cache_updated}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- UTR calls: 0")
