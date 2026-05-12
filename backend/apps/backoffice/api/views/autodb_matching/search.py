from __future__ import annotations

from typing import Any

from apps.autodb.services.article_number_normalizer import ArticleNumberNormalizer
from apps.autodb.services.column_helpers import find_column_name
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage

from .utils import safe_str

ARTICLE_TABLES = ("article_numbers", "articles")


class ManualAutoDbSearch:
    def __init__(
        self,
        *,
        storage: AutoDbRawCloneStorage | None = None,
        normalizer: ArticleNumberNormalizer | None = None,
    ):
        self.storage = storage or AutoDbRawCloneStorage()
        self.normalizer = normalizer or ArticleNumberNormalizer()

    def variants(self, article: str) -> list[str]:
        normalized = self.normalizer.normalize(article)
        values = [normalized.original, normalized.original.upper(), normalized.canonical, normalized.normalized]
        values.extend(normalized.search_variants)
        out: list[str] = []
        for item in values:
            value = safe_str(item).upper()
            if value and value not in out:
                out.append(value)
        return out

    def local(self, *, supplier_id: int, supplier_name: str, article: str) -> dict[str, Any]:
        raw_article = safe_str(article)
        normalized = self.normalizer.normalize(raw_article)
        variants = self.variants(raw_article)
        matched_table = ""
        matched_article = ""
        matched_row: dict[str, Any] = {}
        local_hits = 0

        for table in ARTICLE_TABLES:
            columns = self.storage.get_local_columns(table)
            supplier_col, article_col = self._supplier_article_columns(columns)
            if not supplier_col or not article_col:
                continue
            for variant in variants[:8]:
                rows = self.storage.fetch_local_rows(
                    table=table,
                    filters={supplier_col: supplier_id, article_col: variant},
                    columns=self._selected_columns(columns),
                    limit=5,
                )
                if not rows:
                    continue
                local_hits += len(rows)
                if not matched_table:
                    matched_table = table
                    matched_row = rows[0]
                    matched_article = safe_str(rows[0].get(article_col) or variant)
                break
            if matched_table:
                break

        article_for_linkage = matched_article or normalized.normalized or normalized.canonical
        article_prd_rows, article_links_rows, prd_rows, prd_ids = self._linkage_counts(
            supplier_id=supplier_id,
            article_number=article_for_linkage,
        )
        attributes_rows = self._count_rows(table="article_attributes", supplier_id=supplier_id, article_number=article_for_linkage)
        fitment_rows = self._count_rows(table="article_li", supplier_id=supplier_id, article_number=article_for_linkage)
        image_rows = self._count_rows(table="article_images", supplier_id=supplier_id, article_number=article_for_linkage)
        linkage_present = (article_prd_rows + article_links_rows) > 0 and prd_rows > 0
        status_value = "not_found"
        if matched_table and linkage_present:
            status_value = "exact_local_found"
        elif matched_table:
            status_value = "no_prd_linkage"

        return {
            "source": "local",
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_description": supplier_name,
            "supplier_matchcode": "",
            "article_input": raw_article,
            "variants": variants,
            "searched_article": raw_article,
            "matched_stored_article": matched_article,
            "article_id": self._article_id(matched_row),
            "article_key": f"{supplier_id}:{matched_article}" if matched_article else "",
            "prd_linkage_present": linkage_present,
            "prd_id": prd_ids[0] if prd_ids else None,
            "generic": "",
            "category_metadata_present": prd_rows > 0,
            "attributes_available_count": attributes_rows,
            "fitments_available_count": fitment_rows,
            "images_available_count": image_rows,
            "image_thumbnails": [],
            "status": status_value,
            "matched_table": matched_table,
            "source_path": "auto_db_pro local clone: article_numbers/articles exact variants",
            "confidence": "deterministic_exact",
            "reason": "local deterministic exact variants only; fuzzy/OE/cross/name disabled",
            "counts": {
                "local_hits": local_hits,
                "article_prd_rows": article_prd_rows,
                "article_links_rows": article_links_rows,
                "prd_rows": prd_rows,
            },
            "details": {
                "article": matched_row,
                "prd_ids": prd_ids[:20],
                "attributes_preview": [],
                "compatibility_preview": [],
            },
        }

    def _supplier_article_columns(self, columns: set[str] | list[str]) -> tuple[str | None, str | None]:
        supplier_col = find_column_name(columns, ["supplierId", "supplierid", "SupplierId", "supplier_id", "supplier"])
        article_col = find_column_name(
            columns,
            ["DataSupplierArticleNumber", "datasupplierarticlenumber", "articleNumber", "articlenumber", "article", "number"],
        )
        return supplier_col, article_col

    def _selected_columns(self, columns: set[str]) -> list[str]:
        lower = {col.lower() for col in columns}
        preferred = [
            "id",
            "articleId",
            "articleid",
            "ArticleId",
            "supplierId",
            "supplierid",
            "DataSupplierArticleNumber",
            "datasupplierarticlenumber",
            "articleNumber",
            "articlenumber",
            "description",
            "genericArticleId",
            "genericarticleid",
        ]
        selected = [item for item in preferred if item in columns or item.lower() in lower]
        return selected or list(sorted(columns))[:12]

    def _article_id(self, row: dict[str, Any]) -> str:
        for key in ("id", "articleId", "articleid", "ArticleId"):
            if row.get(key) not in (None, ""):
                return safe_str(row.get(key))
        return ""

    def _linkage_counts(self, *, supplier_id: int, article_number: str) -> tuple[int, int, int, list[int]]:
        product_ids: list[int] = []
        article_prd_rows = self._linkage_table_rows(
            table="article_prd",
            supplier_id=supplier_id,
            article_number=article_number,
            product_ids=product_ids,
        )
        article_links_rows = self._linkage_table_rows(
            table="article_links",
            supplier_id=supplier_id,
            article_number=article_number,
            product_ids=product_ids,
        )
        unique_ids = sorted({item for item in product_ids if item > 0})
        if not unique_ids:
            return article_prd_rows, article_links_rows, 0, []

        prd_columns = self.storage.get_local_columns("prd")
        prd_id_col = find_column_name(prd_columns, ["id", "productId", "productid", "ProductId", "prdId", "prdid"])
        if not prd_id_col:
            return article_prd_rows, article_links_rows, 0, unique_ids
        prd_rows = self.storage.fetch_local_rows_in(
            table="prd",
            column=prd_id_col,
            values=unique_ids,
            columns=[prd_id_col],
            limit=max(len(unique_ids) * 2, 100),
        )
        return article_prd_rows, article_links_rows, len(prd_rows), unique_ids

    def _linkage_table_rows(self, *, table: str, supplier_id: int, article_number: str, product_ids: list[int]) -> int:
        columns = self.storage.get_local_columns(table)
        supplier_col, article_col = self._supplier_article_columns(columns)
        product_col = find_column_name(columns, ["productId", "productid", "ProductId", "prdId", "prdid", "id"])
        if not supplier_col or not article_col or not product_col:
            return 0
        rows = self.storage.fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            columns=[product_col],
            limit=5000,
        )
        for row in rows:
            try:
                product_ids.append(int(row.get(product_col)))
            except (TypeError, ValueError):
                continue
        return len(rows)

    def _count_rows(self, *, table: str, supplier_id: int, article_number: str) -> int:
        columns = self.storage.get_local_columns(table)
        supplier_col, article_col = self._supplier_article_columns(columns)
        if not supplier_col or not article_col:
            return 0
        rows = self.storage.fetch_local_rows(
            table=table,
            filters={supplier_col: supplier_id, article_col: article_number},
            columns=[article_col],
            limit=5000,
        )
        return len(rows)


def remote_result_payload(result, *, article: str, variants: list[str]) -> dict[str, Any]:
    matched_article = safe_str(getattr(result, "remote_stored_article", ""))
    status_value = "exact_remote_found" if bool(getattr(result, "found", False)) else "not_found"
    if bool(getattr(result, "found", False)) and not bool(getattr(result, "linkage_present", False)):
        status_value = "no_prd_linkage"
    return {
        "source": safe_str(getattr(result, "matched_source", "")) or "remote",
        "supplier_id": getattr(result, "supplier_id", None),
        "supplier_name": safe_str(getattr(result, "supplier_name", "")),
        "supplier_description": safe_str(getattr(result, "supplier_name", "")),
        "supplier_matchcode": "",
        "article_input": article,
        "variants": variants,
        "searched_article": article,
        "matched_stored_article": matched_article,
        "article_id": "",
        "article_key": f"{getattr(result, 'supplier_id', '')}:{matched_article}" if matched_article else "",
        "prd_linkage_present": bool(getattr(result, "linkage_present", False)),
        "prd_id": None,
        "generic": "",
        "category_metadata_present": int(getattr(result, "prd_rows", 0) or 0) > 0,
        "attributes_available_count": 0,
        "fitments_available_count": 0,
        "images_available_count": 0,
        "image_thumbnails": [],
        "status": status_value,
        "matched_table": safe_str(getattr(result, "matched_table", "")),
        "source_path": safe_str(getattr(result, "path", "")),
        "endpoint": safe_str(getattr(result, "endpoint", "")),
        "confidence": "deterministic_exact",
        "reason": "remote deterministic exact variants only; fuzzy/OE/cross/name disabled",
        "counts": {
            "local_hits": int(getattr(result, "local_hits", 0) or 0),
            "remote_hits": int(getattr(result, "remote_hits", 0) or 0),
            "remote_queries": int(getattr(result, "remote_queries", 0) or 0),
            "article_prd_rows": int(getattr(result, "article_prd_rows", 0) or 0),
            "article_links_rows": int(getattr(result, "article_links_rows", 0) or 0),
            "prd_rows": int(getattr(result, "prd_rows", 0) or 0),
        },
        "details": {"article": {}, "prd_ids": [], "attributes_preview": [], "compatibility_preview": []},
    }
