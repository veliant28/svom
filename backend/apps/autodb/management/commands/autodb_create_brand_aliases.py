from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services import AutoDbBrandAliasDiagnosticsService
from apps.autodb.services.brand_alias_diagnostics import _brand_hint_key
from apps.supplier_imports.parsers.utils import normalize_brand


def _parse_brand_filters(raw_value: str) -> set[str]:
    if not raw_value:
        return set()
    parts = [item.strip() for item in raw_value.split(",")]
    return {_brand_hint_key(item) for item in parts if item}


class Command(BaseCommand):
    help = "Create Auto_DB_Pro supplier brand aliases from high-confidence diagnostics."
    UNSAFE_AMBIGUOUS_HINTS = {
        _brand_hint_key("AT"),
        _brand_hint_key("K2"),
        _brand_hint_key("LSA"),
        _brand_hint_key("MITKA"),
        _brand_hint_key("ТМК"),
        _brand_hint_key("Без бренду"),
        _brand_hint_key("Без бренда"),
        _brand_hint_key("NO BRAND"),
    }

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="", help="Supplier/source code (GPL/UTR/...)")
        parser.add_argument("--all", action="store_true", help="Run across all suppliers")
        parser.add_argument("--limit", type=int, default=0, help="Limit raw offers sampled for diagnostics")
        parser.add_argument("--dry-run", action="store_true", help="Preview alias changes without writes")
        parser.add_argument("--apply", action="store_true", help="Apply writes explicitly")
        parser.add_argument("--min-confidence", type=float, default=0.9, help="Minimum confidence for alias creation")
        parser.add_argument("--only-high-confidence", action="store_true", help="Create only high-confidence alias recommendations")
        parser.add_argument("--from-csv", type=str, default="", help="Read opportunities from CSV")
        parser.add_argument("--only-auto-confirm", action="store_true", help="Use only rows with can_auto_confirm=1 from CSV")
        parser.add_argument("--brand", type=str, default="", help='Optional brand filter, e.g. "WIX FILTERS"')
        parser.add_argument("--manual-confirmed", action="store_true", help="Mark created aliases as manually confirmed")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        all_suppliers = bool(options.get("all"))
        limit = max(int(options.get("limit") or 0), 0)
        dry_run = bool(options.get("dry_run"))
        do_apply = bool(options.get("apply"))
        min_confidence = max(min(float(options.get("min_confidence") or 0.9), 1.0), 0.0)
        only_high_confidence = bool(options.get("only_high_confidence"))
        from_csv = str(options.get("from_csv") or "").strip()
        only_auto_confirm = bool(options.get("only_auto_confirm"))
        brand_filter_raw = str(options.get("brand") or "").strip()
        brand_filters = _parse_brand_filters(brand_filter_raw)
        manual_confirmed = bool(options.get("manual_confirmed"))
        export_csv = str(options.get("export_csv") or "").strip()

        if from_csv and (all_suppliers or brand_filters):
            raise CommandError("--from-csv cannot be combined with --all or --brand filter.")
        if from_csv and dry_run == do_apply:
            raise CommandError("When using --from-csv specify exactly one mode: --dry-run or --apply.")
        if (not from_csv) and all_suppliers and supplier_code:
            raise CommandError("Use either --supplier CODE or --all.")
        if (not from_csv) and not all_suppliers and not supplier_code:
            raise CommandError("Provide --supplier CODE or --all.")
        if do_apply and dry_run:
            raise CommandError("Specify only one mode: --dry-run or --apply.")

        scope = "ALL" if all_suppliers else supplier_code.upper()
        self.stdout.write(
            "Auto_DB_Pro create brand aliases started "
            f"scope={scope} limit={limit or 'none'} dry_run={dry_run} "
            f"only_high_confidence={only_high_confidence} min_confidence={min_confidence:.2f} "
            f"brand_filter={brand_filter_raw or '-'} manual_confirmed={manual_confirmed} "
            f"from_csv={from_csv or '-'} only_auto_confirm={only_auto_confirm}"
        )

        use_csv_mode = bool(from_csv)
        service = AutoDbBrandAliasDiagnosticsService()
        rows: list[Any]
        if use_csv_mode:
            rows = self._load_rows_from_csv(path=from_csv)
        else:
            stats = service.collect_brand_stats(
                supplier_code=supplier_code,
                all_suppliers=all_suppliers,
                limit=limit,
                brand_filters=brand_filters,
            )
            rows = service.diagnose(stats=stats, min_confidence=min_confidence)

        summary = {
            "diagnosed_rows": len(rows),
            "candidates": 0,
            "recommended_rows": 0,
            "would_create": 0,
            "would_update": 0,
            "created": 0,
            "updated": 0,
            "skipped_existing_same": 0,
            "skipped_not_recommended": 0,
            "skipped_manual_review": 0,
            "skipped_low_confidence": 0,
            "skipped_unsafe_ambiguous": 0,
            "skipped_ambiguous_invalid": 0,
            "failed": 0,
        }
        actions: list[dict[str, str]] = []

        for item in rows:
            if item.recommendation != "create_alias" or not item.recommended_supplier_id:
                summary["skipped_not_recommended"] += 1
                if item.recommendation == "manual_review":
                    summary["skipped_manual_review"] += 1
                if item.recommendation in {"manual_review", "supplier_only_or_non_auto"}:
                    summary["skipped_ambiguous_invalid"] += 1
                actions.append(self._action_row(item=item, action="skip", reason=item.recommendation))
                continue
            summary["recommended_rows"] += 1

            if use_csv_mode and only_auto_confirm and not bool(getattr(item, "can_auto_confirm", False)):
                summary["skipped_manual_review"] += 1
                actions.append(self._action_row(item=item, action="skip", reason="not_auto_confirm"))
                continue

            if self._is_unsafe_ambiguous_brand(getattr(item, "raw_brand", "")):
                summary["skipped_unsafe_ambiguous"] += 1
                actions.append(self._action_row(item=item, action="skip", reason="unsafe_ambiguous_brand"))
                continue

            if only_high_confidence and item.confidence < min_confidence:
                summary["skipped_low_confidence"] += 1
                actions.append(self._action_row(item=item, action="skip", reason="low_confidence"))
                continue
            if item.confidence < min_confidence:
                summary["skipped_low_confidence"] += 1
                actions.append(self._action_row(item=item, action="skip", reason="low_confidence"))
                continue

            existing = AutoDbSupplierBrandAlias.objects.filter(normalized_raw_brand=item.normalized_brand).first()
            if existing and existing.autodb_supplier_id == int(item.recommended_supplier_id) and existing.is_active:
                summary["skipped_existing_same"] += 1
                actions.append(self._action_row(item=item, action="skip", reason="existing_same"))
                continue

            summary["candidates"] += 1
            summary["would_create"] += 1
            if existing:
                summary["would_update"] += 1
            if dry_run:
                actions.append(self._action_row(item=item, action="dry_run_create", reason="recommended"))
                continue

            source = AutoDbSupplierBrandAlias.SOURCE_MANUAL if manual_confirmed else AutoDbSupplierBrandAlias.SOURCE_AUTO
            alias, created = service.upsert_alias(
                raw_brand=item.raw_brand,
                normalized_brand=item.normalized_brand,
                supplier_id=int(item.recommended_supplier_id),
                supplier_name=item.recommended_supplier_name,
                confidence=float(item.confidence),
                manual_confirmed=manual_confirmed,
                note=f"auto-created from diagnostics reason={item.reason}",
                source=source,
            )
            if created:
                summary["created"] += 1
                actions.append(self._action_row(item=item, action="created", reason=f"alias_id={alias.id}"))
            else:
                summary["updated"] += 1
                actions.append(self._action_row(item=item, action="updated", reason=f"alias_id={alias.id}"))

        self._print_summary(summary=summary)
        self._print_examples(actions=actions, limit=20)
        if export_csv:
            self._export_csv(path=export_csv, rows=actions)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")
        if dry_run:
            self.stdout.write("- mode: dry-run (no alias writes)")

    def _action_row(self, *, item, action: str, reason: str) -> dict[str, str]:
        return {
            "raw_brand": item.raw_brand,
            "normalized_brand": item.normalized_brand,
            "offers": str(item.offers),
            "unique_articles": str(item.unique_articles),
            "recommended_supplier_id": str(item.recommended_supplier_id or ""),
            "recommended_supplier_name": item.recommended_supplier_name,
            "confidence": f"{item.confidence:.2f}",
            "recommendation": item.recommendation,
            "action": action,
            "reason": reason,
            "can_auto_confirm": "1" if bool(getattr(item, "can_auto_confirm", False)) else "0",
            "sample_articles": item.sample_articles,
            "candidates": item.candidates,
        }

    def _print_summary(self, *, summary: dict[str, int]) -> None:
        self.stdout.write("Create brand aliases summary:")
        self.stdout.write(f"- diagnosed_rows: {summary['diagnosed_rows']}")
        self.stdout.write(f"- candidates: {summary['candidates']}")
        self.stdout.write(f"- recommended_rows: {summary['recommended_rows']}")
        self.stdout.write(f"- would_create: {summary['would_create']}")
        self.stdout.write(f"- would_update: {summary['would_update']}")
        self.stdout.write(f"- created: {summary['created']}")
        self.stdout.write(f"- updated: {summary['updated']}")
        self.stdout.write(f"- skipped_existing_same: {summary['skipped_existing_same']}")
        self.stdout.write(f"- skipped_not_recommended: {summary['skipped_not_recommended']}")
        self.stdout.write(f"- skipped_manual_review: {summary['skipped_manual_review']}")
        self.stdout.write(f"- skipped_low_confidence: {summary['skipped_low_confidence']}")
        self.stdout.write(f"- skipped_unsafe_ambiguous: {summary['skipped_unsafe_ambiguous']}")
        self.stdout.write(f"- skipped_ambiguous_invalid: {summary['skipped_ambiguous_invalid']}")
        self.stdout.write(f"- failed: {summary['failed']}")

    def _print_examples(self, *, actions: list[dict[str, str]], limit: int) -> None:
        self.stdout.write(f"Alias actions (top {limit}):")
        for item in actions[:limit]:
            self.stdout.write(
                f"- raw_brand={item['raw_brand'] or '-'} normalized_brand={item['normalized_brand'] or '-'} "
                f"supplier={item['recommended_supplier_id'] or '-'} confidence={item['confidence']} "
                f"action={item['action']} reason={item['reason']} "
                f"examples={item['sample_articles'] or '-'} candidates={item['candidates'] or '-'}"
            )

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "raw_brand",
                    "normalized_brand",
                    "offers",
                    "unique_articles",
                    "recommended_supplier_id",
                    "recommended_supplier_name",
                    "confidence",
                    "recommendation",
                    "action",
                    "reason",
                    "can_auto_confirm",
                    "sample_articles",
                    "candidates",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _load_rows_from_csv(self, *, path: str) -> list[Any]:
        csv_path = Path(path).expanduser()
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")
        out: list[Any] = []
        with csv_path.open(encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                raw_brand = str(row.get("raw_brand") or "").strip()
                normalized_brand = normalize_brand(raw_brand)
                recommendation = str(row.get("recommended_action") or row.get("recommendation") or "").strip()
                proposed_supplier_id = str(row.get("proposed_supplier_id") or row.get("recommended_supplier_id") or "").strip()
                try:
                    supplier_id = int(proposed_supplier_id) if proposed_supplier_id else None
                except (TypeError, ValueError):
                    supplier_id = None
                confidence_raw = str(row.get("confidence") or "0").strip() or "0"
                try:
                    confidence = float(confidence_raw)
                except (TypeError, ValueError):
                    confidence = 0.0
                can_auto_confirm_raw = str(row.get("can_auto_confirm") or "").strip().lower()
                can_auto_confirm = can_auto_confirm_raw in {"1", "true", "yes"}
                out.append(
                    type(
                        "CsvAliasRow",
                        (),
                        {
                            "raw_brand": raw_brand,
                            "normalized_brand": normalized_brand,
                            "offers": int(str(row.get("product_count") or row.get("offers") or "0") or 0),
                            "unique_articles": 0,
                            "exact_supplier_match": str(row.get("exact_supplier_name_match") or "").strip() in {"1", "true", "yes"},
                            "relaxed_candidates": int(str(row.get("fuzzy_supplier_candidates") or "0") or 0),
                            "current_alias": False,
                            "current_alias_supplier_id": None,
                            "recommended_supplier_id": supplier_id,
                            "recommended_supplier_name": str(row.get("proposed_supplier_name") or row.get("recommended_supplier_name") or "").strip(),
                            "confidence": confidence,
                            "recommendation": recommendation,
                            "reason": str(row.get("reason") or "").strip(),
                            "candidates": str(row.get("possible_supplier_matches") or row.get("candidates") or "").strip(),
                            "sample_articles": str(row.get("examples") or row.get("sample_articles") or "").strip(),
                            "can_auto_confirm": can_auto_confirm,
                        },
                    )()
                )
        return out

    def _is_unsafe_ambiguous_brand(self, raw_brand: str) -> bool:
        hint = _brand_hint_key(raw_brand)
        return hint in self.UNSAFE_AMBIGUOUS_HINTS
