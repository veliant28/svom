from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Product
from apps.catalog.services.linked_semantic_audit import (
    SHOCK_TOKENS,
    detect_semantic_conflicts,
    extract_autodb_titles_from_quality,
    extract_raw_fields,
    load_latest_quality_map,
    load_latest_raw_offer_map,
)


def _norm(value: str) -> str:
    return " ".join(str(value or "").split()).casefold()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


class Command(BaseCommand):
    help = "Dry-run rollback plan for suspicious Auto_DB enrichment effects (no writes)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=5000, help="Max linked products to inspect")
        parser.add_argument("--reason", type=str, default="exhaust_as_shock", help="Reason scope, e.g. exhaust_as_shock")
        parser.add_argument("--dry-run", action="store_true", help="Required safety flag (command is no-write)")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier")
        limit = max(int(options.get("limit") or 0), 0)
        reason = str(options.get("reason") or "").strip().lower()
        dry_run = bool(options.get("dry_run"))
        export_csv = str(options.get("export_csv") or "").strip()

        if not dry_run:
            raise CommandError("Safety mode: run with --dry-run. Real rollback is disabled in this stage.")

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
            "rollback_suspicious_autodb_product_enrichment started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'} reason={reason} dry_run=1"
        )

        for product in products:
            pid = str(product.id)
            raw = raw_map.get(pid, {})
            payload = raw.get("raw_payload") if isinstance(raw.get("raw_payload"), dict) else {}
            fields = extract_raw_fields(payload)

            raw_brand = str(raw.get("brand_name") or "").strip()
            raw_product_name = str(raw.get("product_name") or "").strip()
            raw_text = " | ".join(
                [
                    raw_product_name,
                    fields["raw_name"],
                    fields["raw_category"],
                    fields["raw_group"],
                    fields["raw_description"],
                    raw_brand,
                ]
            )
            current_category = str(getattr(product.category, "name", "") or "")
            category_source = str(getattr(product.category, "source", "") or "")
            product_text = " | ".join(
                [
                    str(getattr(product, "name", "") or ""),
                    str(getattr(product, "name_uk", "") or ""),
                    str(getattr(product, "name_ru", "") or ""),
                    str(getattr(product, "name_en", "") or ""),
                ]
            )

            quality = quality_map.get(pid)
            autodb_title = " | ".join(
                x
                for x in [
                    str(getattr(product, "name_source_text", "") or "").strip(),
                    extract_autodb_titles_from_quality(quality),
                ]
                if x
            )

            conflicts = detect_semantic_conflicts(
                raw_brand=raw_brand,
                raw_text=raw_text,
                product_text=product_text,
                category_text=current_category,
                autodb_title_text=autodb_title,
            )
            conflict_types = {item.conflict_type for item in conflicts}
            if reason == "exhaust_as_shock":
                if not conflict_types.intersection({"exhaust_vs_shock", "polmo_exhaust_vs_shock"}):
                    continue
            elif reason and reason not in conflict_types:
                continue

            summary["candidates"] += 1

            would_mark_suspicious = 1
            would_clear_category = int(category_source == "autodb_pro" and _contains_any(_norm(current_category), SHOCK_TOKENS))
            would_reset_name = int(
                str(getattr(product, "name_source", "") or "") == Product.NAME_SOURCE_AUTODB_PRO
                and _contains_any(_norm(str(getattr(product, "name", "") or "")), SHOCK_TOKENS)
            )
            would_reset_brand_source = int(str(getattr(product, "brand_source", "") or "") == Product.BRAND_SOURCE_AUTODB_PRO)
            would_unlink_autodb = int(any(item.confidence >= 0.97 for item in conflicts))

            summary["would_mark_suspicious"] += would_mark_suspicious
            summary["would_clear_category"] += would_clear_category
            summary["would_reset_name"] += would_reset_name
            summary["would_reset_brand_source"] += would_reset_brand_source
            summary["would_unlink_autodb"] += would_unlink_autodb

            row = {
                "product_id": pid,
                "raw_brand": raw_brand,
                "raw_article": str(raw.get("article") or ""),
                "raw_product_name": raw_product_name,
                "raw_category": fields["raw_category"],
                "raw_group": fields["raw_group"],
                "raw_description": fields["raw_description"],
                "current_name": str(getattr(product, "name", "") or ""),
                "current_category": current_category,
                "current_category_source": category_source,
                "autodb_article_key": str(getattr(product, "autodb_article_key", "") or ""),
                "autodb_supplier_id": str(getattr(product, "autodb_supplier_id", "") or ""),
                "autodb_supplier_name": str(getattr(product, "autodb_supplier_name", "") or ""),
                "name_source": str(getattr(product, "name_source", "") or ""),
                "brand_source": str(getattr(product, "brand_source", "") or ""),
                "conflict_types": ",".join(sorted(conflict_types)),
                "max_confidence": f"{max((item.confidence for item in conflicts), default=0.0):.3f}",
                "would_mark_link_quality_suspicious": str(would_mark_suspicious),
                "would_clear_category": str(would_clear_category),
                "would_reset_name": str(would_reset_name),
                "would_reset_brand_source": str(would_reset_brand_source),
                "would_unlink_autodb": str(would_unlink_autodb),
            }
            rows.append(row)

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("rollback suspicious autodb enrichment dry-run summary:")
        self.stdout.write(f"- candidates: {summary.get('candidates', 0)}")
        self.stdout.write(f"- would_mark_suspicious: {summary.get('would_mark_suspicious', 0)}")
        self.stdout.write(f"- would_clear_category: {summary.get('would_clear_category', 0)}")
        self.stdout.write(f"- would_reset_name: {summary.get('would_reset_name', 0)}")
        self.stdout.write(f"- would_reset_brand_source: {summary.get('would_reset_brand_source', 0)}")
        self.stdout.write(f"- would_unlink_autodb: {summary.get('would_unlink_autodb', 0)}")
        self.stdout.write("- price/stock changed=0")
        self.stdout.write("- UTR calls=0")

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
            "current_name",
            "current_category",
            "current_category_source",
            "autodb_article_key",
            "autodb_supplier_id",
            "autodb_supplier_name",
            "name_source",
            "brand_source",
            "conflict_types",
            "max_confidence",
            "would_mark_link_quality_suspicious",
            "would_clear_category",
            "would_reset_name",
            "would_reset_brand_source",
            "would_unlink_autodb",
        ]
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
