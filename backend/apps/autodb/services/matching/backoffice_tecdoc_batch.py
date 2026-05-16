from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Exists, OuterRef, Q

from apps.autodb.services.matching.constants import NON_TECDOC_BRAND_KEYS
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.supplier_brand_matcher import normalize_brand_lookup_key
from apps.catalog.models import AutoDbProductLinkQuality, Product


def _safe_str(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class TecdocBatchCandidate:
    product_id: str
    supplier_id: int
    supplier_name: str
    article: str


class BackofficeTecdocBatchSelector:
    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()
        self._non_tecdoc = {
            normalize_brand_lookup_key(str(item).strip())
            for item in NON_TECDOC_BRAND_KEYS
            if str(item).strip()
        }

    def select_candidates(self, *, limit: int, product_ids: list[str] | None = None) -> list[TecdocBatchCandidate]:
        target_limit = max(1, min(int(limit or 0), 1000))
        selected: list[TecdocBatchCandidate] = []
        requested_product_ids = [str(item).strip() for item in (product_ids or []) if str(item).strip()]
        if requested_product_ids:
            queryset = (
                Product.objects.filter(id__in=requested_product_ids)
                .order_by("-updated_at", "id")
            )
        else:
            queryset = self._base_queryset()
        for product in queryset.iterator(chunk_size=250):
            if requested_product_ids and self._has_trusted_link_quality(product):
                continue
            supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0)
            article = _safe_str(getattr(product, "autodb_article_number", "")) or _safe_str(getattr(product, "article", ""))
            if supplier_id <= 0 or not article:
                continue
            if self._is_non_tecdoc(product):
                continue
            supplier_name = _safe_str(getattr(product, "autodb_supplier_name", "")) or _safe_str(getattr(product, "display_brand_name", ""))
            selected.append(
                TecdocBatchCandidate(
                    product_id=str(product.id),
                    supplier_id=supplier_id,
                    supplier_name=supplier_name,
                    article=article,
                )
            )
            if len(selected) >= target_limit:
                break
        return selected

    def _base_queryset(self):
        trusted_exists = AutoDbProductLinkQuality.objects.filter(
            product_id=OuterRef("pk"),
            autodb_article_key=OuterRef("autodb_article_key"),
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        )
        queryset = (
            Product.objects.annotate(_trusted=Exists(trusted_exists))
            .filter(_trusted=False)
            .filter(autodb_supplier_id__isnull=False)
            .filter(
                (
                    Q(autodb_article_number__isnull=False)
                    & ~Q(autodb_article_number="")
                )
                | (
                    Q(article__isnull=False)
                    & ~Q(article="")
                )
            )
            .order_by("-updated_at", "id")
        )
        return queryset

    def _has_trusted_link_quality(self, product: Product) -> bool:
        article_key = _safe_str(getattr(product, "autodb_article_key", ""))
        if not article_key:
            return False
        return AutoDbProductLinkQuality.objects.filter(
            product_id=product.id,
            autodb_article_key=article_key,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()

    def _is_non_tecdoc(self, product: Product) -> bool:
        brand = _safe_str(getattr(product, "display_brand_name", "")) or _safe_str(getattr(product, "autodb_supplier_name", ""))
        if not brand:
            return False
        normalized = normalize_brand_lookup_key(brand)
        return normalized in self._non_tecdoc

    def _is_clone_linked(self, *, supplier_id: int, article: str) -> bool:
        key = (int(supplier_id), _safe_str(article).upper())
        cache = getattr(self, "_clone_linked_cache", None)
        if cache is None:
            cache = {}
            self._clone_linked_cache = cache
        cached = cache.get(key)
        if cached is not None:
            return bool(cached)

        storage = self.storage
        supplier_col_ap = storage.first_existing_column(table="article_prd", candidates=["supplierid", "supplierId", "SupplierId", "supplier_id", "supplier"])
        article_col_ap = storage.first_existing_column(
            table="article_prd",
            candidates=["datasupplierarticlenumber", "DataSupplierArticleNumber", "articleNumber", "articlenumber", "article", "number"],
        )
        product_col_ap = storage.first_existing_column(table="article_prd", candidates=["productId", "productid", "id", "prdId", "prdid"])
        prd_id_col = storage.first_existing_column(table="prd", candidates=["id", "productId", "productid", "prdId", "prdid"])
        if not supplier_col_ap or not article_col_ap or not product_col_ap or not prd_id_col:
            cache[key] = False
            return False

        rows = storage.fetch_local_rows(
            table="article_prd",
            filters={supplier_col_ap: int(supplier_id), article_col_ap: article},
            columns=[product_col_ap],
            limit=200,
        )
        if not rows:
            cache[key] = False
            return False

        product_ids = [row.get(product_col_ap) for row in rows if row.get(product_col_ap) not in (None, "")]
        if not product_ids:
            cache[key] = False
            return False

        prd_rows = storage.fetch_local_rows_in(
            table="prd",
            column=prd_id_col,
            values=product_ids,
            columns=[prd_id_col],
            limit=1,
        )
        linked = bool(prd_rows)
        cache[key] = linked
        return linked
