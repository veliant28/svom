from __future__ import annotations

from dataclasses import dataclass

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services import AutoDbArticleVariantApplyCheckpointService
from apps.autodb.services.article_variant_apply_classifier import ArticleVariantApplyClassifier
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.parsers.utils import normalize_brand


@dataclass(frozen=True)
class _ApplyView:
    status: str
    reason: str
    excluded_before_classification: bool = False


class Command(BaseCommand):
    help = "Debug side-by-side candidate status: checkpoint vs apply logic for one brand."

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--brand", type=str, required=True, help='Brand, e.g. "WIX FILTERS"')
        parser.add_argument("--limit", type=int, default=20, help="Rows to print")
        parser.add_argument("--scope-limit", type=int, default=5000, help="Raw offers scope for diagnostics/checkpoint")
        parser.add_argument("--batch-size", type=int, default=1000, help="Diagnostics pair chunk size")
        parser.add_argument("--min-confidence", type=float, default=0.9, help="Minimum confidence for apply logic")

    def handle(self, *args, **options):
        supplier = str(options.get("supplier") or "").strip().lower()
        brand_raw = str(options.get("brand") or "").strip()
        if not supplier or not brand_raw:
            raise CommandError("Provide --supplier and --brand")

        row_limit = max(int(options.get("limit") or 20), 1)
        scope_limit = max(int(options.get("scope_limit") or 5000), 1)
        batch_size = max(int(options.get("batch_size") or 1000), 1)
        min_confidence = max(min(float(options.get("min_confidence") or 0.9), 1.0), 0.9)

        brand_filter = {normalize_brand(brand_raw)}
        checkpoint_service = AutoDbArticleVariantApplyCheckpointService()
        report = checkpoint_service.build_report(
            supplier_code=supplier,
            limit=scope_limit,
            brand_filter=brand_filter,
            batch_size=batch_size,
            min_confidence=min_confidence,
        )

        classifier = ArticleVariantApplyClassifier()
        apply_index = self._build_apply_index(
            report=report,
            brand_filter=brand_filter,
            min_confidence=min_confidence,
            classifier=classifier,
        )

        brand_rows = [row for row in report.checkpoint_rows if row.normalized_brand in brand_filter]
        safe_rows = [row for row in brand_rows if row.status == classifier.STATUS_SAFE_TO_APPLY]
        target_rows = safe_rows[:row_limit] if safe_rows else brand_rows[:row_limit]

        if not safe_rows:
            self.stdout.write("No checkpoint safe_to_apply rows for this brand in selected scope; showing first rows by brand.")

        self.stdout.write(
            "Auto_DB_Pro debug candidate selection "
            f"supplier={supplier} brand={brand_raw} scope_limit={scope_limit} min_confidence={min_confidence:.2f}"
        )
        self.stdout.write(
            f"- brand_rows={len(brand_rows)} checkpoint_safe_rows={len(safe_rows)} printed_rows={len(target_rows)}"
        )

        mismatch_count = 0
        for row in target_rows:
            key = (
                row.normalized_brand,
                row.raw_article,
                row.product_id,
                row.proposed_autodb_article_key,
                row.sample_offer_id,
            )
            apply_view = apply_index.get(key, _ApplyView(status="missing_in_apply_index", reason="not_present_in_apply_scope"))
            mismatch_reason = self._mismatch_reason(row_status=row.status, apply_view=apply_view)
            if mismatch_reason != "match":
                mismatch_count += 1
            self.stdout.write(
                f"- raw_brand={row.raw_brand or '-'} raw_article={row.raw_article or '-'} product_id={row.product_id or '-'} "
                f"current_autodb_article_key={row.current_autodb_article_key or '-'} "
                f"corrected_article_candidate={row.corrected_article_candidate or '-'} "
                f"proposed_autodb_article_key={row.proposed_autodb_article_key or '-'} "
                f"status_by_checkpoint={row.status} status_by_apply={apply_view.status}"
            )
            self.stdout.write(
                f"  reason_by_checkpoint={row.reason or '-'} reason_by_apply={apply_view.reason or '-'} why_mismatch={mismatch_reason}"
            )

        self.stdout.write(f"- mismatches_in_printed_rows: {mismatch_count}")
        self.stdout.write("- report_mode: debug/read-only (no Product/SupplierRawOffer/SupplierOffer writes)")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")

    def _build_apply_index(
        self,
        *,
        report,
        brand_filter: set[str],
        min_confidence: float,
        classifier: ArticleVariantApplyClassifier,
    ) -> dict[tuple[str, str, str, str, str], _ApplyView]:
        diagnostics_rows = report.diagnostics_report.diagnostics_rows
        product_ids = sorted({pid for row in diagnostics_rows for pid in row.matched_product_ids})
        products = {str(item.id): item for item in Product.objects.in_bulk(product_ids).values()}
        quality_map = {
            (str(item.product_id), str(item.autodb_article_key or "").strip()): str(item.status or "")
            for item in AutoDbProductLinkQuality.objects.filter(product_id__in=product_ids)
        }
        excluded_map: dict[tuple[str, str], int] = {}
        for row in ProductFitment.objects.filter(
            product_id__in=product_ids,
            excluded_from_public_filtering=True,
        ).values("product_id", "autodb_article_key"):
            key = (str(row["product_id"]), str(row.get("autodb_article_key") or "").strip())
            excluded_map[key] = int(excluded_map.get(key, 0)) + 1

        out: dict[tuple[str, str, str, str, str], _ApplyView] = {}
        for row in diagnostics_rows:
            normalized_brand = normalize_brand(row.raw_brand or row.normalized_brand)
            if brand_filter and normalized_brand not in brand_filter:
                continue
            if row.recommendation not in classifier.SAFE_RECOMMENDATIONS:
                continue
            if row.confidence < min_confidence:
                continue
            if not row.supplier_id or not row.corrected_article_candidate:
                continue
            candidate_number = str(row.corrected_article_candidate or "").replace(" ", "")
            proposed_key = f"{row.supplier_id}:{candidate_number}" if row.supplier_id and candidate_number else ""

            if not row.matched_product_ids:
                index_key = (normalized_brand, row.raw_article, "", proposed_key, row.sample_offer_id)
                out[index_key] = _ApplyView(
                    status="skipped_no_matched_product",
                    reason="no_matched_product",
                    excluded_before_classification=True,
                )
                continue

            for product_id in row.matched_product_ids:
                product = products.get(str(product_id))
                if product is None:
                    index_key = (normalized_brand, row.raw_article, str(product_id), proposed_key, row.sample_offer_id)
                    out[index_key] = _ApplyView(
                        status="skipped_missing_product",
                        reason="product_not_found",
                        excluded_before_classification=True,
                    )
                    continue
                current_key = str(product.autodb_article_key or "").strip()
                quality_status = quality_map.get((str(product.id), current_key), "")
                excluded_count = int(excluded_map.get((str(product.id), current_key), 0))
                status, reason = classifier.classify(
                    row=row,
                    product=product,
                    proposed_key=proposed_key,
                    min_confidence=min_confidence,
                    quality_status=quality_status,
                    excluded_count=excluded_count,
                    autodb_title=row.autodb_title,
                    autodb_category="",
                )
                index_key = (normalized_brand, row.raw_article, str(product.id), proposed_key, row.sample_offer_id)
                out[index_key] = _ApplyView(status=status, reason=reason)
        return out

    def _mismatch_reason(self, *, row_status: str, apply_view: _ApplyView) -> str:
        if row_status == apply_view.status:
            return "match"
        if apply_view.excluded_before_classification:
            return f"excluded_by_apply_filter:{apply_view.reason}"
        return f"classification_diff:{row_status}!={apply_view.status}"

