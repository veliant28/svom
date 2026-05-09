from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.catalog.models import Category, Product
from apps.catalog.services.manual_remaining_categories import extract_remaining_payload_fields
from apps.catalog.services.supplier_category_mapping import (
    CONTROLLED_SUPPLIER_TARGET_SLUGS,
    STATUS_ACTIVE,
    STATUS_REVIEW,
    SupplierCategoryMappingResolver,
)
from apps.supplier_imports.models import SupplierRawOffer


@dataclass
class AssignSummary:
    processed_uncategorized: int = 0
    active_mapping_found: int = 0
    would_assign: int = 0
    assigned: int = 0
    skipped_no_mapping: int = 0
    skipped_review_mapping: int = 0
    skipped_already_categorized: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Assign categories only via controlled SupplierCategoryMapping (status=active)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max products to inspect")
        parser.add_argument("--only-uncategorized", action="store_true", help="Limit to Product.category is null")
        parser.add_argument("--dry-run", action="store_true", help="Preview only, no writes")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")
        limit = max(int(options.get("limit") or 0), 0)
        only_uncategorized = bool(options.get("only_uncategorized"))
        dry_run = bool(options.get("dry_run"))
        export_csv = str(options.get("export_csv") or "").strip()

        resolver = SupplierCategoryMappingResolver()
        products = self._load_products(supplier_code=supplier_code, limit=limit, only_uncategorized=only_uncategorized)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])

        summary = AssignSummary()
        counts_by_target: Counter[str] = Counter()
        rows: list[dict[str, str]] = []

        self.stdout.write(
            "assign_supplier_mapped_categories started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'} dry_run={int(dry_run)} only_uncategorized={int(only_uncategorized)}"
        )

        for product in products:
            summary.processed_uncategorized += 1
            offer = raw_offer_map.get(str(product.id), {})
            payload = offer.get("raw_payload") if isinstance(offer, dict) else {}
            fields = extract_remaining_payload_fields(payload if isinstance(payload, dict) else {})

            resolution = resolver.resolve_with_evidence(
                supplier_code=supplier_code,
                raw_category=fields.category,
                raw_group=fields.group,
                raw_name=fields.name,
                raw_description=fields.description,
                product_name=str(product.name or ""),
                supplier_product_name=str(offer.get("product_name") or ""),
                raw_brand=str(offer.get("brand_name") or ""),
            )

            if resolution is None:
                summary.skipped_no_mapping += 1
                rows.append(
                    self._row_for(
                        product=product,
                        offer=offer,
                        status="skipped_no_mapping",
                        target="",
                        reason="no_mapping",
                        confidence=0.0,
                        raw_category=fields.category,
                        raw_group=fields.group,
                    )
                )
                continue

            if resolution.status == STATUS_REVIEW:
                summary.skipped_review_mapping += 1
                rows.append(self._row_for(product=product, offer=offer, status="skipped_review_mapping", target=resolution.target_category_slug, reason=resolution.reason, confidence=resolution.confidence, raw_category=fields.category, raw_group=fields.group))
                continue

            if resolution.status != STATUS_ACTIVE:
                summary.skipped_no_mapping += 1
                rows.append(self._row_for(product=product, offer=offer, status="skipped_inactive_mapping", target=resolution.target_category_slug, reason=resolution.reason, confidence=resolution.confidence, raw_category=fields.category, raw_group=fields.group))
                continue

            if resolution.target_category_slug not in CONTROLLED_SUPPLIER_TARGET_SLUGS:
                summary.failed += 1
                rows.append(
                    self._row_for(
                        product=product,
                        offer=offer,
                        status="failed",
                        target=resolution.target_category_slug,
                        reason="target_outside_controlled_whitelist",
                        confidence=resolution.confidence,
                        raw_category=fields.category,
                        raw_group=fields.group,
                    )
                )
                continue

            summary.active_mapping_found += 1
            target = Category.objects.filter(slug=resolution.target_category_slug).first()
            if target is None:
                summary.failed += 1
                rows.append(self._row_for(product=product, offer=offer, status="failed", target=resolution.target_category_slug, reason="target_category_missing", confidence=resolution.confidence, raw_category=fields.category, raw_group=fields.group))
                continue

            if product.category_id == target.id:
                summary.skipped_already_categorized += 1
                rows.append(self._row_for(product=product, offer=offer, status="skipped_already_categorized", target=target.name, reason="already_target", confidence=resolution.confidence, raw_category=fields.category, raw_group=fields.group))
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
                    rows.append(self._row_for(product=product, offer=offer, status="failed", target=target.name, reason="save_error", confidence=resolution.confidence, raw_category=fields.category, raw_group=fields.group))
                    continue

            rows.append(self._row_for(product=product, offer=offer, status="would_assign", target=target.name, reason=resolution.reason, confidence=resolution.confidence, raw_category=fields.category, raw_group=fields.group))

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("assign supplier mapped categories summary:")
        self.stdout.write(f"- processed_uncategorized: {summary.processed_uncategorized}")
        self.stdout.write(f"- active_mapping_found: {summary.active_mapping_found}")
        self.stdout.write(f"- would_assign: {summary.would_assign}")
        self.stdout.write(f"- skipped_no_mapping: {summary.skipped_no_mapping}")
        self.stdout.write(f"- skipped_review_mapping: {summary.skipped_review_mapping}")
        self.stdout.write(f"- skipped_already_categorized: {summary.skipped_already_categorized}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- counts_by_target_category:")
        for key, value in counts_by_target.most_common():
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _load_products(self, *, supplier_code: str, limit: int, only_uncategorized: bool) -> list[Product]:
        qs = (
            Product.objects.select_related("category", "brand")
            .filter(raw_supplier_offers__source__code=supplier_code)
            .filter(Q(autodb_supplier_id__isnull=True) | Q(autodb_article_key__isnull=True) | Q(autodb_article_key=""))
            .distinct()
            .order_by("id")
        )
        if only_uncategorized:
            qs = qs.filter(category__isnull=True)
        if limit > 0:
            qs = qs[:limit]
        return list(qs)

    def _load_latest_raw_offer_map(self, *, supplier_code: str, product_ids: list[str]) -> dict[str, dict]:
        if not product_ids:
            return {}
        rows = (
            SupplierRawOffer.objects.filter(source__code=supplier_code, matched_product_id__in=product_ids)
            .order_by("matched_product_id", "-updated_at", "-id")
            .values("id", "matched_product_id", "brand_name", "article", "product_name", "raw_payload")
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
        target: str,
        reason: str,
        confidence: float,
        raw_category: str,
        raw_group: str,
    ) -> dict[str, str]:
        return {
            "product_id": str(product.id),
            "raw_offer_id": str(offer.get("id") or ""),
            "brand": str(offer.get("brand_name") or ""),
            "article": str(offer.get("article") or ""),
            "product_name": str(product.name or ""),
            "raw_category": raw_category,
            "raw_group": raw_group,
            "status": status,
            "target_category": target,
            "confidence": f"{confidence:.3f}",
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
            "raw_category",
            "raw_group",
            "status",
            "target_category",
            "confidence",
            "reason",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
