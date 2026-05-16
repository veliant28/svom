from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.supplier_imports.parsers.utils import normalize_article


@dataclass(frozen=True)
class ArticleEnrichmentResult:
    article_id: int | None
    supplier_id: int | None
    article_number: str
    populated_tables: dict[str, int] = field(default_factory=dict)
    skipped_tables: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    remote_queries: int = 0
    remote_hits: int = 0


class AutoDbArticleEnrichmentService:
    RELATED_TABLES: tuple[str, ...] = (
        "articles",
        "article_numbers",
        "article_attributes",
        "article_images",
        "article_inf",
        "article_li",
        "article_links",
        "article_prd",
        "article_oe",
        "article_cross",
        "article_ean",
        "article_nn",
        "article_m",
        "article_acc",
        "article_parts",
    )

    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()

    def enrich_article(
        self,
        *,
        article_id: int | None = None,
        supplier_id: int | None = None,
        article_number: str = "",
        tables: list[str] | None = None,
        dry_run: bool = False,
        replace_local: bool = False,
    ) -> ArticleEnrichmentResult:
        target_tables = tuple(tables or self.RELATED_TABLES)
        populated: dict[str, int] = {}
        skipped: list[str] = []
        warnings: list[str] = []
        remote_queries = 0
        remote_hits = 0

        for table in target_tables:
            if table == "prd":
                continue
            filters = self._build_filters(
                table=table,
                article_id=article_id,
                supplier_id=supplier_id,
                article_number=article_number,
            )
            if not filters:
                skipped.append(table)
                warnings.append(f"{table}: relation columns are not resolved")
                continue

            rows: list[dict[str, Any]] = []
            matched_filter: dict[str, Any] = {}
            filter_variants = self._filters_with_article_variants(
                table=table,
                filters=filters,
                article_number=article_number,
            )
            for filter_variant in filter_variants:
                remote_queries += 1
                rows = self.storage.fetch_remote_rows_exact(table=table, filters=filter_variant, limit=20000)
                if rows:
                    matched_filter = dict(filter_variant)
                    break
            if not rows:
                populated[table] = 0
                continue
            remote_hits += len(rows)

            if dry_run:
                populated[table] = len(rows)
            else:
                if replace_local:
                    supplier_key = ""
                    article_key = ""
                    for key in matched_filter.keys():
                        key_lower = str(key).lower()
                        if key_lower in {"supplierid", "supplier_id", "supplier"}:
                            supplier_key = str(key)
                        if key_lower in {
                            "datasupplierarticlenumber",
                            "partsdatasupplierarticlenumber",
                            "articlenumber",
                            "article",
                            "number",
                        }:
                            article_key = str(key)
                    if supplier_key and article_key:
                        self.storage.delete_local_rows(
                            table=table,
                            filters={
                                supplier_key: matched_filter.get(supplier_key),
                                article_key: self._article_variants(article_number),
                            },
                        )
                failed = self.storage.upsert_rows(table=table, rows=rows)
                populated[table] = max(len(rows) - failed, 0)

        if "prd" in target_tables:
            prd_populated, prd_queries, prd_hits = self._enrich_prd_from_relations(
                supplier_id=supplier_id,
                article_number=article_number,
                dry_run=dry_run,
            )
            populated["prd"] = prd_populated
            remote_queries += prd_queries
            remote_hits += prd_hits

        return ArticleEnrichmentResult(
            article_id=article_id,
            supplier_id=supplier_id,
            article_number=article_number,
            populated_tables=populated,
            skipped_tables=skipped,
            warnings=warnings,
            remote_queries=remote_queries,
            remote_hits=remote_hits,
        )

    def _enrich_prd_from_relations(
        self,
        *,
        supplier_id: int | None,
        article_number: str,
        dry_run: bool,
    ) -> tuple[int, int, int]:
        if supplier_id is None or not article_number:
            return 0, 0, 0

        product_ids = self._collect_product_ids_from_local_relation(
            table="article_prd",
            supplier_id=supplier_id,
            article_number=article_number,
            product_candidates=["productId", "productid", "ProductId", "id"],
        )
        product_ids |= self._collect_product_ids_from_local_relation(
            table="article_links",
            supplier_id=supplier_id,
            article_number=article_number,
            product_candidates=["productId", "productid", "ProductId"],
        )
        if not product_ids:
            return 0, 0, 0

        remote_columns = self.storage.get_remote_columns("prd")
        id_column = find_column_name(remote_columns, ["id", "productId", "productid", "ProductId"])
        if not id_column:
            return 0, 0, 0
        rows = self.storage.fetch_remote_rows_in(
            table="prd",
            column=id_column,
            values=sorted(product_ids),
            limit=max(len(product_ids) * 4, 200),
            columns=remote_columns,
        )
        if not rows:
            return 0, 1, 0
        if dry_run:
            return len(rows), 1, len(rows)
        failed = self.storage.upsert_rows(table="prd", rows=rows)
        return max(len(rows) - failed, 0), 1, len(rows)

    def _collect_product_ids_from_local_relation(
        self,
        *,
        table: str,
        supplier_id: int,
        article_number: str,
        product_candidates: list[str],
    ) -> set[int]:
        self.storage.ensure_table(table)
        columns = list(self.storage.get_local_columns(table))
        if not columns:
            return set()
        supplier_column = find_column_name(columns, ["supplierId", "supplierid", "supplier_id", "SupplierId"])
        article_column = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "PartsDataSupplierArticleNumber", "articlenumber", "article", "number"],
        )
        product_column = find_column_name(columns, product_candidates)
        if not supplier_column or not article_column or not product_column:
            return set()

        variants = self._article_variants(article_number)
        rows = self.storage.fetch_local_rows_in(
            table=table,
            column=article_column,
            values=variants,
            extra_filters={supplier_column: supplier_id},
            limit=1000,
            columns=columns,
        )
        out: set[int] = set()
        for row in rows:
            value = row.get(product_column)
            try:
                out.add(int(value))
            except (TypeError, ValueError):
                continue
        return out

    def _article_variants(self, article_number: str) -> list[str]:
        raw = str(article_number or "").strip()
        if not raw:
            return []
        values = [raw, raw.replace(" ", ""), normalize_article(raw)]
        out: list[str] = []
        seen: set[str] = set()
        for item in values:
            candidate = str(item or "").strip()
            if not candidate:
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(candidate)
        return out

    def _filters_with_article_variants(
        self,
        *,
        table: str,
        filters: dict[str, Any],
        article_number: str,
    ) -> list[dict[str, Any]]:
        if not filters or not article_number:
            return [filters]
        columns = self.storage.get_remote_columns(table)
        article_column = find_column_name(
            columns,
            [
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "PartsDataSupplierArticleNumber",
                "articleNumber",
                "articlenumber",
                "article",
                "number",
            ],
        )
        if not article_column or article_column not in filters:
            return [filters]

        variants = self._article_variants(article_number)
        if not variants:
            return [filters]

        out: list[dict[str, Any]] = []
        for variant in variants:
            out.append({**filters, article_column: variant})
        return out

    def _build_filters(
        self,
        *,
        table: str,
        article_id: int | None,
        supplier_id: int | None,
        article_number: str,
    ) -> dict[str, Any]:
        columns = self.storage.get_remote_columns(table)
        if table == "article_m":
            return {}

        def first_of(*names: str) -> str | None:
            return find_column_name(columns, list(names))

        filters: dict[str, Any] = {}

        if table == "article_cross":
            supplier_column = first_of("SupplierId", "supplierid", "supplier_id", "supplierId")
            if supplier_id is not None and supplier_column is not None:
                filters[supplier_column] = int(supplier_id)
            number_column = first_of(
                "PartsDataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "DataSupplierArticleNumber",
            )
            if article_number and number_column is not None:
                filters[number_column] = str(article_number)
            if filters:
                return filters
        else:
            supplier_column = first_of("supplierId", "supplierid", "supplier_id", "supplier")
            number_column = first_of(
                "DataSupplierArticleNumber",
                "datasupplierarticlenumber",
                "articlenumber",
                "article",
                "number",
            )
            if supplier_id is not None and supplier_column is not None:
                filters[supplier_column] = int(supplier_id)
            if article_number and number_column is not None:
                filters[number_column] = str(article_number)
            if filters:
                return filters

        # Compatibility fallback for datasets where only a numeric article key exists.
        article_column = first_of("articleid", "id")
        if article_id is not None and article_column is not None:
            filters[article_column] = int(article_id)

        return filters
