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
    Read-only lookup for FAST matching with exact-only cascade strategy:
    A) supplier/brand + normalized article exact
    B) normalized article exact (article-only)
    C) original article exact (article-only)
    D) aggressive normalized article exact (article-only)
    F) OE/cross exact (supplier-gated first, article-only fallback)

    Broad LIKE/contains is intentionally excluded from live remote lookups.
    """

    PRIMARY_TABLE_ORDER: tuple[str, ...] = ("article_numbers", "articles")
    OE_CROSS_TABLE_ORDER: tuple[str, ...] = ("article_oe", "article_cross", "article_m", "article_nn")
    SUPPLIER_COLUMN_CANDIDATES: tuple[str, ...] = ("supplierId", "supplierid", "SupplierId", "supplier_id", "supplier")
    MAIN_ARTICLE_COLUMN_CANDIDATES: tuple[str, ...] = (
        "DataSupplierArticleNumber",
        "datasupplierarticlenumber",
        "articleNumber",
        "articlenumber",
        "article",
        "number",
    )
    OE_ARTICLE_COLUMN_CANDIDATES: tuple[str, ...] = (
        "oe_number",
        "oenumber",
        "oe",
        "trade_number",
        "tradenumber",
        "part_number",
        "partnumber",
        "manufacturer_article",
        "manufacturerArticle",
        "number",
        "article",
        "DataSupplierArticleNumber",
        "datasupplierarticlenumber",
    )

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
        canonical_article = self.normalizer.normalize(raw_article).normalized or normalize_article(raw_article)
        original_article = raw_article
        aggressive_article = self._aggressive_article_value(canonical_article or raw_article)
        endpoint = self._endpoint_summary()
        path_steps: list[str] = []

        match = self.brand_matcher.resolve_many([brand_norm]).get(brand_norm)
        supplier_id = int(match.matched_supplier_id) if (match and match.matched_supplier_id is not None) else None
        supplier_name = ""
        supplier_reason = "brand_not_found"
        if match is not None:
            supplier_reason = str(match.reason or "")
            if match.candidates:
                supplier_name = str(match.candidates[0].supplier_description or "").strip()

        if not canonical_article:
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

        cascade: list[tuple[str, bool, str, tuple[str, ...], bool]] = [
            ("A_supplier_norm", True, canonical_article, self.PRIMARY_TABLE_ORDER, False),
            ("B_norm_article_only", False, canonical_article, self.PRIMARY_TABLE_ORDER, False),
            ("C_original_article_only", False, original_article, self.PRIMARY_TABLE_ORDER, False),
            ("D_aggressive_article_only", False, aggressive_article, self.PRIMARY_TABLE_ORDER, False),
            ("F_oe_cross_supplier_exact", True, canonical_article, self.OE_CROSS_TABLE_ORDER, True),
            ("F_oe_cross_article_only", False, canonical_article, self.OE_CROSS_TABLE_ORDER, True),
        ]

        supplier_id_from_hit: int | None = None
        for step_key, require_supplier, step_article, table_order, oe_mode in cascade:
            article_value = str(step_article or "").strip()
            if not article_value:
                path_steps.append(f"{step_key}:skip_empty_article")
                continue
            if require_supplier and supplier_id is None:
                path_steps.append(f"{step_key}:skip_missing_supplier_id")
                continue
            try:
                step_match = self._lookup_step_exact(
                    step_key=step_key,
                    table_order=table_order,
                    article_value=article_value,
                    supplier_id=(supplier_id if require_supplier else None),
                    oe_mode=oe_mode,
                )
            except Exception as exc:  # noqa: BLE001
                lookup_error = str(exc)
                path_steps.append(f"{step_key}:error:{exc.__class__.__name__}")
                continue

            local_hits += step_match["local_hits"]
            remote_hits += step_match["remote_hits"]
            remote_queries += step_match["remote_queries"]
            path_steps.append(step_match["trace"])
            if step_match["found"]:
                matched_table = str(step_match["matched_table"] or "")
                matched_source = str(step_match["matched_source"] or "")
                remote_stored_article = str(step_match["remote_stored_article"] or "")
                supplier_id_from_hit = step_match["supplier_id_from_row"]
                break

        if supplier_id is None and supplier_id_from_hit is not None:
            supplier_id = supplier_id_from_hit

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

        path = " -> ".join(path_steps) if path_steps else "no_steps"

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

    def _aggressive_article_value(self, value: str) -> str:
        normalized = self.normalizer.normalize(value).normalized
        compact = str(normalized or "").replace("-", "").replace("/", "").replace(".", "").replace(" ", "").upper()
        if not compact:
            return ""
        trimmed = compact.lstrip("0")
        return trimmed or compact

    def _endpoint_summary(self) -> str:
        cfg = self.storage.remote_client.sanitized_config()
        return f"mysql://{cfg.get('host')}:{cfg.get('port')}/{cfg.get('database')}"

    def _resolve_remote_columns(self, *, table: str, oe_mode: bool = False) -> tuple[str | None, str | None]:
        columns = self._safe_remote_columns(table)
        supplier_col = find_column_name(columns, list(self.SUPPLIER_COLUMN_CANDIDATES))
        article_col = find_column_name(
            columns,
            list(self.OE_ARTICLE_COLUMN_CANDIDATES if oe_mode else self.MAIN_ARTICLE_COLUMN_CANDIDATES),
        )
        return supplier_col, article_col

    def _lookup_step_exact(
        self,
        *,
        step_key: str,
        table_order: tuple[str, ...],
        article_value: str,
        supplier_id: int | None,
        oe_mode: bool,
    ) -> dict[str, Any]:
        local_hits = 0
        remote_hits = 0
        remote_queries = 0
        article_col_candidates = self.OE_ARTICLE_COLUMN_CANDIDATES if oe_mode else self.MAIN_ARTICLE_COLUMN_CANDIDATES

        for table in table_order:
            local_columns = sorted(self.storage.get_local_columns(table))
            supplier_col_local = find_column_name(local_columns, list(self.SUPPLIER_COLUMN_CANDIDATES))
            article_col_local = find_column_name(local_columns, list(article_col_candidates))
            if article_col_local:
                local_filters = {article_col_local: article_value}
                if supplier_id is not None and supplier_col_local:
                    local_filters[supplier_col_local] = supplier_id
                local_rows = self.storage.fetch_local_rows(
                    table=table,
                    filters=local_filters,
                    limit=3,
                    columns=[item for item in [supplier_col_local, article_col_local] if item],
                )
                if local_rows:
                    local_hits += len(local_rows)
                    supplier_from_row = self._int_or_none(local_rows[0].get(supplier_col_local)) if supplier_col_local else None
                    return {
                        "found": True,
                        "matched_table": table,
                        "matched_source": f"{step_key}:local:{table}.{article_col_local}",
                        "remote_stored_article": str(local_rows[0].get(article_col_local) or "").strip(),
                        "supplier_id_from_row": supplier_from_row,
                        "local_hits": local_hits,
                        "remote_hits": remote_hits,
                        "remote_queries": remote_queries,
                        "trace": f"{step_key}:local_hit:{table}.{article_col_local}",
                    }

            remote_columns = self._safe_remote_columns(table)
            if not remote_columns:
                continue
            supplier_col_remote = find_column_name(remote_columns, list(self.SUPPLIER_COLUMN_CANDIDATES))
            article_col_remote = find_column_name(remote_columns, list(article_col_candidates))
            if not article_col_remote:
                continue
            remote_filters = {article_col_remote: article_value}
            if supplier_id is not None and supplier_col_remote:
                remote_filters[supplier_col_remote] = supplier_id
            if supplier_id is not None and supplier_col_remote is None:
                continue
            remote_queries += 1
            rows = self._safe_remote_lookup_exact(
                table=table,
                filters=remote_filters,
                limit=3,
                columns=[item for item in [supplier_col_remote, article_col_remote] if item],
            )
            if rows is None:
                continue
            if rows:
                remote_hits += len(rows)
                supplier_from_row = self._int_or_none(rows[0].get(supplier_col_remote)) if supplier_col_remote else None
                return {
                    "found": True,
                    "matched_table": table,
                    "matched_source": f"{step_key}:remote:{table}.{article_col_remote}",
                    "remote_stored_article": str(rows[0].get(article_col_remote) or "").strip(),
                    "supplier_id_from_row": supplier_from_row,
                    "local_hits": local_hits,
                    "remote_hits": remote_hits,
                    "remote_queries": remote_queries,
                    "trace": f"{step_key}:remote_hit:{table}.{article_col_remote}",
                }

        return {
            "found": False,
            "matched_table": "",
            "matched_source": "",
            "remote_stored_article": "",
            "supplier_id_from_row": None,
            "local_hits": local_hits,
            "remote_hits": remote_hits,
            "remote_queries": remote_queries,
            "trace": f"{step_key}:miss",
        }

    def _safe_remote_columns(self, table: str) -> list[str]:
        try:
            return self.storage.get_remote_columns(table)
        except Exception:  # noqa: BLE001
            return []

    def _safe_remote_lookup_exact(
        self,
        *,
        table: str,
        filters: dict[str, Any],
        limit: int,
        columns: list[str],
    ) -> list[dict[str, Any]] | None:
        try:
            return self.storage.fetch_remote_rows_exact(table=table, filters=filters, limit=limit, columns=columns)
        except Exception:  # noqa: BLE001
            return None

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

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
        supplier_col, article_col = self._resolve_remote_columns(table=table, oe_mode=False)
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
