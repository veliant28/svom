from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbBrandAliasDiagnosticsService


def _parse_brand_filters(raw_value: str) -> set[str]:
    from apps.autodb.services.brand_alias_diagnostics import _brand_hint_key

    if not raw_value:
        return set()
    parts = [item.strip() for item in raw_value.split(",")]
    return {_brand_hint_key(item) for item in parts if item}


class Command(BaseCommand):
    help = "Diagnose raw supplier brands and suggest safe Auto_DB_Pro supplier aliases."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, default="", help="Supplier/source code (GPL/UTR/...)")
        parser.add_argument("--all", action="store_true", help="Run across all suppliers")
        parser.add_argument("--limit", type=int, default=0, help="Limit raw offers sampled for diagnostics")
        parser.add_argument("--brand", type=str, default="", help='Optional brand filter, e.g. "WIX FILTERS,MANN-FILTER"')
        parser.add_argument("--min-confidence", type=float, default=0.9, help="Suggestion confidence threshold")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier_code = str(options.get("supplier") or "").strip().lower()
        all_suppliers = bool(options.get("all"))
        limit = max(int(options.get("limit") or 0), 0)
        min_confidence = max(min(float(options.get("min_confidence") or 0.9), 1.0), 0.0)
        brand_filter = _parse_brand_filters(str(options.get("brand") or "").strip())
        export_csv = str(options.get("export_csv") or "").strip()

        if all_suppliers and supplier_code:
            raise CommandError("Use either --supplier CODE or --all.")
        if not all_suppliers and not supplier_code:
            raise CommandError("Provide --supplier CODE or --all.")

        scope = "ALL" if all_suppliers else supplier_code.upper()
        self.stdout.write(
            "Auto_DB_Pro brand alias diagnostics started "
            f"scope={scope} limit={limit or 'none'} min_confidence={min_confidence:.2f} "
            f"brand_filter={str(options.get('brand') or '-').strip() or '-'}"
        )

        service = AutoDbBrandAliasDiagnosticsService()
        stats = service.collect_brand_stats(
            supplier_code=supplier_code,
            all_suppliers=all_suppliers,
            limit=limit,
            brand_filters=brand_filter,
        )
        rows = service.diagnose(stats=stats, min_confidence=min_confidence)

        self._print_summary(rows=rows)
        self._print_top(rows=rows, limit=50)
        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- report_mode: diagnostics-only")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")

    def _print_summary(self, *, rows):
        total_offers = sum(item.offers for item in rows)
        total_alias_exists = sum(1 for item in rows if item.current_alias)
        total_recommended = sum(1 for item in rows if item.recommendation == "create_alias")
        total_manual = sum(1 for item in rows if item.recommendation == "manual_review")
        total_invalid = sum(1 for item in rows if item.recommendation == "supplier_only_or_non_auto")
        self.stdout.write("Brand alias diagnostics summary:")
        self.stdout.write(f"- total raw brands: {len(rows)}")
        self.stdout.write(f"- total offers in scope: {total_offers}")
        self.stdout.write(f"- exact supplier match rows: {sum(1 for item in rows if item.exact_supplier_match)}")
        self.stdout.write(f"- current alias rows: {total_alias_exists}")
        self.stdout.write(f"- recommended aliases: {total_recommended}")
        self.stdout.write(f"- manual review rows: {total_manual}")
        self.stdout.write(f"- supplier_only/non_auto rows: {total_invalid}")

    def _print_top(self, *, rows, limit: int):
        self.stdout.write(f"Top brand diagnostics (top {limit}):")
        for item in rows[:limit]:
            self.stdout.write(
                f"- raw_brand={item.raw_brand or '-'} normalized_brand={item.normalized_brand or '-'} "
                f"offers={item.offers} unique_articles={item.unique_articles} exact_match={'yes' if item.exact_supplier_match else 'no'} "
                f"relaxed_candidates={item.relaxed_candidates} current_alias={'yes' if item.current_alias else 'no'} "
                f"recommended={item.recommended_supplier_id or '-'} confidence={item.confidence:.2f} "
                f"recommendation={item.recommendation} reason={item.reason} examples={item.sample_articles or '-'} "
                f"candidates={item.candidates or '-'}"
            )

    def _export_csv(self, *, path: str, rows):
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
                    "exact_supplier_match",
                    "relaxed_candidates",
                    "current_alias",
                    "current_alias_supplier_id",
                    "recommended_supplier_id",
                    "recommended_supplier_name",
                    "confidence",
                    "recommendation",
                    "reason",
                    "sample_articles",
                    "candidates",
                ],
            )
            writer.writeheader()
            for item in rows:
                writer.writerow(
                    {
                        "raw_brand": item.raw_brand,
                        "normalized_brand": item.normalized_brand,
                        "offers": item.offers,
                        "unique_articles": item.unique_articles,
                        "exact_supplier_match": item.exact_supplier_match,
                        "relaxed_candidates": item.relaxed_candidates,
                        "current_alias": item.current_alias,
                        "current_alias_supplier_id": item.current_alias_supplier_id,
                        "recommended_supplier_id": item.recommended_supplier_id,
                        "recommended_supplier_name": item.recommended_supplier_name,
                        "confidence": f"{item.confidence:.2f}",
                        "recommendation": item.recommendation,
                        "reason": item.reason,
                        "sample_articles": item.sample_articles,
                        "candidates": item.candidates,
                    }
                )
