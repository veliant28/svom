from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.models import AutoDbSupplierBrandAlias
from apps.autodb.services import AutoDbBrandAliasDiagnosticsService
from apps.autodb.services.brand_alias_diagnostics import _brand_hint_key


def _parse_brand_filters(raw_value: str) -> set[str]:
    if not raw_value:
        return set()
    parts = [item.strip() for item in raw_value.split(",")]
    return {_brand_hint_key(item) for item in parts if item}


class Command(BaseCommand):
    help = "Create Auto_DB_Pro supplier brand aliases from high-confidence diagnostics."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="", help="Supplier/source code (GPL/UTR/...)")
        parser.add_argument("--all", action="store_true", help="Run across all suppliers")
        parser.add_argument("--limit", type=int, default=0, help="Limit raw offers sampled for diagnostics")
        parser.add_argument("--dry-run", action="store_true", help="Preview alias changes without writes")
        parser.add_argument("--min-confidence", type=float, default=0.9, help="Minimum confidence for alias creation")
        parser.add_argument("--only-high-confidence", action="store_true", help="Create only high-confidence alias recommendations")
        parser.add_argument("--brand", type=str, default="", help='Optional brand filter, e.g. "WIX FILTERS"')
        parser.add_argument("--manual-confirmed", action="store_true", help="Mark created aliases as manually confirmed")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        all_suppliers = bool(options.get("all"))
        limit = max(int(options.get("limit") or 0), 0)
        dry_run = bool(options.get("dry_run"))
        min_confidence = max(min(float(options.get("min_confidence") or 0.9), 1.0), 0.0)
        only_high_confidence = bool(options.get("only_high_confidence"))
        brand_filter_raw = str(options.get("brand") or "").strip()
        brand_filters = _parse_brand_filters(brand_filter_raw)
        manual_confirmed = bool(options.get("manual_confirmed"))
        export_csv = str(options.get("export_csv") or "").strip()

        if all_suppliers and supplier_code:
            raise CommandError("Use either --supplier CODE or --all.")
        if not all_suppliers and not supplier_code:
            raise CommandError("Provide --supplier CODE or --all.")

        scope = "ALL" if all_suppliers else supplier_code.upper()
        self.stdout.write(
            "Auto_DB_Pro create brand aliases started "
            f"scope={scope} limit={limit or 'none'} dry_run={dry_run} "
            f"only_high_confidence={only_high_confidence} min_confidence={min_confidence:.2f} "
            f"brand_filter={brand_filter_raw or '-'} manual_confirmed={manual_confirmed}"
        )

        service = AutoDbBrandAliasDiagnosticsService()
        stats = service.collect_brand_stats(
            supplier_code=supplier_code,
            all_suppliers=all_suppliers,
            limit=limit,
            brand_filters=brand_filters,
        )
        rows = service.diagnose(stats=stats, min_confidence=min_confidence)

        summary = {
            "diagnosed_rows": len(rows),
            "recommended_rows": 0,
            "would_create": 0,
            "created": 0,
            "updated": 0,
            "skipped_existing_same": 0,
            "skipped_not_recommended": 0,
            "skipped_low_confidence": 0,
            "skipped_ambiguous_invalid": 0,
            "failed": 0,
        }
        actions: list[dict[str, str]] = []

        for item in rows:
            if item.recommendation != "create_alias" or not item.recommended_supplier_id:
                summary["skipped_not_recommended"] += 1
                if item.recommendation in {"manual_review", "supplier_only_or_non_auto"}:
                    summary["skipped_ambiguous_invalid"] += 1
                actions.append(self._action_row(item=item, action="skip", reason=item.recommendation))
                continue
            summary["recommended_rows"] += 1

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

            summary["would_create"] += 1
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
            "sample_articles": item.sample_articles,
            "candidates": item.candidates,
        }

    def _print_summary(self, *, summary: dict[str, int]) -> None:
        self.stdout.write("Create brand aliases summary:")
        self.stdout.write(f"- diagnosed_rows: {summary['diagnosed_rows']}")
        self.stdout.write(f"- recommended_rows: {summary['recommended_rows']}")
        self.stdout.write(f"- would_create: {summary['would_create']}")
        self.stdout.write(f"- created: {summary['created']}")
        self.stdout.write(f"- updated: {summary['updated']}")
        self.stdout.write(f"- skipped_existing_same: {summary['skipped_existing_same']}")
        self.stdout.write(f"- skipped_not_recommended: {summary['skipped_not_recommended']}")
        self.stdout.write(f"- skipped_low_confidence: {summary['skipped_low_confidence']}")
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
                    "sample_articles",
                    "candidates",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
