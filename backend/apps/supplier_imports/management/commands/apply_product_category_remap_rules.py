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
class RemapRule:
    index: int
    from_category_id: str
    to_category_id: str
    from_category_path: str
    to_category_path: str
    product_ids: tuple[str, ...]


def _chunked(items: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class Command(BaseCommand):
    help = (
        "Apply category remap rules produced by audit_product_category_distribution. "
        "Runs in dry-run mode by default; use --apply to persist updates."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--rules-json",
            default="/tmp/svom_category_remap_audit.json",
            help="Path to audit JSON report with proposed_rules.",
        )
        parser.add_argument(
            "--rule-index",
            action="append",
            type=int,
            default=None,
            help="1-based rule index from JSON. Can be passed multiple times.",
        )
        parser.add_argument(
            "--max-rules",
            type=int,
            default=None,
            help="Limit how many rules to process (after filtering by --rule-index).",
        )
        parser.add_argument(
            "--max-products",
            type=int,
            default=None,
            help="Global cap on affected products across all rules.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Batch size for bulk updates.",
        )
        parser.add_argument(
            "--no-sync-raw-offers",
            action="store_true",
            help="Do not update SupplierRawOffer.mapped_category for affected products.",
        )
        parser.add_argument(
            "--lock-manual",
            action="store_true",
            help=(
                "When syncing raw offers, also set mapping status to manual_mapped "
                "with confidence=1.000 to avoid future auto-remap drift."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist updates. Without this flag command runs as dry-run.",
        )
        parser.add_argument(
            "--report-json",
            default="/tmp/svom_category_remap_apply_report.json",
            help="Where to write apply/dry-run report JSON.",
        )

    def handle(self, *args, **options):
        rules_json_path = Path(str(options["rules_json"])).expanduser().resolve()
        if not rules_json_path.exists():
            raise CommandError(f"Rules JSON not found: {rules_json_path}")

        is_apply = bool(options["apply"])
        batch_size = max(100, int(options["batch_size"] or 1000))
        sync_raw_offers = not bool(options["no_sync_raw_offers"])
        lock_manual = bool(options["lock_manual"])
        max_rules = int(options["max_rules"]) if options["max_rules"] else None
        max_products = int(options["max_products"]) if options["max_products"] else None
        requested_rule_indexes = options.get("rule_index") or []
        report_json_path = Path(str(options["report_json"])).expanduser().resolve()

        payload = json.loads(rules_json_path.read_text(encoding="utf-8"))
        rules = self._parse_rules(payload=payload)
        if not rules:
            raise CommandError("No proposed_rules found in JSON payload.")

        selected = self._select_rules(
            rules=rules,
            requested_rule_indexes=requested_rule_indexes,
            max_rules=max_rules,
            max_products=max_products,
        )
        if not selected:
            raise CommandError("No rules selected after filters.")

        category_ids = {rule.from_category_id for rule in selected} | {rule.to_category_id for rule in selected}
        existing_category_ids = {
            str(category_id)
            for category_id in Category.objects.filter(id__in=category_ids).values_list("id", flat=True)
        }
        missing_categories = sorted(str(category_id) for category_id in category_ids if str(category_id) not in existing_category_ids)
        if missing_categories:
            raise CommandError(f"Some category IDs from rules do not exist: {missing_categories}")

        self.stdout.write(
            f"Running {'APPLY' if is_apply else 'DRY-RUN'} for {len(selected)} rule(s); "
            f"sync_raw_offers={sync_raw_offers}, lock_manual={lock_manual}"
        )

        rule_reports: list[dict] = []
        total_products_would_move = 0
        total_raw_offers_would_move = 0
        total_products_updated = 0
        total_raw_offers_updated = 0

        with transaction.atomic():
            for rule in selected:
                candidate_product_ids = list(rule.product_ids)
                if not candidate_product_ids:
                    continue

                eligible_product_ids = list(
                    Product.objects.filter(
                        id__in=candidate_product_ids,
                        category_id=rule.from_category_id,
                    ).values_list("id", flat=True)
                )
                eligible_product_ids = [str(product_id) for product_id in eligible_product_ids]
                products_would_move = len(eligible_product_ids)

                raw_offers_would_move = 0
                if sync_raw_offers and eligible_product_ids:
                    raw_offers_would_move = SupplierRawOffer.objects.filter(
                        matched_product_id__in=eligible_product_ids,
                        mapped_category_id=rule.from_category_id,
                    ).count()

                products_updated = 0
                raw_offers_updated = 0

                if is_apply and eligible_product_ids:
                    for chunk in _chunked(eligible_product_ids, batch_size):
                        products_updated += Product.objects.filter(
                            id__in=chunk,
                            category_id=rule.from_category_id,
                        ).update(category_id=rule.to_category_id)

                        if sync_raw_offers:
                            update_kwargs: dict = {"mapped_category_id": rule.to_category_id}
                            if lock_manual:
                                update_kwargs.update(
                                    {
                                        "category_mapping_status": SupplierRawOffer.CATEGORY_MAPPING_STATUS_MANUAL_MAPPED,
                                        "category_mapping_reason": SupplierRawOffer.CATEGORY_MAPPING_REASON_MANUAL,
                                        "category_mapping_confidence": Decimal("1.000"),
                                        "category_mapped_at": timezone.now(),
                                        "category_mapped_by_id": None,
                                    }
                                )
                            raw_offers_updated += SupplierRawOffer.objects.filter(
                                matched_product_id__in=chunk,
                                mapped_category_id=rule.from_category_id,
                            ).update(**update_kwargs)

                total_products_would_move += products_would_move
                total_raw_offers_would_move += raw_offers_would_move
                total_products_updated += products_updated
                total_raw_offers_updated += raw_offers_updated

                rule_report = {
                    "rule_index": rule.index,
                    "from_category_id": rule.from_category_id,
                    "from_category_path": rule.from_category_path,
                    "to_category_id": rule.to_category_id,
                    "to_category_path": rule.to_category_path,
                    "candidate_products": len(candidate_product_ids),
                    "products_would_move": products_would_move,
                    "raw_offers_would_move": raw_offers_would_move,
                    "products_updated": products_updated,
                    "raw_offers_updated": raw_offers_updated,
                }
                rule_reports.append(rule_report)

                self.stdout.write(
                    f"#{rule.index} {rule.from_category_path} => {rule.to_category_path} | "
                    f"products={products_would_move} | raw_offers={raw_offers_would_move}"
                )

            if not is_apply:
                transaction.set_rollback(True)

        report = {
            "mode": "apply" if is_apply else "dry-run",
            "source_rules_json": str(rules_json_path),
            "options": {
                "rule_index": requested_rule_indexes,
                "max_rules": max_rules,
                "max_products": max_products,
                "batch_size": batch_size,
                "sync_raw_offers": sync_raw_offers,
                "lock_manual": lock_manual,
            },
            "totals": {
                "rules_processed": len(rule_reports),
                "products_would_move": total_products_would_move,
                "raw_offers_would_move": total_raw_offers_would_move,
                "products_updated": total_products_updated,
                "raw_offers_updated": total_raw_offers_updated,
            },
            "rules": rule_reports,
        }

        report_json_path.parent.mkdir(parents=True, exist_ok=True)
        report_json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        self.stdout.write(self.style.SUCCESS("Remap execution completed."))
        self.stdout.write(f"Report: {report_json_path}")
        self.stdout.write(
            "Totals: "
            f"products_would_move={total_products_would_move}, "
            f"raw_offers_would_move={total_raw_offers_would_move}, "
            f"products_updated={total_products_updated}, "
            f"raw_offers_updated={total_raw_offers_updated}"
        )

    @staticmethod
    def _parse_rules(*, payload: dict) -> list[RemapRule]:
        raw_rules = payload.get("proposed_rules")
        if not isinstance(raw_rules, list):
            return []

        result: list[RemapRule] = []
        for index, raw_rule in enumerate(raw_rules, start=1):
            if not isinstance(raw_rule, dict):
                continue
            from_category_id = str(raw_rule.get("from_category_id") or "").strip()
            to_category_id = str(raw_rule.get("to_category_id") or "").strip()
            if not from_category_id or not to_category_id or from_category_id == to_category_id:
                continue

            product_ids_raw = raw_rule.get("product_ids") or []
            if not isinstance(product_ids_raw, list):
                product_ids_raw = []
            product_ids = tuple(str(item).strip() for item in product_ids_raw if str(item).strip())

            result.append(
                RemapRule(
                    index=index,
                    from_category_id=from_category_id,
                    to_category_id=to_category_id,
                    from_category_path=str(raw_rule.get("from_category_path") or ""),
                    to_category_path=str(raw_rule.get("to_category_path") or ""),
                    product_ids=product_ids,
                )
            )
        return result

    @staticmethod
    def _select_rules(
        *,
        rules: list[RemapRule],
        requested_rule_indexes: list[int],
        max_rules: int | None,
        max_products: int | None,
    ) -> list[RemapRule]:
        selected: list[RemapRule] = []

        if requested_rule_indexes:
            allowed = set(int(value) for value in requested_rule_indexes if int(value) > 0)
            for rule in rules:
                if rule.index in allowed:
                    selected.append(rule)
        else:
            selected = list(rules)

        if max_rules is not None:
            selected = selected[: max(0, max_rules)]

        if max_products is None:
            return selected

        remaining = max(0, max_products)
        capped: list[RemapRule] = []
        for rule in selected:
            if remaining <= 0:
                break
            if len(rule.product_ids) <= remaining:
                capped.append(rule)
                remaining -= len(rule.product_ids)
                continue

            capped.append(
                RemapRule(
                    index=rule.index,
                    from_category_id=rule.from_category_id,
                    to_category_id=rule.to_category_id,
                    from_category_path=rule.from_category_path,
                    to_category_path=rule.to_category_path,
                    product_ids=rule.product_ids[:remaining],
                )
            )
            remaining = 0
            break

        return capped
