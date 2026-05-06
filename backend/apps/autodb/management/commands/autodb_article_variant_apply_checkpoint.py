from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbArticleVariantApplyCheckpointService
from apps.supplier_imports.parsers.utils import normalize_brand


def _parse_brand_filters(raw_value: str) -> set[str]:
    if not raw_value:
        return set()
    parts = [item.strip() for item in raw_value.split(",")]
    return {normalize_brand(item) for item in parts if normalize_brand(item)}


class Command(BaseCommand):
    help = "Read-only checkpoint for remaining Auto_DB_Pro article-variant apply candidates."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--limit", type=int, default=5000, help="Max raw offers to sample")
        parser.add_argument("--brand", type=str, default="", help='Optional brand filter, e.g. "WIX FILTERS"')
        parser.add_argument("--batch-size", type=int, default=1000, help="Diagnostics pair chunk size")
        parser.add_argument("--min-confidence", type=float, default=0.9, help="Minimum confidence for safe_to_apply")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        supplier = str(options.get("supplier") or "").strip().lower()
        if not supplier:
            raise CommandError("Provide --supplier CODE")

        limit = max(int(options.get("limit") or 5000), 1)
        brand_filter_raw = str(options.get("brand") or "").strip()
        brand_filter = _parse_brand_filters(brand_filter_raw)
        batch_size = max(int(options.get("batch_size") or 1000), 1)
        min_confidence = max(min(float(options.get("min_confidence") or 0.9), 1.0), 0.0)
        export_csv = str(options.get("export_csv") or "").strip()

        self.stdout.write(
            "Auto_DB_Pro article variant apply checkpoint started "
            f"supplier={supplier} limit={limit} brand_filter={brand_filter_raw or '-'} min_confidence={min_confidence:.2f}"
        )

        service = AutoDbArticleVariantApplyCheckpointService()
        report = service.build_report(
            supplier_code=supplier,
            limit=limit,
            brand_filter=brand_filter or None,
            batch_size=batch_size,
            min_confidence=min_confidence,
        )

        self._print_summary(report)
        self._print_brand_summary(report)
        self._print_remaining_by_brand(report)
        self._print_polmo_review(report)
        self._print_recommended_next(report)

        if export_csv:
            self._export_csv(path=export_csv, report=report)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- report_mode: checkpoint/read-only (no Product/SupplierRawOffer/SupplierOffer writes)")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")

    def _print_summary(self, report):
        rows = report.checkpoint_rows
        counter = {}
        for row in rows:
            counter[row.status] = counter.get(row.status, 0) + 1

        self.stdout.write("Checkpoint summary:")
        self.stdout.write(f"- total raw offers: {report.diagnostics_report.total_raw_offers}")
        self.stdout.write(f"- total pairs: {report.diagnostics_report.total_pairs}")
        self.stdout.write(f"- diagnostics rows: {len(report.diagnostics_report.diagnostics_rows)}")
        self.stdout.write(f"- checkpoint rows: {len(rows)}")
        self.stdout.write(f"- remaining_safe_to_apply: {counter.get('safe_to_apply', 0)}")
        self.stdout.write(f"- already_linked_same_key: {counter.get('already_linked_same_key', 0)}")
        self.stdout.write(f"- already_linked_conflicting_key: {counter.get('already_linked_conflicting_key', 0)}")
        self.stdout.write(f"- skipped_suspicious: {counter.get('skipped_suspicious', 0)}")
        self.stdout.write(f"- skipped_semantic_conflict: {counter.get('skipped_semantic_conflict', 0)}")
        self.stdout.write(f"- needs_manual_review: {counter.get('needs_manual_review', 0)}")
        self.stdout.write(f"- exact_not_found: {counter.get('exact_not_found', 0)}")
        self.stdout.write(f"- non_auto_ignore: {counter.get('non_auto_ignore', 0)}")

    def _print_brand_summary(self, report):
        self.stdout.write("Brand summary:")
        for item in report.brand_summaries:
            self.stdout.write(
                f"- brand={item.raw_brand or '-'} supplier_id={item.resolved_supplier_id or '-'} "
                f"total_pairs={item.total_pairs} linked_before_or_current={item.linked_before_or_current} "
                f"variant_would_find_total={item.variant_would_find_total} already_linked_same_key={item.already_linked_same_key} "
                f"already_linked_conflicting_key={item.already_linked_conflicting_key} remaining_safe_to_apply={item.remaining_safe_to_apply} "
                f"needs_manual_review={item.needs_manual_review} suspicious={item.suspicious} "
                f"semantic_conflict={item.semantic_conflict} exact_not_found={item.exact_not_found} "
                f"recommended_next_action={item.recommended_next_action}"
            )

    def _print_remaining_by_brand(self, report):
        self.stdout.write("Remaining safe_to_apply by brand:")
        remaining = [item for item in report.brand_summaries if item.remaining_safe_to_apply > 0]
        if not remaining:
            self.stdout.write("- -")
            return
        for item in sorted(remaining, key=lambda row: (-row.remaining_safe_to_apply, row.raw_brand or "")):
            self.stdout.write(
                f"- brand={item.raw_brand or '-'} remaining_safe_to_apply={item.remaining_safe_to_apply} "
                f"already_linked_same_key={item.already_linked_same_key} suspicious={item.suspicious} "
                f"semantic_conflict={item.semantic_conflict} action={item.recommended_next_action}"
            )

    def _print_polmo_review(self, report):
        polmo = report.polmo_summary
        self.stdout.write("POLMO review-only summary:")
        self.stdout.write(f"- safe_to_apply: {polmo.safe_to_apply}")
        self.stdout.write(f"- suspicious: {polmo.suspicious}")
        self.stdout.write(f"- semantic_conflict: {polmo.semantic_conflict}")
        self.stdout.write(f"- already_linked_same_key: {polmo.already_linked_same_key}")
        self.stdout.write(f"- already_linked_conflicting_key: {polmo.already_linked_conflicting_key}")
        self.stdout.write(f"- related_to_known_suspicious_products: {polmo.related_to_known_suspicious_products}")
        self.stdout.write(f"- exhaust_to_shock_risk: {polmo.exhaust_to_shock_risk}")
        self.stdout.write(f"- recommended_next_action: {polmo.recommended_next_action}")
        self.stdout.write("POLMO examples (top 20):")
        if not polmo.examples:
            self.stdout.write("- -")
            return
        for row in polmo.examples:
            self.stdout.write(
                f"- product_id={row.product_id or '-'} raw_article={row.raw_article or '-'} corrected={row.corrected_article_candidate or '-'} "
                f"status={row.status} current_key={row.current_autodb_article_key or '-'} proposed_key={row.proposed_autodb_article_key or '-'} "
                f"reason={row.reason} related_to_known_suspicious={'yes' if row.related_to_known_suspicious_product else 'no'}"
            )
            self.stdout.write(
                f"  raw_product_name={row.raw_product_name or '-'} autodb_title={row.autodb_title or '-'} autodb_category={row.autodb_category or '-'}"
            )

    def _print_recommended_next(self, report):
        recommendation = report.recommended_next
        self.stdout.write("Recommended next batch:")
        self.stdout.write(f"- recommended_next_brand: {recommendation.recommended_next_brand or '-'}")
        self.stdout.write(f"- recommended_limit: {recommendation.recommended_limit}")
        self.stdout.write(f"- expected_safe_candidates: {recommendation.expected_safe_candidates}")
        self.stdout.write(f"- command_to_run_next_dry_run: {recommendation.command_to_run_next_dry_run or '-'}")
        self.stdout.write(f"- command_to_run_next_real: {recommendation.command_to_run_next_real or '-'}")

    def _export_csv(self, *, path: str, report) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "supplier",
                    "raw_brand",
                    "resolved_supplier_id",
                    "raw_article",
                    "normalized_article",
                    "corrected_article_candidate",
                    "product_id",
                    "current_autodb_article_key",
                    "proposed_autodb_article_key",
                    "status",
                    "confidence",
                    "reason",
                    "raw_product_name",
                    "autodb_title",
                    "autodb_category",
                    "recommended_action",
                ],
            )
            writer.writeheader()
            for row in report.checkpoint_rows:
                writer.writerow(
                    {
                        "supplier": row.supplier,
                        "raw_brand": row.raw_brand,
                        "resolved_supplier_id": row.resolved_supplier_id,
                        "raw_article": row.raw_article,
                        "normalized_article": row.normalized_article,
                        "corrected_article_candidate": row.corrected_article_candidate,
                        "product_id": row.product_id,
                        "current_autodb_article_key": row.current_autodb_article_key,
                        "proposed_autodb_article_key": row.proposed_autodb_article_key,
                        "status": row.status,
                        "confidence": f"{row.confidence:.2f}",
                        "reason": row.reason,
                        "raw_product_name": row.raw_product_name,
                        "autodb_title": row.autodb_title,
                        "autodb_category": row.autodb_category,
                        "recommended_action": row.recommended_action,
                    }
                )
