from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.catalog.models import Category, Product
from apps.catalog.services import get_product_display_brand_payload
from apps.catalog.services.manual_chemical_categories import (
    MANUAL_CHEMICAL_CATEGORY_SPECS,
    MANUAL_CHEMICAL_ROOT_SLUG,
    STATUS_NEEDS_REVIEW,
    STATUS_SAFE,
    decide_manual_chemical_category,
    extract_manual_chemical_payload_fields,
)
from apps.supplier_imports.models import SupplierRawOffer


@dataclass
class AssignSummary:
    processed_unlinked: int = 0
    safe_candidates: int = 0
    would_assign: int = 0
    assigned: int = 0
    skipped_already_categorized: int = 0
    skipped_not_chemical: int = 0
    skipped_needs_review: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Assign controlled manual chemical child categories to unlinked products (safe, supports dry-run)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max unlinked products to inspect")
        parser.add_argument("--dry-run", action="store_true", help="Preview only, do not write Product.category")
        parser.add_argument("--min-confidence", type=float, default=0.9, help="Minimum confidence for assignment")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV output path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")
        limit = max(int(options.get("limit") or 0), 0)
        dry_run = bool(options.get("dry_run"))
        min_confidence = max(min(float(options.get("min_confidence") or 0.9), 1.0), 0.0)
        export_csv = str(options.get("export_csv") or "").strip()

        target_categories = self._load_target_categories()
        expected_targets = len(MANUAL_CHEMICAL_CATEGORY_SPECS)
        if len(target_categories) < expected_targets:
            raise CommandError(
                "Manual chemical categories are missing. Run seed_manual_chemical_categories first."
            )

        products = self._load_unlinked_products(supplier_code=supplier_code, limit=limit)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])

        summary = AssignSummary()
        counts_by_target: Counter[str] = Counter()
        rows: list[dict[str, str]] = []

        self.stdout.write(
            "assign_manual_chemical_categories started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'} dry_run={int(dry_run)} min_confidence={min_confidence:.2f}"
        )

        for product in products:
            summary.processed_unlinked += 1
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

            if decision.status == STATUS_NEEDS_REVIEW:
                summary.skipped_needs_review += 1
                rows.append(self._row_for(product=product, offer=offer, status=decision.status, reason=decision.reason, proposed=decision.proposed_category, confidence=decision.confidence))
                continue

            if decision.status != STATUS_SAFE or decision.confidence < min_confidence:
                summary.skipped_not_chemical += 1
                rows.append(self._row_for(product=product, offer=offer, status="skip", reason=decision.reason, proposed=decision.proposed_category, confidence=decision.confidence))
                continue

            summary.safe_candidates += 1
            target = target_categories.get(decision.proposed_slug)
            if target is None:
                summary.failed += 1
                rows.append(self._row_for(product=product, offer=offer, status="failed", reason="target_category_not_found", proposed=decision.proposed_category, confidence=decision.confidence))
                continue

            current_category = getattr(product, "category", None)
            if current_category is not None and str(current_category.id) == str(target.id):
                summary.skipped_already_categorized += 1
                rows.append(
                    self._row_for(
                        product=product,
                        offer=offer,
                        status="skip",
                        reason="already_categorized_same_target",
                        proposed=target.name,
                        confidence=decision.confidence,
                    )
                )
                continue

            summary.would_assign += 1
            counts_by_target[target.name] += 1

            if not dry_run:
                try:
                    with transaction.atomic():
                        product.category = target
                        product.save(update_fields=["category", "updated_at"])
                    summary.assigned += 1
                except Exception:  # noqa: BLE001
                    summary.failed += 1
                    rows.append(self._row_for(product=product, offer=offer, status="failed", reason="save_error", proposed=target.name, confidence=decision.confidence))
                    continue

            rows.append(self._row_for(product=product, offer=offer, status=STATUS_SAFE, reason=decision.reason, proposed=target.name, confidence=decision.confidence))

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("assign_manual_chemical_categories summary:")
        self.stdout.write(f"- processed_unlinked: {summary.processed_unlinked}")
        self.stdout.write(f"- safe_candidates: {summary.safe_candidates}")
        self.stdout.write(f"- would_assign: {summary.would_assign}")
        self.stdout.write(f"- skipped_already_categorized: {summary.skipped_already_categorized}")
        self.stdout.write(f"- skipped_not_chemical: {summary.skipped_not_chemical}")
        self.stdout.write(f"- skipped_needs_review: {summary.skipped_needs_review}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- counts_by_target_category:")
        for key, value in counts_by_target.most_common():
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _load_target_categories(self) -> dict[str, Category]:
        return {
            item.slug: item
            for item in Category.objects.filter(parent__slug=MANUAL_CHEMICAL_ROOT_SLUG, source=Category.SOURCE_MANUAL)
        }

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
            .values("id", "matched_product_id", "brand_name", "article", "raw_payload")
        )
        out: dict[str, dict] = {}
        for row in rows.iterator(chunk_size=500):
            key = str(row.get("matched_product_id") or "")
            if key and key not in out:
                out[key] = row
        return out

    def _row_for(
        self,
        *,
        product: Product,
        offer: dict,
        status: str,
        reason: str,
        proposed: str = "",
        confidence: float = 0.0,
    ) -> dict[str, str]:
        return {
            "product_id": str(product.id),
            "raw_offer_id": str(offer.get("id") or ""),
            "brand": str(offer.get("brand_name") or ""),
            "article": str(offer.get("article") or ""),
            "product_name": str(product.name or ""),
            "proposed_category": proposed,
            "confidence": f"{confidence:.3f}",
            "status": status,
            "reason": reason,
        }

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "raw_offer_id",
            "brand",
            "article",
            "product_name",
            "proposed_category",
            "confidence",
            "status",
            "reason",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
