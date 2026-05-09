from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.catalog.models import Product
from apps.catalog.services import get_product_display_brand_payload
from apps.catalog.services.supplier_category_fallback import (
    SupplierCategoryFallbackInput,
    SupplierCategoryToSiteRootMapper,
    extract_supplier_payload_fields,
)
from apps.supplier_imports.models import SupplierRawOffer


@dataclass
class DiagnoseSummary:
    total_unlinked: int = 0
    with_category: int = 0
    without_category: int = 0
    mapped_root_only: int = 0
    mapped_child_category: int = 0
    needs_review: int = 0
    skipped_unclear: int = 0
    non_auto_supplier_only: int = 0


class Command(BaseCommand):
    help = "Diagnose root category fallback mapping for unlinked products from supplier raw payloads."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max unlinked products to inspect")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV output path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")
        limit = max(int(options.get("limit") or 0), 0)
        export_csv = str(options.get("export_csv") or "").strip()

        mapper = SupplierCategoryToSiteRootMapper()
        products = self._load_unlinked_products(supplier_code=supplier_code, limit=limit)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])

        summary = DiagnoseSummary(total_unlinked=len(products))
        root_counter: Counter[str] = Counter()
        raw_category_counter: Counter[str] = Counter()
        raw_group_counter: Counter[str] = Counter()
        brand_counter: Counter[str] = Counter()
        rows: list[dict[str, str]] = []

        self.stdout.write(
            "Unlinked supplier categories diagnostics started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'}"
        )

        for product in products:
            brand_payload = get_product_display_brand_payload(product)
            offer_row = raw_offer_map.get(str(product.id), {})
            raw_payload = offer_row.get("raw_payload") if isinstance(offer_row, dict) else {}
            extracted = extract_supplier_payload_fields(raw_payload if isinstance(raw_payload, dict) else {})

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
            status = decision.status

            current_category = getattr(getattr(product, "category", None), "name", "") or ""
            if current_category:
                summary.with_category += 1
            else:
                summary.without_category += 1

            if status == SupplierCategoryToSiteRootMapper.STATUS_MAPPED_ROOT_ONLY:
                summary.mapped_root_only += 1
            elif status == SupplierCategoryToSiteRootMapper.STATUS_MAPPED_CHILD_CATEGORY:
                summary.mapped_child_category += 1
            elif status == SupplierCategoryToSiteRootMapper.STATUS_NEEDS_REVIEW:
                summary.needs_review += 1
            elif status == SupplierCategoryToSiteRootMapper.STATUS_NON_AUTO_SUPPLIER_ONLY:
                summary.non_auto_supplier_only += 1
            else:
                summary.skipped_unclear += 1

            if decision.proposed_root_name:
                root_counter[decision.proposed_root_name] += 1
            if extracted["raw_category"]:
                raw_category_counter[extracted["raw_category"]] += 1
            if extracted["raw_group"]:
                raw_group_counter[extracted["raw_group"]] += 1
            if brand_value:
                brand_counter[str(brand_value)] += 1

            row = {
                "product_id": str(product.id),
                "product_name": str(product.name or ""),
                "display_brand": str(brand_payload.display_brand or ""),
                "brand_source": str(brand_payload.brand_source or ""),
                "supplier_product_name": str(offer_row.get("product_name") or ""),
                "raw_category": extracted["raw_category"],
                "raw_group": extracted["raw_group"],
                "raw_name": extracted["raw_name"],
                "raw_description": extracted["raw_description"],
                "raw_article_td": extracted["raw_article_td"],
                "raw_code": extracted["raw_code"],
                "current_category": current_category,
                "proposed_root_category": decision.proposed_root_name,
                "proposed_root_slug": decision.proposed_root_slug,
                "proposed_child_category": decision.proposed_child_name,
                "confidence": f"{decision.confidence:.3f}",
                "reason": decision.reason,
                "status": decision.status,
            }
            rows.append(row)

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("Unlinked supplier categories diagnostics summary:")
        self.stdout.write(f"- total_unlinked: {summary.total_unlinked}")
        self.stdout.write(f"- with_category: {summary.with_category}")
        self.stdout.write(f"- without_category: {summary.without_category}")
        self.stdout.write(f"- mapped_root_only: {summary.mapped_root_only}")
        self.stdout.write(f"- mapped_child_category: {summary.mapped_child_category}")
        self.stdout.write(f"- needs_review: {summary.needs_review}")
        self.stdout.write(f"- skipped_unclear: {summary.skipped_unclear}")
        self.stdout.write(f"- non_auto_supplier_only: {summary.non_auto_supplier_only}")

        self.stdout.write("- counts_by_proposed_root:")
        for root_name, count in root_counter.most_common():
            self.stdout.write(f"  - {root_name}: {count}")

        self.stdout.write("- top_raw_categories:")
        for label, count in raw_category_counter.most_common(20):
            self.stdout.write(f"  - {label}: {count}")

        self.stdout.write("- top_raw_groups:")
        for label, count in raw_group_counter.most_common(20):
            self.stdout.write(f"  - {label}: {count}")

        self.stdout.write("- top_brands:")
        for label, count in brand_counter.most_common(20):
            self.stdout.write(f"  - {label}: {count}")

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

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "product_name",
            "display_brand",
            "brand_source",
            "supplier_product_name",
            "raw_category",
            "raw_group",
            "raw_name",
            "raw_description",
            "raw_article_td",
            "raw_code",
            "current_category",
            "proposed_root_category",
            "proposed_root_slug",
            "proposed_child_category",
            "confidence",
            "reason",
            "status",
        ]
        with export_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
