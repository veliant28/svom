from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.remote_config import AutoDbRemoteConfigError, AutoDbRemoteConfigValidator
from apps.autodb.services.product_category_enrichment import AutoDbProductCategoryEnrichmentService
from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Debug local/remote related rows (article_prd/article_links/prd) for one linked Product."

    def add_arguments(self, parser):
        parser.add_argument("--product-id", required=True, help="Product UUID")
        parser.add_argument("--allow-remote", action="store_true", help="Enable remote Auto_DB_Pro checks")
        parser.add_argument("--sample-limit", type=int, default=5, help="Sample rows per table")

    def handle(self, *args, **options):
        product_id = str(options.get("product_id") or "").strip()
        allow_remote = bool(options.get("allow_remote"))
        sample_limit = max(int(options.get("sample_limit") or 5), 1)

        try:
            product = Product.objects.select_related("category").get(pk=product_id)
        except Product.DoesNotExist as exc:
            raise CommandError(f"Product not found: {product_id}") from exc

        supplier_id = self._safe_int(getattr(product, "autodb_supplier_id", None))
        article_number = str(getattr(product, "autodb_article_number", "") or "").strip()
        article_key = str(getattr(product, "autodb_article_key", "") or "").strip()

        self.stdout.write("Auto_DB_Pro linked related debug:")
        self.stdout.write(f"- product_id: {product.id}")
        self.stdout.write(f"- display_name: {product.get_localized_name(locale='uk') or product.name or '-'}")
        self.stdout.write(f"- autodb_supplier_id: {supplier_id or '-'}")
        self.stdout.write(f"- autodb_article_number: {article_number or '-'}")
        self.stdout.write(f"- autodb_article_key: {article_key or '-'}")

        if supplier_id is None or not article_number:
            self.stdout.write("- skip_reason: no_autodb_bridge")
            self.stdout.write("- UTR calls: 0")
            return

        storage = AutoDbRawCloneStorage()
        category_service = AutoDbProductCategoryEnrichmentService(storage=storage)
        diagnostics = category_service.build_diagnostics(product=product)
        dry_result = category_service.enrich_product(product=product, dry_run=True)

        self.stdout.write("- diagnose_status:")
        self.stdout.write(f"  - dry_run_status: {dry_result.status}")
        self.stdout.write(f"  - skipped_reason: {diagnostics.skipped_reason or '-'}")
        self.stdout.write(f"  - suspicious_link: {diagnostics.suspicious_link}")
        self.stdout.write(f"  - suspicious_reason: {diagnostics.suspicious_reason or '-'}")
        self.stdout.write(f"  - article_row_exists: {bool(diagnostics.article_row)}")
        self.stdout.write(f"  - local_article_prd_rows_count: {len(diagnostics.article_prd_rows)}")
        self.stdout.write(f"  - local_article_links_rows_count: {len(diagnostics.article_links_rows)}")
        self.stdout.write(f"  - local_prd_candidates_count: {len(diagnostics.prd_rows)}")
        self.stdout.write(f"  - chosen_prd_id: {diagnostics.chosen_prd_id or '-'}")

        for table in ("article_prd", "article_links", "prd"):
            self._print_local_rows(
                storage=storage,
                table=table,
                supplier_id=supplier_id,
                article_number=article_number,
                sample_limit=sample_limit,
            )

        if allow_remote:
            try:
                AutoDbRemoteConfigValidator.ensure_remote_ready(allow_remote=True)
            except AutoDbRemoteConfigError as exc:
                raise CommandError(f"Remote Auto_DB_Pro not ready: {exc}") from exc
            for table in ("article_prd", "article_links", "prd"):
                self._print_remote_rows(
                    storage=storage,
                    table=table,
                    supplier_id=supplier_id,
                    article_number=article_number,
                    sample_limit=sample_limit,
                )

        self.stdout.write("- why_diagnose_missing:")
        if not diagnostics.article_prd_rows:
            self.stdout.write("  - article_prd_missing")
        if not diagnostics.article_links_rows:
            self.stdout.write("  - article_links_missing")
        if not diagnostics.prd_rows:
            self.stdout.write("  - prd_missing")
        if diagnostics.article_prd_rows or diagnostics.article_links_rows or diagnostics.prd_rows:
            self.stdout.write("  - some_related_rows_present")
        self.stdout.write("- UTR calls: 0")
        self.stdout.write("- price/stock changed: 0")
        self.stdout.write("- product name/category changed: 0")
        self.stdout.write("- compatibility filtering: disabled/no-op unchanged")

    def _print_local_rows(
        self,
        *,
        storage: AutoDbRawCloneStorage,
        table: str,
        supplier_id: int,
        article_number: str,
        sample_limit: int,
    ) -> None:
        storage.ensure_table(table)
        columns = list(storage.get_local_columns(table))
        if not columns:
            self.stdout.write(f"- local {table}: table_missing_or_no_columns")
            return

        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_col = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "partsdatasupplierarticlenumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        product_col = find_column_name(columns, ["productId", "productid", "ProductId", "prdId", "prdid", "id"])

        if table == "prd":
            rows = storage.fetch_local_rows(table=table, limit=sample_limit, columns=columns)
            self.stdout.write(f"- local prd total_columns={len(columns)} sample_count={len(rows)}")
            for row in rows[:sample_limit]:
                self.stdout.write(
                    f"  - sample id={row.get('id') or row.get('productid') or row.get('productId') or '-'} "
                    f"description={row.get('description') or row.get('Description') or '-'}"
                )
            return

        if not supplier_col or not article_col:
            self.stdout.write(f"- local {table}: relation_columns_missing supplier={supplier_col or '-'} article={article_col or '-'}")
            return

        rows = storage.fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=2000,
            columns=columns,
        )
        self.stdout.write(
            f"- local {table} count={len(rows)} supplier_col={supplier_col} article_col={article_col} "
            f"product_col={product_col or '-'}"
        )
        for row in rows[:sample_limit]:
            self.stdout.write(
                f"  - supplier={row.get(supplier_col)} article={row.get(article_col)} "
                f"product={row.get(product_col) if product_col else '-'}"
            )

    def _print_remote_rows(
        self,
        *,
        storage: AutoDbRawCloneStorage,
        table: str,
        supplier_id: int,
        article_number: str,
        sample_limit: int,
    ) -> None:
        columns = storage.get_remote_columns(table)
        if not columns:
            self.stdout.write(f"- remote {table}: columns_missing")
            return
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
        article_col = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "partsdatasupplierarticlenumber",
                "article",
                "articlenumber",
                "number",
            ],
        )
        product_col = find_column_name(columns, ["productId", "productid", "ProductId", "prdId", "prdid", "id"])

        if table == "prd":
            self.stdout.write(f"- remote prd columns={len(columns)} (queried by related product ids only)")
            product_ids = self._collect_remote_product_ids(
                storage=storage,
                supplier_id=supplier_id,
                article_number=article_number,
            )
            self.stdout.write(f"  - collected_product_ids={len(product_ids)}")
            if not product_ids:
                return
            id_col = find_column_name(columns, ["id", "productId", "productid", "ProductId", "prdid", "prdId"])
            if not id_col:
                self.stdout.write("  - remote prd id column not found")
                return
            rows = storage.fetch_remote_rows_in(
                table="prd",
                column=id_col,
                values=sorted(product_ids),
                limit=max(200, len(product_ids) * 2),
                columns=columns,
            )
            self.stdout.write(f"  - remote prd count={len(rows)} id_col={id_col}")
            for row in rows[:sample_limit]:
                self.stdout.write(
                    f"    - id={row.get(id_col)} description={row.get('description') or row.get('Description') or '-'}"
                )
            return

        if not supplier_col or not article_col:
            self.stdout.write(f"- remote {table}: relation_columns_missing supplier={supplier_col or '-'} article={article_col or '-'}")
            return

        rows = storage.fetch_remote_rows_exact(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=20000,
            columns=columns,
        )
        self.stdout.write(
            f"- remote {table} count={len(rows)} supplier_col={supplier_col} article_col={article_col} "
            f"product_col={product_col or '-'}"
        )
        for row in rows[:sample_limit]:
            self.stdout.write(
                f"  - supplier={row.get(supplier_col)} article={row.get(article_col)} "
                f"product={row.get(product_col) if product_col else '-'}"
            )

    def _collect_remote_product_ids(
        self,
        *,
        storage: AutoDbRawCloneStorage,
        supplier_id: int,
        article_number: str,
    ) -> set[int]:
        out: set[int] = set()
        for table in ("article_prd", "article_links"):
            columns = storage.get_remote_columns(table)
            supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id"])
            article_col = find_column_name(
                columns,
                [
                    "DataSupplierArticleNumber",
                    "datasupplierarticlenumber",
                    "PartsDataSupplierArticleNumber",
                    "partsdatasupplierarticlenumber",
                    "article",
                    "articlenumber",
                    "number",
                ],
            )
            product_col = find_column_name(columns, ["productId", "productid", "ProductId", "prdId", "prdid", "id"])
            if not supplier_col or not article_col or not product_col:
                continue
            rows = storage.fetch_remote_rows_exact(
                table=table,
                filters={supplier_col: supplier_id, article_col: article_number},
                limit=20000,
                columns=[product_col],
            )
            for row in rows:
                value = self._safe_int(row.get(product_col))
                if value is not None:
                    out.add(value)
        return out

    def _safe_int(self, value: Any) -> int | None:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None
