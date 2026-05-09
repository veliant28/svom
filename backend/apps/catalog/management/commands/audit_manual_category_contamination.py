from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Category, Product
from apps.catalog.services.linked_semantic_audit import extract_raw_fields, load_latest_raw_offer_map
from apps.catalog.services.manual_category_contamination import classify_manual_category_contamination


class Command(BaseCommand):
    help = "Read-only audit of contamination in a manual category (e.g. Автоэмали и краски)."

    def add_arguments(self, parser):
        parser.add_argument("--category", type=str, required=True, help="Category display name")
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=5000, help="Max products to inspect")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        category_name = str(options.get("category") or "").strip()
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not category_name:
            raise CommandError("Provide --category")
        if not supplier_code:
            raise CommandError("Provide --supplier")
        limit = max(int(options.get("limit") or 0), 0)
        export_csv = str(options.get("export_csv") or "").strip()

        category = Category.objects.filter(name=category_name).first()
        if category is None:
            raise CommandError(f"Category not found: {category_name}")

        qs = (
            Product.objects.select_related("category", "brand")
            .filter(category=category, raw_supplier_offers__source__code=supplier_code)
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]
        products = list(qs)
        product_ids = [str(item.id) for item in products]
        raw_map = load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=product_ids)

        rows: list[dict[str, str]] = []
        summary = Counter()
        by_target = Counter()

        self.stdout.write(
            "audit_manual_category_contamination started "
            f"category={category_name} supplier={supplier_code.upper()} limit={limit or 'none'}"
        )

        for product in products:
            pid = str(product.id)
            raw = raw_map.get(pid, {})
            payload = raw.get("raw_payload") if isinstance(raw.get("raw_payload"), dict) else {}
            fields = extract_raw_fields(payload)

            raw_brand = str(raw.get("brand_name") or "").strip()
            raw_article = str(raw.get("article") or "").strip()
            raw_product_name = str(raw.get("product_name") or "").strip()
            evidence_text = " | ".join(
                [
                    str(getattr(product, "name", "") or ""),
                    raw_product_name,
                    fields["raw_name"],
                    fields["raw_category"],
                    fields["raw_group"],
                    fields["raw_description"],
                    raw_brand,
                ]
            )

            decision = classify_manual_category_contamination(text=evidence_text)
            status = decision.status
            summary[status] += 1
            by_target[status] += 1
            if status != "safe_paint":
                summary["contaminated_count"] += 1

            rows.append(
                {
                    "product_id": pid,
                    "brand": raw_brand,
                    "article": raw_article,
                    "raw_product_name": raw_product_name,
                    "raw_category": fields["raw_category"],
                    "raw_group": fields["raw_group"],
                    "raw_description": fields["raw_description"],
                    "current_category": category_name,
                    "classification": status,
                    "confidence": f"{decision.confidence:.3f}",
                    "reason": decision.reason,
                }
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("manual category contamination audit summary:")
        self.stdout.write(f"- total_in_category: {len(rows)}")
        self.stdout.write(f"- contaminated_count: {summary.get('contaminated_count', 0)}")
        self.stdout.write(f"- safe_paint_count: {summary.get('safe_paint', 0)}")
        self.stdout.write("- by_recommended_target:")
        for key, value in sorted(by_target.items(), key=lambda item: (-item[1], item[0])):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- examples:")
        for row in [r for r in rows if r["classification"] != "safe_paint"][:30]:
            self.stdout.write(
                "  - "
                f"product_id={row['product_id']} brand={row['brand']} article={row['article']} "
                f"class={row['classification']} conf={row['confidence']} reason={row['reason']} "
                f"raw_name={row['raw_product_name'][:80]}"
            )
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "brand",
            "article",
            "raw_product_name",
            "raw_category",
            "raw_group",
            "raw_description",
            "current_category",
            "classification",
            "confidence",
            "reason",
        ]
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
