from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.product_category_enrichment import AutoDbProductCategoryEnrichmentService
from apps.catalog.models import AutoDbProductLinkQuality, Product


@dataclass
class CategoryDiagnosticsSummary:
    total_checked: int = 0
    articles_missing: int = 0
    article_prd_missing: int = 0
    article_links_missing: int = 0
    prd_missing: int = 0
    has_category_candidates: int = 0
    skipped_manual_locked: int = 0
    skipped_suspicious_link: int = 0
    skipped_semantic_conflict: int = 0
    category_update_possible: int = 0


class Command(BaseCommand):
    help = "Diagnose Product category enrichment from local Auto_DB_Pro rows."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", default="", help="Product UUID")
        parser.add_argument("--only-linked", action="store_true", help="Process only products linked to Auto_DB_Pro")
        parser.add_argument("--limit", type=int, default=0, help="Limit products count in batch mode")
        parser.add_argument(
            "--status",
            type=str,
            default="",
            help="Filter by dry-run status, e.g. skipped_no_autodb_category",
        )
        parser.add_argument("--export-csv", type=str, default="", help="Optional CSV path")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        only_linked = bool(options.get("only_linked"))
        limit = max(int(options.get("limit") or 0), 0)
        status_filter = str(options.get("status") or "").strip()
        export_csv = str(options.get("export_csv") or "").strip()

        service = AutoDbProductCategoryEnrichmentService()

        if product_id and not only_linked and limit == 0 and not status_filter and not export_csv:
            product = self._get_product_or_error(product_id=product_id)
            diagnostics = service.build_diagnostics(product=product)
            self._print_single(product=product, diagnostics=diagnostics)
            return

        qs = service.build_queryset(
            only_linked=only_linked or bool(product_id),
            only_missing=False,
            product_id=product_id,
        )
        if limit > 0:
            qs = qs[:limit]
        if not product_id and not only_linked and limit == 0:
            raise CommandError("Provide --product-id or use batch mode flags like --only-linked/--limit.")

        rows: list[dict[str, str]] = []
        summary = CategoryDiagnosticsSummary()

        for product in qs.iterator(chunk_size=200):
            diagnostics = service.build_diagnostics(product=product)
            dry_result = service.enrich_product(product=product, dry_run=True)
            quality_status = self._link_quality_status(product=product, article_key=diagnostics.bridge_article_key)
            manual_lock = bool(getattr(product, "category_manually_locked", False))
            current_source = str(getattr(getattr(product, "category", None), "source", "") or "")
            manual_category = manual_lock or current_source == "manual"

            row = {
                "product_id": str(product.id),
                "display_name": str(product.get_localized_name(locale="uk") or product.name or ""),
                "autodb_article_key": diagnostics.bridge_article_key,
                "autodb_supplier_id": str(diagnostics.bridge_supplier_id or ""),
                "autodb_article_number": diagnostics.bridge_article_number,
                "current_category": diagnostics.current_category_name,
                "current_category_source": diagnostics.current_category_source,
                "category_manual_locked": str(int(manual_category)),
                "articles_row_exists": str(int(bool(diagnostics.article_row))),
                "article_prd_rows_count": str(len(diagnostics.article_prd_rows)),
                "article_links_rows_count": str(len(diagnostics.article_links_rows)),
                "prd_candidates_count": str(len(diagnostics.prd_rows)),
                "chosen_prd_candidate": str(diagnostics.chosen_prd_id or ""),
                "skip_or_update_reason": dry_result.status,
                "link_quality_status": quality_status,
                "suspicious_or_manual_review": str(
                    int(
                        diagnostics.suspicious_link
                        or quality_status in {"suspicious", "needs_manual_review"}
                    )
                ),
                "autodb_article_title": diagnostics.autodb_article_title,
                "autodb_prd_title": diagnostics.autodb_prd_title,
            }

            if status_filter and row["skip_or_update_reason"] != status_filter:
                continue

            rows.append(row)
            summary.total_checked += 1
            if row["articles_row_exists"] != "1":
                summary.articles_missing += 1
            if row["article_prd_rows_count"] == "0":
                summary.article_prd_missing += 1
            if row["article_links_rows_count"] == "0":
                summary.article_links_missing += 1
            if row["prd_candidates_count"] == "0":
                summary.prd_missing += 1
            if row["chosen_prd_candidate"]:
                summary.has_category_candidates += 1
            if dry_result.status == "skipped_manual_locked":
                summary.skipped_manual_locked += 1
            if dry_result.status == "skipped_suspicious_link":
                summary.skipped_suspicious_link += 1
            if diagnostics.suspicious_link and "conflict" in str(diagnostics.suspicious_reason or ""):
                summary.skipped_semantic_conflict += 1
            if dry_result.status in {"updated", "skipped_hash_unchanged"}:
                summary.category_update_possible += 1

        self.stdout.write("Auto_DB_Pro product category diagnostics batch summary:")
        self.stdout.write(f"- total_checked: {summary.total_checked}")
        self.stdout.write(f"- articles_missing: {summary.articles_missing}")
        self.stdout.write(f"- article_prd_missing: {summary.article_prd_missing}")
        self.stdout.write(f"- article_links_missing: {summary.article_links_missing}")
        self.stdout.write(f"- prd_missing: {summary.prd_missing}")
        self.stdout.write(f"- has_category_candidates: {summary.has_category_candidates}")
        self.stdout.write(f"- skipped_manual_locked: {summary.skipped_manual_locked}")
        self.stdout.write(f"- skipped_suspicious_link: {summary.skipped_suspicious_link}")
        self.stdout.write(f"- skipped_semantic_conflict: {summary.skipped_semantic_conflict}")
        self.stdout.write(f"- category_update_possible: {summary.category_update_possible}")

        for item in rows[:40]:
            self.stdout.write(
                "- product_id={product_id} status={skip_or_update_reason} article_key={autodb_article_key} "
                "manual_locked={category_manual_locked} quality={link_quality_status} "
                "articles={articles_row_exists} article_prd={article_prd_rows_count} article_links={article_links_rows_count} "
                "prd_candidates={prd_candidates_count} chosen_prd={chosen_prd_candidate}".format(**item)
            )

        if export_csv:
            self._export_csv(path=export_csv, rows=rows)
            self.stdout.write(f"CSV export: {export_csv}")
        self.stdout.write("- UTR calls: 0")

    def _get_product_or_error(self, *, product_id: str) -> Product:
        try:
            return Product.objects.select_related("brand", "category", "category__parent").get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise CommandError(f"Product not found: {product_id}") from exc

    def _print_single(self, *, product: Product, diagnostics) -> None:
        self.stdout.write("Auto_DB_Pro product category diagnostics:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- product_name: {product.name or '-'}")
        self.stdout.write(f"- current_category: {diagnostics.current_category_name or '-'} ({diagnostics.current_category_id or '-'})")
        self.stdout.write(f"- current_category_source: {diagnostics.current_category_source or '-'}")
        self.stdout.write(f"- current_category_autodb_prd_id: {diagnostics.current_category_autodb_prd_id or '-'}")
        self.stdout.write(f"- bridge.autodb_supplier_id: {diagnostics.bridge_supplier_id or '-'}")
        self.stdout.write(f"- bridge.autodb_article_number: {diagnostics.bridge_article_number or '-'}")
        self.stdout.write(f"- bridge.autodb_article_key: {diagnostics.bridge_article_key or '-'}")

        self.stdout.write("- article_prd rows:")
        if not diagnostics.article_prd_rows:
            self.stdout.write("  - -")
        for row in diagnostics.article_prd_rows:
            self.stdout.write(
                f"  - supplierid={row.get('supplierid') or row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={row.get('datasupplierarticlenumber') or row.get('DataSupplierArticleNumber') or '-'} "
                f"productid={row.get('productid') or row.get('productId') or row.get('ProductId') or '-'}"
            )

        self.stdout.write("- articles row:")
        if not diagnostics.article_row:
            self.stdout.write("  - -")
        else:
            self.stdout.write(
                f"  - supplierid={diagnostics.article_row.get('supplierid') or diagnostics.article_row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={diagnostics.article_row.get('datasupplierarticlenumber') or diagnostics.article_row.get('DataSupplierArticleNumber') or '-'} "
                f"NormalizedDescription={diagnostics.article_row.get('NormalizedDescription') or diagnostics.article_row.get('normalizeddescription') or '-'} "
                f"Description={diagnostics.article_row.get('Description') or diagnostics.article_row.get('description') or '-'}"
            )

        self.stdout.write("- article_links rows:")
        if not diagnostics.article_links_rows:
            self.stdout.write("  - -")
        for row in diagnostics.article_links_rows:
            self.stdout.write(
                f"  - supplierid={row.get('supplierid') or row.get('supplierId') or '-'} "
                f"datasupplierarticlenumber={row.get('datasupplierarticlenumber') or row.get('DataSupplierArticleNumber') or '-'} "
                f"productid={row.get('productid') or row.get('productId') or row.get('ProductId') or '-'}"
            )

        self.stdout.write("- prd candidates:")
        if not diagnostics.prd_rows:
            self.stdout.write("  - -")
        for row in diagnostics.prd_rows:
            self.stdout.write(
                f"  - id={row.get('id') or row.get('productid') or row.get('productId') or '-'} "
                f"parentid={row.get('parentid') or row.get('parentId') or '-'} "
                f"description={row.get('description') or '-'} "
                f"fulldescription={row.get('fulldescription') or row.get('fullDescription') or '-'}"
            )

        self.stdout.write(f"- chosen_prd_id: {diagnostics.chosen_prd_id or '-'}")
        self.stdout.write(f"- chosen_source: {diagnostics.chosen_source or '-'}")
        self.stdout.write(f"- chosen_prd_row: {diagnostics.chosen_prd_row or '-'}")
        self.stdout.write(f"- autodb_article_title: {diagnostics.autodb_article_title or '-'}")
        self.stdout.write(f"- autodb_prd_title: {diagnostics.autodb_prd_title or '-'}")
        self.stdout.write(f"- suspicious_link: {diagnostics.suspicious_link}")
        self.stdout.write(f"- suspicious_reason: {diagnostics.suspicious_reason or '-'}")
        self.stdout.write(f"- proposed_category: {diagnostics.proposed_category_name or '-'} ({diagnostics.proposed_category_id or '-'})")
        self.stdout.write(f"- proposed_category_source: {diagnostics.proposed_category_source or '-'}")
        self.stdout.write(f"- proposed_category_autodb_prd_id: {diagnostics.proposed_category_autodb_prd_id or '-'}")
        self.stdout.write(f"- skipped_reason: {diagnostics.skipped_reason or '-'}")
        self.stdout.write("- UTR calls: 0")

    def _link_quality_status(self, *, product: Product, article_key: str) -> str:
        normalized_key = str(article_key or "").strip()
        if not normalized_key:
            return ""
        quality = (
            AutoDbProductLinkQuality.objects.filter(
                product=product,
                autodb_article_key=normalized_key,
            )
            .order_by("-checked_at", "-updated_at")
            .first()
        )
        if quality is None:
            return ""
        return str(quality.status or "")

    def _export_csv(self, *, path: str, rows: list[dict[str, str]]) -> None:
        export_path = Path(path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        with export_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "product_id",
                    "display_name",
                    "autodb_article_key",
                    "autodb_supplier_id",
                    "autodb_article_number",
                    "current_category",
                    "current_category_source",
                    "category_manual_locked",
                    "articles_row_exists",
                    "article_prd_rows_count",
                    "article_links_rows_count",
                    "prd_candidates_count",
                    "chosen_prd_candidate",
                    "skip_or_update_reason",
                    "link_quality_status",
                    "suspicious_or_manual_review",
                    "autodb_article_title",
                    "autodb_prd_title",
                ],
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
