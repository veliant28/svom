from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.catalog.models import Category, Product
from apps.catalog.services import get_product_display_brand_payload
from apps.catalog.services.manual_remaining_categories import extract_remaining_payload_fields
from apps.catalog.services.supplier_category_mapping import (
    STATUS_ACTIVE,
    STATUS_IGNORED,
    STATUS_REVIEW,
    CATEGORY_NAME_BY_SLUG,
    SupplierCategoryMappingResolver,
)
from apps.supplier_imports.models import SupplierRawOffer


class Command(BaseCommand):
    help = "Read-only grouped audit of supplier raw category/group against controlled SupplierCategoryMapping."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max products to inspect")
        parser.add_argument("--only-uncategorized", action="store_true", help="Include only Product.category is null")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")
        limit = max(int(options.get("limit") or 0), 0)
        only_uncategorized = bool(options.get("only_uncategorized"))
        export_csv = str(options.get("export_csv") or "").strip()

        resolver = SupplierCategoryMappingResolver()
        products = self._load_products(supplier_code=supplier_code, limit=limit, only_uncategorized=only_uncategorized)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])
        categories_by_slug = {item.slug: item.name for item in Category.objects.all().only("slug", "name")}

        grouped: dict[tuple[str, str], dict] = defaultdict(
            lambda: {
                "count": 0,
                "examples": [],
                "status": "ignore",
                "target": "",
                "confidence": 0.0,
                "reason": "",
            }
        )

        status_counts: Counter[str] = Counter()
        brand_counts: Counter[str] = Counter()

        self.stdout.write(
            "audit_supplier_category_mapping started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'} only_uncategorized={int(only_uncategorized)}"
        )

        for product in products:
            offer = raw_offer_map.get(str(product.id), {})
            payload = offer.get("raw_payload") if isinstance(offer, dict) else {}
            fields = extract_remaining_payload_fields(payload if isinstance(payload, dict) else {})
            brand_payload = get_product_display_brand_payload(product)
            display_brand = brand_payload.display_brand

            raw_category = fields.category
            raw_group = fields.group
            key = (raw_category, raw_group)

            resolution = resolver.resolve_with_evidence(
                supplier_code=supplier_code,
                raw_category=raw_category,
                raw_group=raw_group,
                raw_name=fields.name,
                raw_description=fields.description,
                product_name=str(product.name or ""),
                supplier_product_name=str(offer.get("product_name") or ""),
                raw_brand=str(offer.get("brand_name") or ""),
            )

            suggested_name = ""
            status = "ignore"
            confidence = 0.0
            reason = "no_mapping"

            if resolution is not None:
                suggested_name = categories_by_slug.get(
                    resolution.target_category_slug,
                    CATEGORY_NAME_BY_SLUG.get(resolution.target_category_slug, resolution.target_category_slug),
                )
                confidence = float(resolution.confidence)
                reason = resolution.reason
                if resolution.status == STATUS_ACTIVE:
                    if resolution.source == "explicit_mapping":
                        status = "safe_existing_mapping_candidate"
                    else:
                        status = "safe_new_manual_category_candidate"
                elif resolution.status == STATUS_REVIEW:
                    status = "needs_review"
                elif resolution.status == STATUS_IGNORED:
                    status = "ignore"

            bucket = grouped[key]
            bucket["count"] += 1
            bucket["status"] = self._priority_status(bucket["status"], status)
            if confidence >= bucket["confidence"]:
                bucket["target"] = suggested_name
                bucket["confidence"] = confidence
                bucket["reason"] = reason

            if len(bucket["examples"]) < 5:
                bucket["examples"].append(
                    {
                        "product_id": str(product.id),
                        "display_name": str(product.name or ""),
                        "display_brand": display_brand,
                        "raw_article": str(offer.get("article") or ""),
                    }
                )

            status_counts[status] += 1
            brand_counts[display_brand or str(offer.get("brand_name") or "Без бренду")] += 1

        rows: list[dict[str, str]] = []
        for (raw_category, raw_group), item in sorted(grouped.items(), key=lambda kv: (-kv[1]["count"], kv[0][0], kv[0][1])):
            examples = item["examples"]
            rows.append(
                {
                    "supplier_code": supplier_code.upper(),
                    "raw_category": raw_category,
                    "raw_group": raw_group,
                    "group_count": str(item["count"]),
                    "status": item["status"],
                    "existing_target_category_suggestion": item["target"],
                    "confidence": f"{item['confidence']:.3f}",
                    "reason": item["reason"],
                    "examples": " | ".join(
                        f"{row['product_id']}::{row['raw_article']}::{row['display_brand']}::{row['display_name']}"
                        for row in examples
                    ),
                }
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("supplier category mapping audit summary:")
        self.stdout.write(f"- total_uncategorized_products: {len(products)}")
        self.stdout.write(f"- grouped_pairs: {len(rows)}")
        self.stdout.write(f"- safe_existing_mapping_candidate: {status_counts.get('safe_existing_mapping_candidate', 0)}")
        self.stdout.write(f"- safe_new_manual_category_candidate: {status_counts.get('safe_new_manual_category_candidate', 0)}")
        self.stdout.write(f"- needs_review: {status_counts.get('needs_review', 0)}")
        self.stdout.write(f"- ignore: {status_counts.get('ignore', 0)}")
        self.stdout.write("- top_raw_category_group:")
        for row in rows[:12]:
            self.stdout.write(
                "  - "
                f"{row['group_count']} | {row['raw_category']} | {row['raw_group']} | {row['status']} "
                f"| {row['existing_target_category_suggestion']} | {row['confidence']} | {row['reason']}"
            )
        self.stdout.write("- top_brands_uncategorized:")
        for brand, count in brand_counts.most_common(12):
            self.stdout.write(f"  - {brand}: {count}")
        self.stdout.write("- top_review_examples:")
        review_rows = [row for row in rows if row["status"] == "needs_review"][:10]
        for row in review_rows:
            self.stdout.write(
                f"  - {row['raw_category']} | {row['raw_group']} | conf={row['confidence']} | "
                f"reason={row['reason']} | {row['examples']}"
            )
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _load_products(self, *, supplier_code: str, limit: int, only_uncategorized: bool) -> list[Product]:
        qs = (
            Product.objects.select_related("brand", "category")
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

    def _priority_status(self, left: str, right: str) -> str:
        order = {
            "safe_existing_mapping_candidate": 3,
            "safe_new_manual_category_candidate": 2,
            "needs_review": 1,
            "ignore": 0,
        }
        return left if order.get(left, 0) >= order.get(right, 0) else right

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "supplier_code",
            "raw_category",
            "raw_group",
            "group_count",
            "status",
            "existing_target_category_suggestion",
            "confidence",
            "reason",
            "examples",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
