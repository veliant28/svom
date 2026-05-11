from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.supplier_brand_matcher import SupplierBrandMatcher
from apps.supplier_imports.parsers.utils import normalize_article, normalize_brand


@dataclass(frozen=True)
class AutoDbLookupV3ReadOnlyResult:
    found: bool
    supplier_id: int | None
    supplier_name: str
    supplier_reason: str
    raw_article: str
    canonical_article: str
    remote_stored_article: str
    matched_table: str
    matched_source: str
    local_hits: int
    remote_hits: int
    article_prd_rows: int
    article_links_rows: int
    prd_rows: int
    linkage_present: bool
    remote_queries: int
    error: str
    path: str
    endpoint: str


class AutoDbLookupV3ReadOnlyService:
    """
    Read-only lookup that follows the same lookup primitives as the working GPL/UTR path:
    - SupplierBrandMatcher for supplier resolution
    - article_numbers -> articles lookup order
    - shared ArticleNumberNormalizer variants
    - optional remote exact checks via AutoDbRawCloneStorage fetch_remote_rows_exact
    """

    TABLE_ORDER: tuple[str, ...] = ("article_numbers", "articles")

    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        brand_matcher: SupplierBrandMatcher | None = None,
        normalizer: ArticleNumberNormalizer | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.brand_matcher = brand_matcher or SupplierBrandMatcher(storage=self.storage)
        self.normalizer = normalizer or ArticleNumberNormalizer()

    def lookup(
        self,
        *,
        brand: str,
        article: str,
    ) -> AutoDbLookupV3ReadOnlyResult:
        brand_norm = normalize_brand(brand)
        raw_article = str(article or "").strip()
        canonical_article = self._canonical_article(raw_article)
        variants = self._article_variants(raw_article=raw_article, canonical_article=canonical_article)

        endpoint = self._endpoint_summary()
        path = (
            "SupplierBrandMatcher.resolve_many -> "
            "AutoDbRawCloneStorage.fetch_local_rows/fetch_remote_rows_exact "
            "(article_numbers->articles, exact variants only)"
        )

        match = self.brand_matcher.resolve_many([brand_norm]).get(brand_norm)
        supplier_id = int(match.matched_supplier_id) if (match and match.matched_supplier_id is not None) else None
        supplier_name = ""
        supplier_reason = "brand_not_found"
        if match is not None:
            supplier_reason = str(match.reason or "")
            if match.candidates:
                supplier_name = str(match.candidates[0].supplier_description or "").strip()

        if supplier_id is None or not canonical_article:
            return AutoDbLookupV3ReadOnlyResult(
                found=False,
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                supplier_reason=supplier_reason,
                raw_article=raw_article,
                canonical_article=canonical_article,
                remote_stored_article="",
                matched_table="",
                matched_source="",
                local_hits=0,
                remote_hits=0,
                article_prd_rows=0,
                article_links_rows=0,
                prd_rows=0,
                linkage_present=False,
                remote_queries=0,
                error="",
                path=path,
                endpoint=endpoint,
            )

        local_hits = 0
        remote_hits = 0
        remote_queries = 0
        matched_table = ""
        matched_source = ""
        remote_stored_article = ""
        lookup_error = ""

        for table in self.TABLE_ORDER:
            supplier_col, article_col = self._resolve_local_columns(table=table)
            if supplier_col and article_col:
                l_hits, l_article = self._local_hits_for_variants(
                    table=table,
                    supplier_col=supplier_col,
                    article_col=article_col,
                    supplier_id=supplier_id,
                    variants=variants,
                )
                local_hits += l_hits
                if l_hits > 0 and not matched_table:
                    matched_table = table
                    matched_source = "local"
                    remote_stored_article = l_article
                    break

            try:
                supplier_col_r, article_col_r = self._resolve_remote_columns(table=table)
                if supplier_col_r and article_col_r:
                    for variant in variants[:8]:
                        remote_queries += 1
                        rows = self.storage.fetch_remote_rows_exact(
                            table=table,
                            filters={supplier_col_r: supplier_id, article_col_r: variant},
                            limit=3,
                        )
                        if rows:
                            remote_hits += len(rows)
                            if not matched_table:
                                matched_table = table
                                matched_source = "remote"
                                remote_stored_article = str(rows[0].get(article_col_r) or "").strip()
                                break
                    if matched_table:
                        break
            except Exception as exc:  # noqa: BLE001
                lookup_error = str(exc)
                # continue to next table; this stays read-only and diagnostics-oriented

        found = bool(matched_table)
        linkage_prd_rows = 0
        linkage_article_prd_rows = 0
        linkage_article_links_rows = 0
        linkage_present = False

        if found:
            linkage_article = remote_stored_article or canonical_article
            linkage_article_prd_rows, linkage_article_links_rows, linkage_prd_rows = self._read_linkage_presence(
                supplier_id=supplier_id,
                article_number=linkage_article,
            )
            linkage_present = (linkage_article_prd_rows + linkage_article_links_rows) > 0 and linkage_prd_rows > 0

        return AutoDbLookupV3ReadOnlyResult(
            found=found,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            supplier_reason=supplier_reason,
            raw_article=raw_article,
            canonical_article=canonical_article,
            remote_stored_article=remote_stored_article,
            matched_table=matched_table,
            matched_source=matched_source,
            local_hits=local_hits,
            remote_hits=remote_hits,
            article_prd_rows=linkage_article_prd_rows,
            article_links_rows=linkage_article_links_rows,
            prd_rows=linkage_prd_rows,
            linkage_present=linkage_present,
            remote_queries=remote_queries,
            error=lookup_error,
            path=path,
            endpoint=endpoint,
        )

    def _canonical_article(self, raw_article: str) -> str:
        normalized = self.normalizer.normalize(raw_article).normalized
        return normalized or normalize_article(raw_article)

    def _article_variants(self, *, raw_article: str, canonical_article: str) -> list[str]:
        variants = list(self.normalizer.normalize(raw_article).search_variants or ())
        for candidate in (raw_article, canonical_article):
            value = str(candidate or "").strip()
            if value and value not in variants:
                variants.append(value)
        return variants

    def _endpoint_summary(self) -> str:
        cfg = self.storage.remote_client.sanitized_config()
        return f"mysql://{cfg.get('host')}:{cfg.get('port')}/{cfg.get('database')}"

    def _resolve_local_columns(self, *, table: str) -> tuple[str | None, str | None]:
        columns = sorted(self.storage.get_local_columns(table))
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"])
        article_col = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
        )
        return supplier_col, article_col

    def _resolve_remote_columns(self, *, table: str) -> tuple[str | None, str | None]:
        columns = self.storage.get_remote_columns(table)
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"])
        article_col = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
        )
        return supplier_col, article_col

    def _local_hits_for_variants(
        self,
        *,
        table: str,
        supplier_col: str,
        article_col: str,
        supplier_id: int,
        variants: list[str],
    ) -> tuple[int, str]:
        hits = 0
        matched_article = ""
        for variant in variants[:8]:
            rows = self.storage.fetch_local_rows(
                table=table,
                filters={supplier_col: supplier_id, article_col: variant},
                limit=3,
                columns=[article_col],
            )
            if rows:
                hits += len(rows)
                if not matched_article:
                    matched_article = str(rows[0].get(article_col) or "").strip()
        return hits, matched_article

    def _read_linkage_presence(self, *, supplier_id: int, article_number: str) -> tuple[int, int, int]:
        article_prd_rows = self._count_remote_rows(
            table="article_prd",
            supplier_id=supplier_id,
            article_number=article_number,
            limit=10000,
        )
        article_links_rows = self._count_remote_rows(
            table="article_links",
            supplier_id=supplier_id,
            article_number=article_number,
            limit=10000,
        )

        product_ids = self._collect_remote_product_ids(
            table="article_prd",
            supplier_id=supplier_id,
            article_number=article_number,
        )
        product_ids |= self._collect_remote_product_ids(
            table="article_links",
            supplier_id=supplier_id,
            article_number=article_number,
        )
        if not product_ids:
            return article_prd_rows, article_links_rows, 0

        prd_columns = self.storage.get_remote_columns("prd")
        prd_id_col = find_column_name(prd_columns, ["id", "productId", "productid", "ProductId", "prdid", "prdId"])
        if not prd_id_col:
            return article_prd_rows, article_links_rows, 0
        prd_rows = self.storage.fetch_remote_rows_in(
            table="prd",
            column=prd_id_col,
            values=sorted(product_ids),
            limit=max(len(product_ids) * 2, 200),
            columns=[prd_id_col],
        )
        return article_prd_rows, article_links_rows, len(prd_rows)

    def _count_remote_rows(
        self,
        *,
        table: str,
        supplier_id: int,
        article_number: str,
        limit: int,
    ) -> int:
        supplier_col, article_col = self._resolve_remote_columns(table=table)
        if not supplier_col or not article_col:
            return 0
        rows = self.storage.fetch_remote_rows_exact(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=limit,
        )
        return len(rows)

    def _collect_remote_product_ids(self, *, table: str, supplier_id: int, article_number: str) -> set[int]:
        columns = self.storage.get_remote_columns(table)
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"])
        article_col = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
        )
        product_col = find_column_name(columns, ["productId", "productid", "ProductId", "prdid", "prdId", "id"])
        if not supplier_col or not article_col or not product_col:
            return set()

        rows = self.storage.fetch_remote_rows_exact(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            limit=5000,
            columns=[product_col],
        )
        out: set[int] = set()
        for row in rows:
            value = row.get(product_col)
            try:
                out.add(int(value))
            except (TypeError, ValueError):
                continue
        return out
