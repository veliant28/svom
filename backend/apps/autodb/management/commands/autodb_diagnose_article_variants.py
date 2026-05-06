from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbArticleVariantDiagnosticsService
from apps.supplier_imports.parsers.utils import normalize_brand


def _parse_brand_filters(raw_value: str) -> set[str]:
    if not raw_value:
        return set()
    parts = [item.strip() for item in raw_value.split(",")]
    return {normalize_brand(item) for item in parts if normalize_brand(item)}


class Command(BaseCommand):
    help = "Diagnose Auto_DB_Pro article variant/normalization misses for supplier raw offers (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=5000, help="Max raw offers to sample")
        parser.add_argument("--brand", type=str, default="", help='Optional brand filter, e.g. "WIX FILTERS"')
        parser.add_argument("--batch-size", type=int, default=1000, help="Pair chunk size used for remote-query estimate")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier = str(options.get("supplier") or "").strip().lower()
        if not supplier:
            raise CommandError("Provide --supplier CODE")

        limit = max(int(options.get("limit") or 5000), 1)
        brand_filter_raw = str(options.get("brand") or "").strip()
        brand_filter = _parse_brand_filters(brand_filter_raw)
        batch_size = max(int(options.get("batch_size") or 1000), 1)
        export_csv = str(options.get("export_csv") or "").strip()

        self.stdout.write(
            "Auto_DB_Pro article variants diagnostics started "
            f"supplier={supplier} limit={limit} brand_filter={brand_filter_raw or '-'} batch_size={batch_size}"
        )

        service = AutoDbArticleVariantDiagnosticsService()
        report = service.diagnose(
            supplier_code=supplier,
            limit=limit,
            brand_filter=brand_filter,
            batch_size=batch_size,
        )

        self._print_summary(report)
        self._print_recommendation_summary(report)
        self._print_brand_breakdown(report)
        self._print_examples(report)
        self._print_remote_explanation(report)

        if export_csv:
            self._export_csv(path=export_csv, report=report)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- report_mode: diagnostics-only/read-only")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")

    def _print_summary(self, report):
        self.stdout.write("Article variants diagnostics summary:")
        self.stdout.write(f"- total raw offers: {report.total_raw_offers}")
        self.stdout.write(f"- total pairs: {report.total_pairs}")
        self.stdout.write(f"- linked pairs (local exact): {report.linked_pairs}")
        self.stdout.write(f"- unresolved pairs: {report.unresolved_pairs}")
        self.stdout.write(f"- unresolved pairs with supplier resolved: {report.unresolved_supplier_resolved_pairs}")
        self.stdout.write(f"- diagnostics rows: {len(report.diagnostics_rows)}")

    def _print_recommendation_summary(self, report):
        counters: dict[str, int] = {}
        for row in report.diagnostics_rows:
            counters[row.recommendation] = counters.get(row.recommendation, 0) + 1

        self.stdout.write("Recommendation breakdown:")
        for key in [
            "exact_not_found",
            "try_variant",
            "try_external_sku",
            "article_in_raw_name",
            "old_new_number_candidate",
            "needs_manual_mapping",
            "non_auto_ignore",
        ]:
            self.stdout.write(f"- {key}: {counters.get(key, 0)}")

    def _print_brand_breakdown(self, report):
        self.stdout.write("Top brand article diagnostics:")
        for item in report.brand_breakdown:
            self.stdout.write(
                f"- brand={item.raw_brand} normalized={item.normalized_brand} supplier_id={item.supplier_id or '-'} "
                f"total_pairs={item.total_pairs} linked_pairs={item.linked_pairs} not_found_pairs={item.not_found_pairs} "
                f"raw_name_alt_article={item.raw_name_alt_article_count} variant_lookup_would_find={item.variant_lookup_would_find_count} "
                f"needs_manual_mapping={item.needs_manual_mapping_count} top_patterns={','.join(item.top_article_patterns) or '-'}"
            )

    def _print_examples(self, report):
        rows = list(report.diagnostics_rows)

        def _print_block(title: str, predicate, limit: int = 15):
            self.stdout.write(title)
            printed = 0
            for row in rows:
                if not predicate(row):
                    continue
                self.stdout.write(
                    f"- offer_id={row.sample_offer_id} raw_brand={row.raw_brand or '-'} supplier_id={row.supplier_id or '-'} "
                    f"raw_article={row.raw_article or '-'} normalized_article={row.normalized_article or '-'} "
                    f"external_sku={row.external_sku or '-'} corrected={row.corrected_article_candidate or '-'} "
                    f"autodb_title={row.autodb_title or '-'} source={row.corrected_article_source or '-'} recommendation={row.recommendation} "
                    f"confidence={row.confidence:.2f} reason={row.reason}"
                )
                self.stdout.write(
                    f"  variants={','.join(row.article_variants[:8]) or '-'} alt_tokens={','.join(row.raw_name_alt_tokens[:8]) or '-'}"
                )
                self.stdout.write(
                    f"  lookup=articles:{int(row.lookup_articles)} article_numbers:{int(row.lookup_article_numbers)} "
                    f"article_m:{int(row.lookup_article_m)} article_nn:{int(row.lookup_article_nn)} "
                    f"article_oe:{int(row.lookup_article_oe)} article_cross:{int(row.lookup_article_cross)} article_ean:{int(row.lookup_article_ean)}"
                )
                printed += 1
                if printed >= limit:
                    break
            if printed == 0:
                self.stdout.write("- -")

        _print_block(
            "Examples where variant would match:",
            lambda row: row.recommendation in {"try_variant", "article_in_raw_name", "try_external_sku", "old_new_number_candidate"},
            limit=20,
        )
        _print_block(
            "Examples where raw name contains better article:",
            lambda row: row.recommendation == "article_in_raw_name",
            limit=20,
        )
        _print_block(
            "Examples where external_sku is unsafe:",
            lambda row: row.reason == "external_sku_unverified_for_gpl",
            limit=20,
        )

    def _print_remote_explanation(self, report):
        remote = report.remote_summary
        self.stdout.write("Remote query explanation:")
        self.stdout.write(
            f"- estimated_remote_queries={remote.estimated_remote_queries} (chunk-based; batch_size={remote.batch_size}, unresolved_pairs={remote.unresolved_pairs})"
        )
        self.stdout.write(f"- remote_not_checked_reason={remote.remote_not_checked_reason}")
        self.stdout.write("- sample_pairs_that_would_be_sent_to_remote:")
        if not remote.remote_examples:
            self.stdout.write("  - -")
            return
        for brand, article, supplier_id in remote.remote_examples[:20]:
            self.stdout.write(f"  - raw_brand={brand or '-'} raw_article={article or '-'} supplier_id={supplier_id or '-'}")

    def _export_csv(self, *, path: str, report):
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "supplier",
                    "raw_brand",
                    "normalized_brand",
                    "supplier_id",
                    "raw_article",
                    "normalized_article",
                    "raw_product_name",
                    "external_sku",
                    "article_variants",
                    "raw_name_alt_tokens",
                    "raw_name_contains_alt_article",
                    "external_sku_looks_like_manufacturer_article",
                    "lookup_articles",
                    "lookup_article_numbers",
                    "lookup_article_m",
                    "lookup_article_nn",
                    "lookup_article_oe",
                    "lookup_article_cross",
                    "lookup_article_ean",
                    "corrected_article_candidate",
                    "corrected_article_source",
                    "autodb_title",
                    "recommendation",
                    "reason",
                    "confidence",
                    "matched_product_ids",
                    "sample_offer_id",
                ],
            )
            writer.writeheader()
            for row in report.diagnostics_rows:
                writer.writerow(
                    {
                        "supplier": row.supplier,
                        "raw_brand": row.raw_brand,
                        "normalized_brand": row.normalized_brand,
                        "supplier_id": row.supplier_id,
                        "raw_article": row.raw_article,
                        "normalized_article": row.normalized_article,
                        "raw_product_name": row.raw_product_name,
                        "external_sku": row.external_sku,
                        "article_variants": "|".join(row.article_variants),
                        "raw_name_alt_tokens": "|".join(row.raw_name_alt_tokens),
                        "raw_name_contains_alt_article": int(row.raw_name_contains_alt_article),
                        "external_sku_looks_like_manufacturer_article": int(row.external_sku_looks_like_manufacturer_article),
                        "lookup_articles": int(row.lookup_articles),
                        "lookup_article_numbers": int(row.lookup_article_numbers),
                        "lookup_article_m": int(row.lookup_article_m),
                        "lookup_article_nn": int(row.lookup_article_nn),
                        "lookup_article_oe": int(row.lookup_article_oe),
                        "lookup_article_cross": int(row.lookup_article_cross),
                        "lookup_article_ean": int(row.lookup_article_ean),
                        "corrected_article_candidate": row.corrected_article_candidate,
                        "corrected_article_source": row.corrected_article_source,
                        "autodb_title": row.autodb_title,
                        "recommendation": row.recommendation,
                        "reason": row.reason,
                        "confidence": f"{row.confidence:.2f}",
                        "matched_product_ids": "|".join(row.matched_product_ids),
                        "sample_offer_id": row.sample_offer_id,
                    }
                )
