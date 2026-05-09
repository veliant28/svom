from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils.text import slugify

from apps.catalog.models import Product
from apps.catalog.services import generate_unique_product_slug
from apps.pricing.models import SupplierOffer


@dataclass
class RepairSummary:
    processed: int = 0
    skipped_price_guard_publish: int = 0
    slug_created: int = 0
    cache_fixed: int = 0
    skipped_already_ok: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Repair GPL product supporting fields without bypassing ProductPrice activity guard."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="gpl", help="Supplier code to target (default: gpl)")
        parser.add_argument("--limit", type=int, default=0, help="Limit products count")
        parser.add_argument("--dry-run", action="store_true", help="Show changes without saving")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "gpl").strip().lower()
        limit = max(int(options.get("limit") or 0), 0)
        dry_run = bool(options.get("dry_run"))

        queryset = (
            Product.objects.filter(supplier_offers__supplier__code__iexact=supplier_code)
            .distinct()
            .order_by("id")
            .only("id", "name", "sku", "slug", "is_active", "published_at", "available_stock_qty_cached")
        )
        if limit > 0:
            queryset = queryset[:limit]
        products = list(queryset)
        product_ids = [str(item.id) for item in products]

        stock_totals = {
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

        summary = RepairSummary()
        self.stdout.write(
            "GPL public visibility repair started "
            f"supplier={supplier_code} dry_run={dry_run} limit={limit if limit > 0 else 'all'}"
        )

        for product in products:
            summary.processed += 1
            target_stock = int(stock_totals.get(str(product.id), 0))
            needs_publish = (not product.is_active) or (product.published_at is None)
            needs_slug = not str(product.slug or "").strip()
            needs_cache = int(product.available_stock_qty_cached or 0) != target_stock

            if not needs_publish and not needs_slug and not needs_cache:
                summary.skipped_already_ok += 1
                continue

            if needs_publish:
                summary.skipped_price_guard_publish += 1
            if needs_slug:
                summary.slug_created += 1
            if needs_cache:
                summary.cache_fixed += 1

            if dry_run:
                continue

            try:
                changed_fields: list[str] = []
                # Never bypass pricing activity guard by forcing visibility flags.
                if needs_slug:
                    preferred_slug = slugify(f"{product.name}-{product.sku}")[:300]
                    product.slug = generate_unique_product_slug(name=product.name, preferred_slug=preferred_slug)
                    changed_fields.append("slug")
                if needs_cache:
                    product.available_stock_qty_cached = target_stock
                    changed_fields.append("available_stock_qty_cached")

                if changed_fields:
                    product.save(update_fields=[*changed_fields, "updated_at"])
            except Exception:
                summary.failed += 1

        self.stdout.write("GPL public visibility repair summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- skipped_price_guard_publish: {summary.skipped_price_guard_publish}")
        self.stdout.write(f"- slug_created: {summary.slug_created}")
        self.stdout.write(f"- cache_fixed: {summary.cache_fixed}")
        self.stdout.write(f"- skipped_already_ok: {summary.skipped_already_ok}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- UTR calls=0")
