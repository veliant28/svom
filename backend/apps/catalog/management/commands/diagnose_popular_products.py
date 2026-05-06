from __future__ import annotations

from collections import Counter

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.catalog.selectors import get_public_products_queryset


class Command(BaseCommand):
    help = "Diagnose why popular products block may return zero rows."

    def handle(self, *args, **options):
        total_products = Product.objects.count()
        active_products = Product.objects.filter(is_active=True)
        published_products = Product.objects.exclude(published_at__isnull=True)
        with_stock = active_products.filter(
            supplier_offers__is_available=True,
            supplier_offers__stock_qty__gt=0,
        ).distinct()
        with_price = active_products.filter(product_price__final_price__gt=0)

        api_queryset = get_public_products_queryset()
        api_count = api_queryset.count()

        fallback_queryset = active_products.filter(
            supplier_offers__is_available=True,
            supplier_offers__stock_qty__gt=0,
            product_price__final_price__gt=0,
        ).distinct()
        fallback_count = fallback_queryset.count()

        reason_counter: Counter[str] = Counter()
        sample_lines: list[str] = []
        sample_limit = 20

        for product in Product.objects.select_related("product_price", "category").order_by("-updated_at", "id")[:500]:
            reasons: list[str] = []
            if not product.is_active:
                reasons.append("inactive")
            has_supplier_stock = product.supplier_offers.filter(is_available=True, stock_qty__gt=0).exists()
            if not has_supplier_stock:
                reasons.append("stock<=0")
            price_value = getattr(getattr(product, "product_price", None), "final_price", 0) or 0
            if float(price_value) <= 0:
                reasons.append("price<=0")
            if not product.category_id:
                reasons.append("missing_category")
            if not reasons:
                reasons.append("included")

            reason_label = ",".join(reasons)
            reason_counter[reason_label] += 1
            if reasons != ["included"] and len(sample_lines) < sample_limit:
                sample_lines.append(
                    f"  - id={product.id} slug={product.slug or '-'} reasons={reason_label} "
                    f"stock={product.available_stock_qty_cached} price={price_value}"
                )

        self.stdout.write("diagnose_popular_products:")
        self.stdout.write(f"- total products: {total_products}")
        self.stdout.write(f"- active products: {active_products.count()}")
        self.stdout.write(f"- published products: {published_products.count()}")
        self.stdout.write(f"- products with stock > 0: {with_stock.count()}")
        self.stdout.write(f"- products with price > 0: {with_price.count()}")
        self.stdout.write(f"- products passing current API queryset filters: {api_count}")
        self.stdout.write(f"- products passing fallback popular filters (active+stock+price): {fallback_count}")
        self.stdout.write("- top excluded reasons:")
        for reason, count in reason_counter.most_common(10):
            if reason == "included":
                continue
            self.stdout.write(f"  - {reason}: {count}")
        self.stdout.write("- first excluded samples:")
        if not sample_lines:
            self.stdout.write("  - none")
        else:
            for line in sample_lines:
                self.stdout.write(line)
        self.stdout.write(f"- current API response count: {api_count}")
        self.stdout.write(
            "- note: Auto_DB_Pro public compatibility filtering remains disabled/no-op for product list/detail."
        )
        self.stdout.write("- UTR calls: 0")
