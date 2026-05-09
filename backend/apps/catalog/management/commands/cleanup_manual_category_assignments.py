from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import Category, Product
from apps.catalog.services.linked_semantic_audit import extract_raw_fields, load_latest_raw_offer_map
from apps.catalog.services.manual_category_contamination import classify_manual_category_contamination


TARGET_BY_CLASS = {
    "should_move_to_tools_accessories": "Инструменты и аксессуары",
    "should_move_to_ppe_safety": "Аптечки и безопасность",
    "should_move_to_abrasives": "Абразивы и шлифовальные материалы",
    "should_move_to_paper_tape_consumables": "Малярные материалы и расходники",
}


@dataclass
class CleanupSummary:
    processed: int = 0
    would_keep: int = 0
    would_move: int = 0
    would_clear: int = 0
    needs_review: int = 0
    failed: int = 0


class Command(BaseCommand):
    help = "Cleanup manual category assignments by contamination rules."

    def add_arguments(self, parser):
        parser.add_argument("--source-category", type=str, required=True, help="Source category name")
        parser.add_argument("--supplier", type=str, required=True, help="Supplier code")
        parser.add_argument("--limit", type=int, default=5000, help="Max products to inspect")
        parser.add_argument("--dry-run", action="store_true", help="Preview only")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        source_category_name = str(options.get("source_category") or "").strip()
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not source_category_name:
            raise CommandError("Provide --source-category")
        if not supplier_code:
            raise CommandError("Provide --supplier")
        limit = max(int(options.get("limit") or 0), 0)
        dry_run = bool(options.get("dry_run"))
        export_csv = str(options.get("export_csv") or "").strip()

        source_category = Category.objects.filter(name=source_category_name).first()
        if source_category is None:
            raise CommandError(f"Category not found: {source_category_name}")

        qs = (
            Product.objects.select_related("category", "brand")
            .filter(category=source_category, raw_supplier_offers__source__code=supplier_code)
            .distinct()
            .order_by("id")
        )
        if limit > 0:
            qs = qs[:limit]
        products = list(qs)
        product_ids = [str(item.id) for item in products]
        raw_map = load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=product_ids)

        summary = CleanupSummary()
        reason_counts = Counter()
        rows: list[dict[str, str]] = []

        self.stdout.write(
            "cleanup_manual_category_assignments started "
            f"source_category={source_category_name} supplier={supplier_code.upper()} limit={limit or 'none'} dry_run={int(dry_run)}"
        )

        for product in products:
            summary.processed += 1
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
            reason_counts[decision.reason] += 1

            action = "keep"
            target_category = ""

            if decision.status == "safe_paint":
                summary.would_keep += 1
            else:
                if decision.status in TARGET_BY_CLASS and decision.confidence >= 0.9:
                    target_name = TARGET_BY_CLASS[decision.status]
                    target = Category.objects.filter(name=target_name).first()
                    if target is not None:
                        action = "move"
                        target_category = target.name
                        summary.would_move += 1
                    else:
                        action = "clear"
                        summary.would_clear += 1
                else:
                    action = "clear"
                    summary.would_clear += 1
                summary.needs_review += 1

            if not dry_run:
                try:
                    with transaction.atomic():
                        if action == "move":
                            target = Category.objects.filter(name=target_category).first()
                            if target is None:
                                summary.failed += 1
                                continue
                            product.category = target
                        elif action == "clear":
                            product.category = None
                        product.save(update_fields=["category", "updated_at"])
                except Exception:  # noqa: BLE001
                    summary.failed += 1
                    continue

            rows.append(
                {
                    "product_id": pid,
                    "brand": raw_brand,
                    "article": raw_article,
                    "raw_product_name": raw_product_name,
                    "raw_category": fields["raw_category"],
                    "raw_group": fields["raw_group"],
                    "raw_description": fields["raw_description"],
                    "source_category": source_category_name,
                    "classification": decision.status,
                    "confidence": f"{decision.confidence:.3f}",
                    "reason": decision.reason,
                    "action": action,
                    "target_category": target_category,
                }
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("cleanup manual category assignments summary:")
        self.stdout.write(f"- processed: {summary.processed}")
        self.stdout.write(f"- would_keep: {summary.would_keep}")
        self.stdout.write(f"- would_move: {summary.would_move}")
        self.stdout.write(f"- would_clear: {summary.would_clear}")
        self.stdout.write(f"- needs_review: {summary.needs_review}")
        self.stdout.write(f"- failed: {summary.failed}")
        self.stdout.write("- by_reason:")
        for reason, count in reason_counts.most_common(20):
            self.stdout.write(f"  - {reason}: {count}")
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
            "source_category",
            "classification",
            "confidence",
            "reason",
            "action",
            "target_category",
        ]
        with out.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
