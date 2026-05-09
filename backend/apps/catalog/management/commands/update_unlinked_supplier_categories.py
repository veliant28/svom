from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.catalog.models import Category, Product
from apps.catalog.services import get_product_display_brand_payload
from apps.catalog.services.supplier_category_fallback import (
    SupplierCategoryFallbackInput,
    SupplierCategoryToSiteRootMapper,
    extract_supplier_payload_fields,
)
from apps.supplier_imports.models import SupplierRawOffer


@dataclass
class UpdateSummary:
    processed: int = 0
    would_update: int = 0
    would_create_child_categories: int = 0
    would_reuse_root_categories: int = 0
    skipped_already_categorized: int = 0
    skipped_unclear: int = 0
    skipped_manual_locked: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Assign root categories to unlinked products from supplier payload mapping (safe dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max unlinked products to inspect")
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not update Product.category")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")
        limit = max(int(options.get("limit") or 0), 0)
        dry_run = bool(options.get("dry_run"))

        mapper = SupplierCategoryToSiteRootMapper()
        products = self._load_unlinked_products(supplier_code=supplier_code, limit=limit)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])
        manual_roots = {
            item.slug: item
            for item in Category.objects.filter(parent__isnull=True, source=Category.SOURCE_MANUAL)
        }

        summary = UpdateSummary()
        root_counter: Counter[str] = Counter()

        self.stdout.write(
            "Unlinked supplier categories update started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'} dry_run={int(dry_run)}"
        )

        for product in products:
            summary.processed += 1
            if bool(getattr(product, "category_manually_locked", False)):
                summary.skipped_manual_locked += 1
                self.stdout.write(f"- product_id={product.id} status=skipped_manual_locked reason=category_manually_locked")
                continue
            if getattr(product, "category_id", None):
                summary.skipped_already_categorized += 1
                self.stdout.write(f"- product_id={product.id} status=skipped_already_categorized reason=has_category")
                continue

            offer_row = raw_offer_map.get(str(product.id), {})
            raw_payload = offer_row.get("raw_payload") if isinstance(offer_row, dict) else {}
            extracted = extract_supplier_payload_fields(raw_payload if isinstance(raw_payload, dict) else {})
            brand_payload = get_product_display_brand_payload(product)
            brand_value = brand_payload.display_brand or str(getattr(product, "normalized_brand", "") or "")

            mapping_input = SupplierCategoryFallbackInput(
                product_name=str(product.name or ""),
                supplier_product_name=str(offer_row.get("product_name") or ""),
                raw_category=extracted["raw_category"],
                raw_group=extracted["raw_group"],
                raw_name=extracted["raw_name"],
                raw_description=extracted["raw_description"],
                raw_article_td=extracted["raw_article_td"],
                raw_code=extracted["raw_code"],
                display_brand=str(brand_value or ""),
            )
            decision = mapper.map(mapping_input)

            if decision.status not in {
                SupplierCategoryToSiteRootMapper.STATUS_MAPPED_ROOT_ONLY,
                SupplierCategoryToSiteRootMapper.STATUS_MAPPED_CHILD_CATEGORY,
            }:
                summary.skipped_unclear += 1
                self.stdout.write(
                    f"- product_id={product.id} status={decision.status} reason={decision.reason} confidence={decision.confidence:.3f}"
                )
                continue

            root_category = manual_roots.get(decision.proposed_root_slug)
            if root_category is None:
                summary.failed += 1
                self.stdout.write(
                    f"- product_id={product.id} status=failed reason=manual_root_not_found slug={decision.proposed_root_slug or '-'}"
                )
                continue

            summary.would_update += 1
            summary.would_reuse_root_categories += 1
            if decision.status == SupplierCategoryToSiteRootMapper.STATUS_MAPPED_CHILD_CATEGORY:
                summary.would_create_child_categories += 1
            root_counter[root_category.name] += 1

            self.stdout.write(
                f"- product_id={product.id} status=would_update root={root_category.name} "
                f"proposed_child={decision.proposed_child_name or '-'} confidence={decision.confidence:.3f} reason={decision.reason}"
            )

            if not dry_run:
                product.category = root_category
                product.save(update_fields=["category", "updated_at"])

        self.stdout.write("Unlinked supplier categories update summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- would_update: {summary.would_update}")
        self.stdout.write(f"- would_create_child_categories: {summary.would_create_child_categories}")
        self.stdout.write(f"- would_reuse_root_categories: {summary.would_reuse_root_categories}")
        self.stdout.write(f"- skipped_already_categorized: {summary.skipped_already_categorized}")
        self.stdout.write(f"- skipped_unclear: {summary.skipped_unclear}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- counts_by_proposed_root:")
        for root_name, count in root_counter.most_common():
            self.stdout.write(f"  - {root_name}: {count}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _load_unlinked_products(self, *, supplier_code: str, limit: int) -> list[Product]:
        qs = (
            Product.objects.select_related("category", "brand")
            .filter(raw_supplier_offers__source__code=supplier_code)
            .filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_key=""))
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]
        return list(qs)

    def _load_latest_raw_offer_map(self, *, supplier_code: str, product_ids: list[str]) -> dict[str, dict]:
        if not product_ids:
            return {}
        rows = (
            SupplierRawOffer.objects.filter(source__code=supplier_code, matched_product_id__in=product_ids)
            .order_by("matched_product_id", "-updated_at", "-id")
            .values("matched_product_id", "product_name", "brand_name", "raw_payload")
        )
        out: dict[str, dict] = {}
        for row in rows:
            key = str(row.get("matched_product_id") or "")
            if key and key not in out:
                out[key] = row
        return out
