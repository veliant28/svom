from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from apps.catalog.models import Product
from apps.catalog.services import get_product_display_brand_payload
from apps.catalog.services.manual_remaining_categories import (
    STATUS_NEEDS_REVIEW,
    STATUS_SAFE,
    STATUS_SKIP,
    decide_remaining_manual_category,
    extract_remaining_payload_fields,
)
from apps.supplier_imports.models import SupplierRawOffer


@dataclass
class AuditSummary:
    total_uncategorized: int = 0
    safe_candidates: int = 0
    needs_review: int = 0
    skip_unclear: int = 0


class Command(BaseCommand):
    help = "Read-only audit for remaining uncategorized unlinked products (controlled whitelist mapping)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=500, help="Max products to inspect")
        parser.add_argument("--only-uncategorized", action="store_true", help="Keep only Product.category is null (default behavior)")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        if not supplier_code:
            raise CommandError("Provide --supplier CODE")
        limit = max(int(options.get("limit") or 0), 0)
        only_uncategorized = bool(options.get("only_uncategorized"))
        export_csv = str(options.get("export_csv") or "").strip()

        products = self._load_products(supplier_code=supplier_code, limit=limit, only_uncategorized=only_uncategorized)
        raw_offer_map = self._load_latest_raw_offer_map(supplier_code=supplier_code, product_ids=[str(item.id) for item in products])

        summary = AuditSummary(total_uncategorized=len(products))
        counts_by_brand: Counter[str] = Counter()
        counts_by_category: Counter[str] = Counter()
        rows: list[dict[str, str]] = []

        self.stdout.write(
            "audit_remaining_uncategorized_products started "
            f"supplier={supplier_code.upper()} limit={limit or 'none'} only_uncategorized={int(only_uncategorized)}"
        )

        for product in products:
            offer = raw_offer_map.get(str(product.id), {})
            payload = offer.get("raw_payload") if isinstance(offer, dict) else {}
            fields = extract_remaining_payload_fields(payload if isinstance(payload, dict) else {})
            brand_payload = get_product_display_brand_payload(product)
            display_brand = brand_payload.display_brand
            brand_source = brand_payload.brand_source
            raw_brand = str(offer.get("brand_name") or "").strip()
            raw_article = str(offer.get("article") or "").strip()
            supplier_name = str(offer.get("product_name") or "").strip()
            current_category = str(getattr(getattr(product, "category", None), "name", "") or "")

            decision = decide_remaining_manual_category(
                product_name=str(product.name or ""),
                supplier_product_name=supplier_name,
                brand=raw_brand or display_brand,
                payload=fields,
            )
            suggested_action, suggested_existing_category, suggestion_reason, suggestion_confidence = self._suggest_action(
                product_name=str(product.name or ""),
                supplier_product_name=supplier_name,
                payload_fields=(fields.category, fields.group, fields.name, fields.description),
                decision_status=decision.status,
                decision_reason=decision.reason,
                decision_category=decision.proposed_category,
                decision_confidence=decision.confidence,
            )

            if decision.status == STATUS_SAFE:
                summary.safe_candidates += 1
                counts_by_category[decision.proposed_category] += 1
            elif decision.status == STATUS_NEEDS_REVIEW:
                summary.needs_review += 1
            else:
                summary.skip_unclear += 1

            counts_by_brand[(display_brand or raw_brand or "<empty>")] += 1
            rows.append(
                {
                    "product_id": str(product.id),
                    "display_name": str(product.name or ""),
                    "display_brand": display_brand,
                    "brand_source": brand_source,
                    "raw_brand": raw_brand,
                    "raw_article": raw_article,
                    "raw_product_name": supplier_name,
                    "raw_category": fields.category,
                    "raw_group": fields.group,
                    "raw_name": fields.name,
                    "raw_description": fields.description,
                    "current_category": current_category,
                    "suggested_action": suggested_action,
                    "suggested_existing_category": suggested_existing_category,
                    "proposed_root": decision.proposed_root_slug,
                    "proposed_child_category": decision.proposed_category,
                    "confidence": f"{suggestion_confidence:.3f}",
                    "reason": suggestion_reason,
                    "status": decision.status,
                }
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("remaining uncategorized audit summary:")
        self.stdout.write(f"- total_uncategorized: {summary.total_uncategorized}")
        self.stdout.write(f"- safe_candidates: {summary.safe_candidates}")
        self.stdout.write(f"- needs_review: {summary.needs_review}")
        self.stdout.write(f"- skip_unclear: {summary.skip_unclear}")
        self.stdout.write("- counts_by_brand:")
        for key, value in counts_by_brand.most_common(20):
            self.stdout.write(f"  - {key}: {value}")
        self.stdout.write("- counts_by_proposed_category:")
        for key, value in counts_by_category.most_common():
            self.stdout.write(f"  - {key}: {value}")
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
        else:
            qs = qs.filter(category__isnull=True)
        if limit > 0:
            qs = qs[:limit]
        return list(qs)

    def _suggest_action(
        self,
        *,
        product_name: str,
        supplier_product_name: str,
        payload_fields: tuple[str, str, str, str],
        decision_status: str,
        decision_reason: str,
        decision_category: str,
        decision_confidence: float,
    ) -> tuple[str, str, str, float]:
        text = " ".join(
            item
            for item in [
                product_name.strip(),
                supplier_product_name.strip(),
                payload_fields[0],
                payload_fields[1],
                payload_fields[2],
                payload_fields[3],
            ]
            if item
        ).lower()

        tape_tokens = ("изолент", "ізоляційн", "изоляцион", "electrical tape")
        adblue_tokens = ("adblue", "euroblue", "def", "мочевин", "сечовин", "urea")

        if decision_status == STATUS_SAFE and decision_category:
            return (
                "assign_existing_category",
                decision_category,
                decision_reason,
                float(decision_confidence),
            )

        if any(token in text for token in tape_tokens):
            return (
                "assign_existing_category",
                "Изолента и электроматериалы",
                "explicit_electrical_tape_signal",
                0.92,
            )

        if any(token in text for token in adblue_tokens):
            return (
                "assign_existing_category",
                "AdBlue и технические жидкости",
                "explicit_adblue_signal",
                0.91,
            )

        if decision_status == STATUS_NEEDS_REVIEW:
            return ("needs_manual_category", "", decision_reason, float(decision_confidence))

        return ("leave_uncategorized", "", decision_reason, float(decision_confidence))

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

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        out_path = Path(path).expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        headers = [
            "product_id",
            "display_name",
            "display_brand",
            "brand_source",
            "raw_brand",
            "raw_article",
            "raw_product_name",
            "raw_category",
            "raw_group",
            "raw_name",
            "raw_description",
            "current_category",
            "suggested_action",
            "suggested_existing_category",
            "proposed_root",
            "proposed_child_category",
            "confidence",
            "reason",
            "status",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
