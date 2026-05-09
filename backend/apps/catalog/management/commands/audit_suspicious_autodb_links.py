from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Product
from apps.catalog.services.linked_semantic_audit import (
    EXHAUST_TOKENS,
    SHOCK_TOKENS,
    detect_semantic_conflicts,
    extract_autodb_titles_from_quality,
    extract_raw_fields,
    load_latest_quality_map,
    load_latest_raw_offer_map,
    recommend_action,
)


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


class Command(BaseCommand):
    help = "Read-only audit of suspicious linked products, with focus on exhaust-vs-shock conflicts."

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

        self.stdout.write(
            "audit_suspicious_autodb_links started "
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
            gpl_image_url = fields["gpl_image_url"]

            current_category = str(getattr(product.category, "name", "") or "")
            category_source = str(getattr(product.category, "source", "") or "")
            product_display_name = str(getattr(product, "name", "") or "")
            autodb_title = str(getattr(product, "name_source_text", "") or "").strip()

            quality = quality_map.get(pid)
            quality_status = str(getattr(quality, "status", "") or "")
            quality_reason = str(getattr(quality, "reason", "") or "")
            quality_titles = extract_autodb_titles_from_quality(quality)
            if quality_titles:
                autodb_title = " | ".join([x for x in [autodb_title, quality_titles] if x])

            product_text = " | ".join(
                [
                    str(getattr(product, "name", "") or ""),
                    str(getattr(product, "name_uk", "") or ""),
                    str(getattr(product, "name_ru", "") or ""),
                    str(getattr(product, "name_en", "") or ""),
                ]
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

            raw_has_exhaust = _contains_any(_norm(raw_text), EXHAUST_TOKENS) or "polmo" in _norm(raw_brand)
            autodb_has_shock = _contains_any(_norm(" | ".join([product_text, current_category, autodb_title])), SHOCK_TOKENS)
            category_has_shock = _contains_any(_norm(current_category), SHOCK_TOKENS)

            suspicious_reasons: list[str] = []
            if raw_has_exhaust and autodb_has_shock:
                suspicious_reasons.append("exhaust_as_shock")
            if "polmo" in _norm(raw_brand) and autodb_has_shock:
                suspicious_reasons.append("polmo_brand_exhaust_as_shock")
            if category_has_shock and raw_has_exhaust:
                suspicious_reasons.append("category_shock_vs_raw_exhaust")

            conflicts = detect_semantic_conflicts(
                raw_brand=raw_brand,
                raw_text=raw_text,
                product_text=product_text,
                category_text=current_category,
                autodb_title_text=autodb_title,
            )
            conflict_types = ",".join(sorted({item.conflict_type for item in conflicts}))
            conflict_confidence = max([item.confidence for item in conflicts], default=0.0)

            recommended_action = recommend_action(
                conflicts=conflicts,
                product=product,
                category_source=category_source,
            )
            if suspicious_reasons and recommended_action == "safe":
                recommended_action = "needs_manual_review"

            if suspicious_reasons:
                summary["suspicious_exhaust_as_shock"] += 1
            if "polmo" in _norm(raw_brand) and suspicious_reasons:
                summary["suspicious_by_brand_polmo"] += 1
            if category_has_shock and raw_has_exhaust:
                summary["suspicious_by_category_name"] += 1

            if recommended_action == "safe":
                summary["safe"] += 1
            if recommended_action == "needs_manual_review":
                summary["needs_review"] += 1

            row = {
                "product_id": pid,
                "supplier_raw_offer_id": str(raw.get("id") or ""),
                "raw_brand": raw_brand,
                "raw_article": raw_article,
                "raw_product_name": raw_product_name,
                "raw_category": raw_category,
                "raw_group": raw_group,
                "raw_description": raw_description,
                "gpl_image_url": gpl_image_url,
                "product_name_or_display_name": product_display_name,
                "current_category": current_category,
                "autodb_article_key": str(getattr(product, "autodb_article_key", "") or ""),
                "autodb_supplier_id": str(getattr(product, "autodb_supplier_id", "") or ""),
                "autodb_supplier_name": str(getattr(product, "autodb_supplier_name", "") or ""),
                "autodb_title_source_title": autodb_title,
                "link_quality_status": quality_status,
                "quality_reason": quality_reason,
                "conflict_type": conflict_types,
                "conflict_confidence": f"{conflict_confidence:.3f}",
                "suspicious_reason": ",".join(suspicious_reasons) if suspicious_reasons else "",
                "recommended_action": recommended_action,
            }
            rows.append(row)

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        suspicious_rows = [row for row in rows if row["suspicious_reason"]]
        self.stdout.write("suspicious Auto_DB link audit summary:")
        self.stdout.write(f"- total_linked_checked: {len(rows)}")
        self.stdout.write(f"- suspicious_exhaust_as_shock: {summary.get('suspicious_exhaust_as_shock', 0)}")
        self.stdout.write(f"- suspicious_by_brand_polmo: {summary.get('suspicious_by_brand_polmo', 0)}")
        self.stdout.write(f"- suspicious_by_category_name: {summary.get('suspicious_by_category_name', 0)}")
        self.stdout.write(f"- safe: {summary.get('safe', 0)}")
        self.stdout.write(f"- needs_review: {summary.get('needs_review', 0)}")
        self.stdout.write("- top_suspicious_examples:")
        for row in suspicious_rows[:20]:
            self.stdout.write(
                "  - "
                f"product_id={row['product_id']} raw_brand={row['raw_brand']} raw_category={row['raw_category']} "
                f"raw_name={row['raw_product_name'][:80]} current_category={row['current_category']} "
                f"conflict={row['conflict_type']} suspicious={row['suspicious_reason']} action={row['recommended_action']}"
            )
        self.stdout.write("- UTR calls=0")
        self.stdout.write("- price/stock changed=0")

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out = Path(path).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "supplier_raw_offer_id",
            "raw_brand",
            "raw_article",
            "raw_product_name",
            "raw_category",
            "raw_group",
            "raw_description",
            "gpl_image_url",
            "product_name_or_display_name",
            "current_category",
            "autodb_article_key",
            "autodb_supplier_id",
            "autodb_supplier_name",
            "autodb_title_source_title",
            "link_quality_status",
            "quality_reason",
            "conflict_type",
            "conflict_confidence",
            "suspicious_reason",
            "recommended_action",
        ]
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
