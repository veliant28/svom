from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.catalog.models import Product
from apps.catalog.services import get_product_display_brand_payload
from apps.catalog.services.manual_chemical_categories import (
    MANUAL_CHEMICAL_CATEGORY_SPECS,
    STATUS_NEEDS_REVIEW,
    STATUS_SAFE,
    STATUS_SKIP,
    decide_manual_chemical_category,
    extract_manual_chemical_payload_fields,
)
from apps.supplier_imports.models import SupplierRawOffer


@dataclass
class AuditSummary:
    total_unlinked: int = 0
    safe_manual_category_candidate: int = 0
    needs_review: int = 0
    skip: int = 0


class Command(BaseCommand):
    help = "Read-only audit of unlinked GPL products for controlled manual car-chemical categorization."

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

        products = self._load_unlinked_products(supplier_code=supplier_code, limit=limit)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])

        summary = AuditSummary(total_unlinked=len(products))
        counts_by_category: Counter[str] = Counter()
        rows: list[dict[str, str]] = []

        self.stdout.write(
            "audit_manual_chemical_category_candidates started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'}"
        )

        for product in products:
            offer = raw_offer_map.get(str(product.id), {})
            payload = offer.get("raw_payload") if isinstance(offer, dict) else {}
            fields = extract_manual_chemical_payload_fields(payload if isinstance(payload, dict) else {})
            brand_payload = get_product_display_brand_payload(product)
            brand = str(offer.get("brand_name") or brand_payload.display_brand or getattr(product, "normalized_brand", "") or "")

            decision = decide_manual_chemical_category(
                product_name=str(product.name or ""),
                brand=brand,
                payload=fields,
            )

            if decision.status == STATUS_SAFE:
                summary.safe_manual_category_candidate += 1
                counts_by_category[decision.proposed_category] += 1
            elif decision.status == STATUS_NEEDS_REVIEW:
                summary.needs_review += 1
            else:
                summary.skip += 1

            rows.append(
                {
                    "product_id": str(product.id),
                    "raw_offer_id": str(offer.get("id") or ""),
                    "brand": brand,
                    "article": str(offer.get("article") or ""),
                    "product_name": str(product.name or ""),
                    "raw_category": fields.category,
                    "raw_group": fields.group,
                    "raw_name": fields.name,
                    "raw_description": fields.description,
                    "proposed_category": decision.proposed_category,
                    "confidence": f"{decision.confidence:.3f}",
                    "reason": decision.reason,
                    "status": decision.status,
                }
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("manual chemical category audit summary:")
        self.stdout.write(f"- total_unlinked: {summary.total_unlinked}")
        self.stdout.write(f"- safe_manual_category_candidate: {summary.safe_manual_category_candidate}")
        self.stdout.write(f"- needs_review: {summary.needs_review}")
        self.stdout.write(f"- skip: {summary.skip}")
        self.stdout.write("- counts_by_target_category:")
        for key, value in counts_by_category.most_common():
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _load_unlinked_products(self, *, supplier_code: str, limit: int) -> list[Product]:
        manual_chemical_slugs = [item.slug for item in MANUAL_CHEMICAL_CATEGORY_SPECS]
        qs = (
            Product.objects.select_related("brand", "category")
            .filter(raw_supplier_offers__source__code=supplier_code)
            .filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_key=""))
            .filter(Q(category__isnull=True) | Q(category__slug__in=manual_chemical_slugs))
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
            .values(
                "id",
                "matched_product_id",
                "brand_name",
                "article",
                "raw_payload",
            )
        )
        out: dict[str, dict] = {}
        for row in rows.iterator(chunk_size=500):
            key = str(row.get("matched_product_id") or "")
            if key and key not in out:
                out[key] = row
        return out

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "raw_offer_id",
            "brand",
            "article",
            "product_name",
            "raw_category",
            "raw_group",
            "raw_name",
            "raw_description",
            "proposed_category",
            "confidence",
            "reason",
            "status",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
