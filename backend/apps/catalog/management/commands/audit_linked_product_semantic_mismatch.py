from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Product
from apps.catalog.services.linked_semantic_audit import (
    detect_semantic_conflicts,
    extract_autodb_titles_from_quality,
    extract_raw_fields,
    load_latest_quality_map,
    load_latest_raw_offer_map,
    recommend_action,
)


class Command(BaseCommand):
    help = "Read-only broader semantic mismatch audit for linked products."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=5000, help="Max linked products to inspect")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier")
        limit = max(int(options.get("limit") or 0), 0)
        export_csv = str(options.get("export_csv") or "").strip()

        qs = (
            Product.objects.select_related("brand", "category")
            .filter(raw_supplier_offers__source__code=supplier_code)
            .exclude(autodb_article_key="")
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]
        products = list(qs)
        product_ids = [str(item.id) for item in products]

        raw_map = load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=product_ids)
        quality_map = load_latest_quality_map(product_ids=product_ids)

        rows: list[dict[str, str]] = []
        summary = Counter()
        by_brand = Counter()

        self.stdout.write(
            "audit_linked_product_semantic_mismatch started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'}"
        )

        for product in products:
            pid = str(product.id)
            raw = raw_map.get(pid, {})
            payload = raw.get("raw_payload") if isinstance(raw.get("raw_payload"), dict) else {}
            fields = extract_raw_fields(payload)

            raw_brand = str(raw.get("brand_name") or "").strip()
            raw_article = str(raw.get("article") or "").strip()
            raw_product_name = str(raw.get("product_name") or "").strip()
            raw_category = fields["raw_category"]
            raw_group = fields["raw_group"]
            raw_description = fields["raw_description"]

            current_category = str(getattr(product.category, "name", "") or "")
            category_source = str(getattr(product.category, "source", "") or "")
            product_name = str(getattr(product, "name", "") or "")

            quality = quality_map.get(pid)
            quality_status = str(getattr(quality, "status", "") or "")
            quality_reason = str(getattr(quality, "reason", "") or "")
            autodb_title = " | ".join(
                x
                for x in [
                    str(getattr(product, "name_source_text", "") or "").strip(),
                    extract_autodb_titles_from_quality(quality),
                ]
                if x
            )

            raw_text = " | ".join(
                [
                    raw_product_name,
                    raw_category,
                    raw_group,
                    raw_description,
                    str(fields.get("raw_name") or ""),
                    raw_brand,
                ]
            )
            product_text = " | ".join(
                [
                    str(getattr(product, "name", "") or ""),
                    str(getattr(product, "name_uk", "") or ""),
                    str(getattr(product, "name_ru", "") or ""),
                    str(getattr(product, "name_en", "") or ""),
                ]
            )

            conflicts = detect_semantic_conflicts(
                raw_brand=raw_brand,
                raw_text=raw_text,
                product_text=product_text,
                category_text=current_category,
                autodb_title_text=autodb_title,
            )

            if conflicts:
                summary["semantic_conflict_count"] += 1
                by_brand[raw_brand or "Без бренду"] += 1

            if not conflicts:
                rows.append(
                    {
                        "product_id": pid,
                        "raw_brand": raw_brand,
                        "raw_article": raw_article,
                        "raw_product_name": raw_product_name,
                        "raw_category": raw_category,
                        "raw_group": raw_group,
                        "raw_description": raw_description,
                        "current_product_name": product_name,
                        "current_category": current_category,
                        "autodb_title": autodb_title,
                        "autodb_article_key": str(getattr(product, "autodb_article_key", "") or ""),
                        "link_quality_status": quality_status,
                        "link_quality_reason": quality_reason,
                        "conflict_type": "",
                        "confidence": "0.000",
                        "recommended_action": "safe",
                    }
                )
                summary["safe"] += 1
                continue

            for conflict in conflicts:
                summary[f"conflict_type:{conflict.conflict_type}"] += 1
                recommended_action = recommend_action(
                    conflicts=[conflict],
                    product=product,
                    category_source=category_source,
                )
                rows.append(
                    {
                        "product_id": pid,
                        "raw_brand": raw_brand,
                        "raw_article": raw_article,
                        "raw_product_name": raw_product_name,
                        "raw_category": raw_category,
                        "raw_group": raw_group,
                        "raw_description": raw_description,
                        "current_product_name": product_name,
                        "current_category": current_category,
                        "autodb_title": autodb_title,
                        "autodb_article_key": str(getattr(product, "autodb_article_key", "") or ""),
                        "link_quality_status": quality_status,
                        "link_quality_reason": quality_reason,
                        "conflict_type": conflict.conflict_type,
                        "confidence": f"{conflict.confidence:.3f}",
                        "recommended_action": recommended_action,
                    }
                )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("linked semantic mismatch summary:")
        self.stdout.write(f"- total_linked_checked: {len(products)}")
        self.stdout.write(f"- semantic_conflict_count: {summary.get('semantic_conflict_count', 0)}")
        self.stdout.write(f"- safe: {summary.get('safe', 0)}")
        self.stdout.write("- by_conflict_type:")
        for key, value in sorted(
            ((k.replace("conflict_type:", ""), v) for k, v in summary.items() if k.startswith("conflict_type:")),
            key=lambda item: (-item[1], item[0]),
        )[:20]:
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- by_brand_conflicts:")
        for brand, count in by_brand.most_common(20):
            self.stdout.write(f"  - {brand}: {count}")
        self.stdout.write("- top_50_conflict_examples:")
        conflict_rows = [row for row in rows if row["conflict_type"]][:50]
        for row in conflict_rows:
            self.stdout.write(
                "  - "
                f"product_id={row['product_id']} conflict={row['conflict_type']} conf={row['confidence']} "
                f"brand={row['raw_brand']} raw_category={row['raw_category']} current_category={row['current_category']}"
            )
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "raw_brand",
            "raw_article",
            "raw_product_name",
            "raw_category",
            "raw_group",
            "raw_description",
            "current_product_name",
            "current_category",
            "autodb_title",
            "autodb_article_key",
            "link_quality_status",
            "link_quality_reason",
            "conflict_type",
            "confidence",
            "recommended_action",
        ]
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
