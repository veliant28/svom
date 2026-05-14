from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.pricing.models import SupplierOffer


class Command(BaseCommand):
    help = "Backfill GPL product SKU from GPL supplier offer SKU (remove GPL-... suffix format)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", default=False)
        parser.add_argument("--limit", type=int, default=0)

    def handle(self, *args, **options):
        apply_changes = bool(options.get("apply"))
        limit = max(int(options.get("limit") or 0), 0)

        offers = SupplierOffer.objects.select_related("product", "supplier").filter(
            supplier__code="gpl",
            product__isnull=False,
        )
        if limit:
            offers = offers[:limit]

        scanned = 0
        updated = 0
        skipped_empty = 0
        skipped_conflict = 0
        unchanged = 0

        for offer in offers.iterator(chunk_size=2000):
            scanned += 1
            product: Product = offer.product
            target_sku = str(offer.supplier_sku or "").strip()[:64]
            if not target_sku:
                skipped_empty += 1
                continue
            if str(product.sku or "").strip() == target_sku:
                unchanged += 1
                continue
            conflict = Product.objects.filter(sku=target_sku).exclude(id=product.id).exists()
            if conflict:
                skipped_conflict += 1
                continue
            updated += 1
            if apply_changes:
                product.sku = target_sku
                product.save(update_fields=["sku", "updated_at"])

        mode = "apply" if apply_changes else "dry-run"
        self.stdout.write(
            self.style.SUCCESS(
                f"backfill_gpl_product_sku_from_offer mode={mode} scanned={scanned} "
                f"updated={updated} unchanged={unchanged} skipped_empty={skipped_empty} skipped_conflict={skipped_conflict}"
            )
        )
