from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.autodb.services import AutoDbArticleVariantDiagnosticsService
from apps.autodb.services.article_variant_apply_classifier import ArticleVariantApplyClassifier
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.compatibility.models import ProductFitment
from apps.supplier_imports.parsers.utils import normalize_brand


class Command(BaseCommand):
    help = "Apply strict-safe article variant link opportunities (default dry-run recommended)."

    SAFE_RECOMMENDATIONS = ArticleVariantApplyClassifier.SAFE_RECOMMENDATIONS

    def add_arguments(self, parser):
        parser.add_argument("--supplier", type=str, required=True, help="Supplier/source code, e.g. GPL")
        parser.add_argument("--brand", type=str, default="", help='Optional brand filter, e.g. "WIX FILTERS"')
        parser.add_argument(
            "--brands",
            type=str,
            default="",
            help='Optional comma-separated brand filter, e.g. "WIX FILTERS,FRAM,ERT"',
        )
        parser.add_argument("--limit", type=int, default=None, help="Global limit for selected candidates (default: 20)")
        parser.add_argument(
            "--limit-per-brand",
            type=int,
            default=0,
            help="Per-brand limit for selected candidates (0 = disabled)",
        )
        parser.add_argument("--min-confidence", type=float, default=0.9, help="Minimum confidence")
        parser.add_argument(
            "--diagnostics-limit",
            type=int,
            default=5000,
            help="Raw offers scope for diagnostics/candidate selection (must match checkpoint scope for reconciliation)",
        )
        parser.add_argument("--batch-size", type=int, default=1000, help="Diagnostics pair chunk size")
        parser.add_argument(
            "--only-remaining",
            action="store_true",
            help="Exclude already_linked_same_key before limit and run only real safe_to_apply candidates",
        )
        parser.add_argument(
            "--exclude-already-linked",
            dest="only_remaining",
            action="store_true",
            help="Alias for --only-remaining",
        )
        parser.add_argument("--dry-run", action="store_true", help="Do not write Product updates")
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV output path")

    def handle(self, *args, **options):
        supplier = str(options.get("supplier") or "").strip().lower()
        if not supplier:
            raise CommandError("Provide --supplier CODE")

        brand_filter_raw = str(options.get("brand") or "").strip()
        brands_filter_raw = str(options.get("brands") or "").strip()
        limit_option = options.get("limit")
        limit = max(int(limit_option), 1) if limit_option is not None else 20
        limit_per_brand = max(int(options.get("limit_per_brand") or 0), 0)
        min_confidence = max(min(float(options.get("min_confidence") or 0.9), 1.0), 0.9)
        diagnostics_limit = max(int(options.get("diagnostics_limit") or 5000), 1)
        batch_size = max(int(options.get("batch_size") or 1000), 1)
        only_remaining = bool(options.get("only_remaining"))
        dry_run = bool(options.get("dry_run"))
        export_csv = str(options.get("export_csv") or "").strip()

        brand_tokens_raw = []
        if brand_filter_raw:
            brand_tokens_raw.extend(brand_filter_raw.split(","))
        if brands_filter_raw:
            brand_tokens_raw.extend(brands_filter_raw.split(","))

        brand_filter = {
            item.strip().upper().replace(" ", "")
            for item in brand_tokens_raw
            if item.strip()
        }
        brand_filter_label = ", ".join(sorted(brand_filter)) if brand_filter else "-"
        effective_limit = limit
        effective_limit_label = str(limit)
        if limit_per_brand > 0 and limit_option is None:
            effective_limit = 0
            effective_limit_label = "unbounded_by_global_limit"

        self.stdout.write(
            "Auto_DB_Pro apply article variant links started "
            f"supplier={supplier} limit={effective_limit_label} limit_per_brand={limit_per_brand or '-'} "
            f"min_confidence={min_confidence:.2f} diagnostics_limit={diagnostics_limit} "
            f"dry_run={dry_run} only_remaining={only_remaining} "
            f"brand_filter={brand_filter_label}"
        )

        classifier = ArticleVariantApplyClassifier()
        service = AutoDbArticleVariantDiagnosticsService()
        report = service.diagnose(
            supplier_code=supplier,
            limit=diagnostics_limit,
            brand_filter={normalize_brand(item) for item in brand_filter} if brand_filter else None,
            batch_size=batch_size,
        )

        candidates = []
        skipped_low_confidence = 0
        skipped_low_confidence_by_brand: dict[str, int] = defaultdict(int)
        for row in report.diagnostics_rows:
            if row.recommendation not in self.SAFE_RECOMMENDATIONS:
                continue
            row_brand_key = self._brand_key(row.raw_brand)
            if row.confidence < min_confidence:
                skipped_low_confidence += 1
                skipped_low_confidence_by_brand[row_brand_key] += 1
                continue
            if not row.supplier_id or not row.corrected_article_candidate:
                continue
            if brand_filter:
                key = row_brand_key
                if key not in brand_filter:
                    continue
            candidates.append(row)

        candidates.sort(key=lambda item: (-item.confidence, str(item.raw_brand or ""), str(item.raw_article or "")))

        product_ids = {pid for row in candidates for pid in row.matched_product_ids}
        products = {str(item.id): item for item in Product.objects.in_bulk(product_ids).values()}
        quality_map = {
            (str(item.product_id), str(item.autodb_article_key or "").strip()): str(item.status or "")
            for item in AutoDbProductLinkQuality.objects.filter(product_id__in=product_ids)
        }
        excluded_map: dict[tuple[str, str], int] = defaultdict(int)
        for row in ProductFitment.objects.filter(
            product_id__in=product_ids,
            excluded_from_public_filtering=True,
        ).values("product_id", "autodb_article_key"):
            excluded_map[(str(row["product_id"]), str(row.get("autodb_article_key") or "").strip())] += 1

        evaluations: list[dict[str, object]] = []
        status_totals = {
            "safe_to_apply": 0,
            "already_linked_same_key": 0,
            "already_linked_conflicting_key": 0,
            "skipped_suspicious": 0,
            "skipped_semantic_conflict": 0,
            "skipped_low_confidence": skipped_low_confidence,
            "skipped_no_matched_product": 0,
            "skipped_missing_product": 0,
            "failed": 0,
        }
        for row in candidates:
            candidate_number = str(row.corrected_article_candidate or "").replace(" ", "")
            candidate_key = f"{row.supplier_id}:{candidate_number}" if row.supplier_id and candidate_number else ""
            if not row.matched_product_ids:
                status_totals["skipped_no_matched_product"] += 1
                evaluations.append(
                    {
                        "row": row,
                        "product_id": "",
                        "status": "skipped_no_matched_product",
                        "reason": "no_matched_product",
                        "candidate_number": candidate_number,
                        "candidate_key": candidate_key,
                    }
                )
                continue

            for product_id in row.matched_product_ids:
                product = products.get(product_id)
                if product is None:
                    status_totals["skipped_missing_product"] += 1
                    evaluations.append(
                        {
                            "row": row,
                            "product_id": product_id,
                            "status": "skipped_missing_product",
                            "reason": "product_not_found",
                            "candidate_number": candidate_number,
                            "candidate_key": candidate_key,
                        }
                    )
                    continue

                if not candidate_key:
                    status_totals["failed"] += 1
                    evaluations.append(
                        {
                            "row": row,
                            "product_id": product_id,
                            "status": "failed",
                            "reason": "empty_candidate_key",
                            "candidate_number": candidate_number,
                            "candidate_key": candidate_key,
                        }
                    )
                    continue

                current_key = str(product.autodb_article_key or "").strip()
                quality_status = quality_map.get((product_id, current_key), "")
                excluded_count = int(excluded_map.get((product_id, current_key), 0))
                status, reason = classifier.classify(
                    row=row,
                    product=product,
                    proposed_key=candidate_key,
                    min_confidence=min_confidence,
                    quality_status=quality_status,
                    excluded_count=excluded_count,
                    autodb_title=row.autodb_title,
                    autodb_category="",
                )
                if status in status_totals:
                    status_totals[status] += 1
                evaluations.append(
                    {
                        "row": row,
                        "product_id": product_id,
                        "status": status,
                        "reason": reason,
                        "candidate_number": candidate_number,
                        "candidate_key": candidate_key,
                    }
                )

        if only_remaining:
            eligible_evaluations = [item for item in evaluations if item["status"] == "safe_to_apply"]
        else:
            eligible_evaluations = list(evaluations)

        selected_evaluations = self._apply_limits(
            evaluations=eligible_evaluations,
            limit=effective_limit,
            limit_per_brand=limit_per_brand,
        )

        actions: list[dict[str, str]] = []
        to_update: list[Product] = []

        summary = {
            "candidates_total": len(candidates),
            "safe_candidates": status_totals["safe_to_apply"],
            "eligible_after_status_filter": len([item for item in evaluations if item["status"] == "safe_to_apply"]),
            "selected_for_run": len(selected_evaluations),
            "only_remaining": 1 if only_remaining else 0,
            "affected_products": 0,
            "applied": 0,
            "would_apply": 0,
            "skipped_low_confidence": status_totals["skipped_low_confidence"],
            "skipped_suspicious": 0,
            "skipped_no_matched_product": 0,
            "skipped_missing_product": 0,
            "skipped_conflicting_existing_link": 0,
            "skipped_semantic_conflict": 0,
            "skipped_already_linked": 0,
            "failed": 0,
            "status_total_safe_to_apply": status_totals["safe_to_apply"],
            "status_total_already_linked_same_key": status_totals["already_linked_same_key"],
            "status_total_already_linked_conflicting_key": status_totals["already_linked_conflicting_key"],
            "status_total_skipped_suspicious": status_totals["skipped_suspicious"],
            "status_total_skipped_semantic_conflict": status_totals["skipped_semantic_conflict"],
        }

        brand_summary: dict[str, dict[str, int | str]] = {}
        for row in candidates:
            key = self._brand_key(row.raw_brand)
            label = self._brand_label(row.raw_brand)
            stats = brand_summary.setdefault(
                key,
                {
                    "brand": label,
                    "candidates_total": 0,
                    "already_linked_same_key": 0,
                    "safe_candidates": 0,
                    "selected_for_run": 0,
                    "would_apply": 0,
                    "applied": 0,
                    "skipped_suspicious": 0,
                    "skipped_conflicting_existing_link": 0,
                    "skipped_semantic_conflict": 0,
                    "skipped_low_confidence": 0,
                },
            )
            stats["candidates_total"] += 1

        for key, value in skipped_low_confidence_by_brand.items():
            stats = brand_summary.setdefault(
                key,
                {
                    "brand": key,
                    "candidates_total": 0,
                    "already_linked_same_key": 0,
                    "safe_candidates": 0,
                    "selected_for_run": 0,
                    "would_apply": 0,
                    "applied": 0,
                    "skipped_suspicious": 0,
                    "skipped_conflicting_existing_link": 0,
                    "skipped_semantic_conflict": 0,
                    "skipped_low_confidence": 0,
                },
            )
            stats["skipped_low_confidence"] += value

        for item in evaluations:
            row = item["row"]
            key = self._brand_key(row.raw_brand)
            label = self._brand_label(row.raw_brand)
            stats = brand_summary.setdefault(
                key,
                {
                    "brand": label,
                    "candidates_total": 0,
                    "already_linked_same_key": 0,
                    "safe_candidates": 0,
                    "selected_for_run": 0,
                    "would_apply": 0,
                    "applied": 0,
                    "skipped_suspicious": 0,
                    "skipped_conflicting_existing_link": 0,
                    "skipped_semantic_conflict": 0,
                    "skipped_low_confidence": 0,
                },
            )
            status = str(item["status"])
            if status == "safe_to_apply":
                stats["safe_candidates"] += 1
            elif status == "already_linked_same_key":
                stats["already_linked_same_key"] += 1
            elif status == "skipped_suspicious":
                stats["skipped_suspicious"] += 1
            elif status == "already_linked_conflicting_key":
                stats["skipped_conflicting_existing_link"] += 1
            elif status == "skipped_semantic_conflict":
                stats["skipped_semantic_conflict"] += 1

        for item in selected_evaluations:
            row = item["row"]
            key = self._brand_key(row.raw_brand)
            label = self._brand_label(row.raw_brand)
            stats = brand_summary.setdefault(
                key,
                {
                    "brand": label,
                    "candidates_total": 0,
                    "already_linked_same_key": 0,
                    "safe_candidates": 0,
                    "selected_for_run": 0,
                    "would_apply": 0,
                    "applied": 0,
                    "skipped_suspicious": 0,
                    "skipped_conflicting_existing_link": 0,
                    "skipped_semantic_conflict": 0,
                    "skipped_low_confidence": 0,
                },
            )
            stats["selected_for_run"] += 1

        touched_products: set[str] = set()
        for item in selected_evaluations:
            row = item["row"]
            product_id = str(item["product_id"])
            status = str(item["status"])
            reason = str(item["reason"])
            candidate_number = str(item["candidate_number"])
            candidate_key = str(item["candidate_key"])

            if status != "safe_to_apply":
                if status == "already_linked_same_key":
                    summary["skipped_already_linked"] += 1
                elif status == "already_linked_conflicting_key":
                    summary["skipped_conflicting_existing_link"] += 1
                elif status == "skipped_suspicious":
                    summary["skipped_suspicious"] += 1
                elif status == "skipped_semantic_conflict":
                    summary["skipped_semantic_conflict"] += 1
                elif status == "skipped_no_matched_product":
                    summary["skipped_no_matched_product"] += 1
                elif status == "skipped_missing_product":
                    summary["skipped_missing_product"] += 1
                elif status == "failed":
                    summary["failed"] += 1
                actions.append(self._action_row(row=row, product_id=product_id, action="skip", reason=reason))
                continue

            brand_key = self._brand_key(row.raw_brand)
            if dry_run:
                summary["would_apply"] += 1
                if brand_key in brand_summary:
                    brand_summary[brand_key]["would_apply"] += 1
                actions.append(self._action_row(row=row, product_id=product_id, action="would_apply", reason="dry_run"))
                touched_products.add(product_id)
                continue

            product = products.get(product_id)
            if product is None:
                summary["skipped_missing_product"] += 1
                actions.append(self._action_row(row=row, product_id=product_id, action="skip", reason="product_not_found"))
                continue
            product.autodb_supplier_id = row.supplier_id
            product.autodb_article_number = candidate_number
            product.autodb_article_key = candidate_key
            product.catalog_source = Product.CATALOG_SOURCE_AUTODB_PRO
            to_update.append(product)
            summary["applied"] += 1
            if brand_key in brand_summary:
                brand_summary[brand_key]["applied"] += 1
            actions.append(self._action_row(row=row, product_id=product_id, action="applied", reason="safe_variant_apply"))
            touched_products.add(product_id)

        if to_update:
            with transaction.atomic():
                Product.objects.bulk_update(
                    to_update,
                    [
                        "autodb_supplier_id",
                        "autodb_article_number",
                        "autodb_article_key",
                        "catalog_source",
                        "updated_at",
                    ],
                    batch_size=200,
                )

        self.stdout.write("Article variant apply summary:")
        for key in [
            "candidates_total",
            "safe_candidates",
            "eligible_after_status_filter",
            "selected_for_run",
            "only_remaining",
            "would_apply",
            "applied",
            "skipped_low_confidence",
            "skipped_suspicious",
            "skipped_no_matched_product",
            "skipped_missing_product",
            "skipped_conflicting_existing_link",
            "skipped_semantic_conflict",
            "skipped_already_linked",
            "failed",
            "status_total_safe_to_apply",
            "status_total_already_linked_same_key",
            "status_total_already_linked_conflicting_key",
            "status_total_skipped_suspicious",
            "status_total_skipped_semantic_conflict",
        ]:
            self.stdout.write(f"- {key}: {summary.get(key, 0)}")
        summary["affected_products"] = len(touched_products)
        self.stdout.write(f"- affected_products: {summary['affected_products']}")

        self.stdout.write("Brand summary:")
        for key in sorted(brand_summary.keys()):
            stats = brand_summary[key]
            self.stdout.write(
                "- brand={brand} candidates_total={candidates_total} already_linked_same_key={already_linked_same_key} "
                "safe_candidates={safe_candidates} selected_for_run={selected_for_run} would_apply={would_apply} "
                "applied={applied} skipped_suspicious={skipped_suspicious} "
                "skipped_conflicting_existing_link={skipped_conflicting_existing_link} "
                "skipped_semantic_conflict={skipped_semantic_conflict} "
                "skipped_low_confidence={skipped_low_confidence}".format(**stats)
            )

        for row in actions[:30]:
            self.stdout.write(
                f"- product_id={row['product_id']} raw_brand={row['raw_brand']} raw_article={row['raw_article']} "
                f"corrected={row['corrected_article_candidate']} autodb_key={row['autodb_article_key'] or '-'} "
                f"autodb_title={row['autodb_title'] or '-'} confidence={row['confidence']} action={row['action']} reason={row['reason']}"
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=actions)
            self.stdout.write(f"CSV export: {export_csv}")

        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")

    def _action_row(self, *, row, product_id: str, action: str, reason: str) -> dict[str, str]:
        return {
            "product_id": str(product_id),
            "raw_brand": str(row.raw_brand or ""),
            "raw_article": str(row.raw_article or ""),
            "raw_product_name": str(row.raw_product_name or ""),
            "autodb_title": str(row.autodb_title or ""),
            "supplier_id": str(row.supplier_id or ""),
            "corrected_article_candidate": str(row.corrected_article_candidate or ""),
            "autodb_article_key": f"{row.supplier_id}:{str(row.corrected_article_candidate or '').replace(' ', '')}" if row.supplier_id and row.corrected_article_candidate else "",
            "confidence": f"{row.confidence:.2f}",
            "recommendation": str(row.recommendation),
            "action": action,
            "reason": reason,
            "sample_offer_id": str(row.sample_offer_id or ""),
        }

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "raw_brand",
                    "raw_article",
                    "raw_product_name",
                    "autodb_title",
                    "supplier_id",
                    "corrected_article_candidate",
                    "autodb_article_key",
                    "confidence",
                    "recommendation",
                    "action",
                    "reason",
                    "sample_offer_id",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _apply_limits(self, *, evaluations: list[dict[str, object]], limit: int, limit_per_brand: int) -> list[dict[str, object]]:
        if limit_per_brand <= 0:
            return evaluations[:limit]

        selected: list[dict[str, object]] = []
        brand_counts: dict[str, int] = defaultdict(int)
        for item in evaluations:
            row = item["row"]
            brand_key = self._brand_key(row.raw_brand)
            if brand_counts[brand_key] >= limit_per_brand:
                continue
            selected.append(item)
            brand_counts[brand_key] += 1
            if limit > 0 and len(selected) >= limit:
                break
        return selected

    def _brand_key(self, raw_brand: str) -> str:
        return str(raw_brand or "").upper().replace(" ", "")

    def _brand_label(self, raw_brand: str) -> str:
        value = str(raw_brand or "").strip()
        return value or "-"
