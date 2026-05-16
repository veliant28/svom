from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.supplier_imports.models import SupplierRawOffer


@dataclass(frozen=True)
class ManualRule:
    index: int
    category_slug: str
    exact_names: tuple[str, ...]
    note: str


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class Command(BaseCommand):
    help = "Apply curated manual category rules only to currently uncategorized products."

    def add_arguments(self, parser):
        parser.add_argument("--rules-json", required=True, help="JSON file with rules[].")
        parser.add_argument("--source", default="", help="Optional supplier source code filter, e.g. utr.")
        parser.add_argument("--batch-size", type=int, default=1000)
        parser.add_argument("--apply", action="store_true", help="Persist updates. Default is dry-run.")
        parser.add_argument("--report-json", default="/tmp/manual_uncategorized_category_rules_report.json")

    def handle(self, *args, **options):
        rules_path = Path(str(options["rules_json"])).expanduser().resolve()
        if not rules_path.exists():
            raise CommandError(f"Rules JSON not found: {rules_path}")

        source_code = str(options.get("source") or "").strip().lower()
        batch_size = max(100, int(options.get("batch_size") or 1000))
        is_apply = bool(options.get("apply"))
        report_path = Path(str(options["report_json"])).expanduser().resolve()

        payload = json.loads(rules_path.read_text(encoding="utf-8"))
        rules = self._parse_rules(payload)
        if not rules:
            raise CommandError("No valid rules found.")

        categories = {
            category.slug: category
            for category in Category.objects.filter(
                slug__in=[rule.category_slug for rule in rules],
                is_active=True,
                is_assignable=True,
            )
        }
        missing = sorted({rule.category_slug for rule in rules if rule.category_slug not in categories})
        if missing:
            raise CommandError(f"Missing active assignable category slug(s): {missing}")

        self.stdout.write(
            f"Running {'APPLY' if is_apply else 'DRY-RUN'} for {len(rules)} manual uncategorized rule(s); "
            f"source={source_code or 'any'}"
        )

        reports: list[dict] = []
        totals = {
            "products_would_assign": 0,
            "products_updated": 0,
            "raw_offers_would_sync": 0,
            "raw_offers_updated": 0,
        }

        with transaction.atomic():
            for rule in rules:
                target = categories[rule.category_slug]
                product_qs = Product.objects.filter(category__isnull=True, name__in=rule.exact_names)
                if source_code:
                    product_qs = product_qs.filter(raw_supplier_offers__source__code=source_code)
                product_ids = [str(item) for item in product_qs.distinct().values_list("id", flat=True)]

                raw_offer_qs = SupplierRawOffer.objects.filter(matched_product_id__in=product_ids)
                if source_code:
                    raw_offer_qs = raw_offer_qs.filter(source__code=source_code)

                products_updated = 0
                raw_offers_updated = 0
                if is_apply and product_ids:
                    now = timezone.now()
                    for chunk in _chunked(product_ids, batch_size):
                        products_updated += Product.objects.filter(
                            id__in=chunk,
                            category__isnull=True,
                        ).update(
                            category=target,
                            category_manually_locked=True,
                            updated_at=now,
                        )

                        chunk_raw_offer_qs = SupplierRawOffer.objects.filter(matched_product_id__in=chunk)
                        if source_code:
                            chunk_raw_offer_qs = chunk_raw_offer_qs.filter(source__code=source_code)
                        raw_offers_updated += chunk_raw_offer_qs.update(
                            mapped_category=target,
                            category_mapping_status=SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
                            category_mapping_reason=SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL,
                            category_mapping_confidence=Decimal("1.000"),
                            category_mapped_at=now,
                            category_mapped_by_id=None,
                            updated_at=now,
                        )

                raw_offers_would_sync = raw_offer_qs.count()
                rule_report = {
                    "rule_index": rule.index,
                    "category_slug": rule.category_slug,
                    "category_id": str(target.id),
                    "category_name": target.name,
                    "exact_names": list(rule.exact_names),
                    "note": rule.note,
                    "products_would_assign": len(product_ids),
                    "products_updated": products_updated,
                    "raw_offers_would_sync": raw_offers_would_sync,
                    "raw_offers_updated": raw_offers_updated,
                }
                reports.append(rule_report)
                for key in totals:
                    totals[key] += int(rule_report[key])
                self.stdout.write(
                    f"#{rule.index} -> {target.name}: "
                    f"products={len(product_ids)} raw_offers={raw_offers_would_sync}"
                )

            if not is_apply:
                transaction.set_rollback(True)

        report = {
            "mode": "apply" if is_apply else "dry-run",
            "rules_json": str(rules_path),
            "source": source_code,
            "totals": totals,
            "rules": reports,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Manual uncategorized category rules completed."))
        self.stdout.write(f"Report: {report_path}")
        self.stdout.write(
            "Totals: "
            f"products_would_assign={totals['products_would_assign']}, "
            f"products_updated={totals['products_updated']}, "
            f"raw_offers_would_sync={totals['raw_offers_would_sync']}, "
            f"raw_offers_updated={totals['raw_offers_updated']}"
        )

    @staticmethod
    def _parse_rules(payload: dict) -> list[ManualRule]:
        raw_rules = payload.get("rules")
        if not isinstance(raw_rules, list):
            return []

        rules: list[ManualRule] = []
        for index, raw_rule in enumerate(raw_rules, start=1):
            if not isinstance(raw_rule, dict):
                continue
            category_slug = str(raw_rule.get("category_slug") or "").strip()
            raw_names = raw_rule.get("exact_names") or []
            if not isinstance(raw_names, list):
                raw_names = []
            exact_names = tuple(dict.fromkeys(str(name).strip() for name in raw_names if str(name).strip()))
            if not category_slug or not exact_names:
                continue
            rules.append(
                ManualRule(
                    index=index,
                    category_slug=category_slug,
                    exact_names=exact_names,
                    note=str(raw_rule.get("note") or "").strip(),
                )
            )
        return rules
