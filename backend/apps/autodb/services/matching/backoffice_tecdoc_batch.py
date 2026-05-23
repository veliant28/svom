from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q

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
    AUTO_SCAN_LIMIT_MULTIPLIER = 20
    AUTO_SCAN_LIMIT_CAP = 20_000

    def __init__(self, *, storage: AutoDbRawCloneStorage | None = None):
        self.storage = storage or AutoDbRawCloneStorage()
        self._non_tecdoc = {
            normalize_brand_lookup_key(str(item).strip())
            for item in NON_TECDOC_BRAND_KEYS
            if str(item).strip()
        }

    def select_candidates(
        self,
        *,
        limit: int,
        product_ids: list[str] | None = None,
        only_new_tecdoc: bool = False,
    ) -> list[TecdocBatchCandidate]:
        target_limit = max(1, min(int(limit or 0), 1000))
        selected: list[TecdocBatchCandidate] = []
        requested_product_ids = [str(item).strip() for item in (product_ids or []) if str(item).strip()]
        queryset = self._base_queryset(
            product_ids=requested_product_ids or None,
            only_new_tecdoc=bool(only_new_tecdoc),
        )
        scanned = 0
        if requested_product_ids:
            max_scan = len(requested_product_ids)
        else:
            max_scan = min(
                max(target_limit * self.AUTO_SCAN_LIMIT_MULTIPLIER, target_limit),
                self.AUTO_SCAN_LIMIT_CAP,
            )
        for product in queryset.iterator(chunk_size=250):
            scanned += 1
            if scanned > max_scan:
                break
            supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0)
            article = _safe_str(getattr(product, "autodb_article_number", "")) or _safe_str(getattr(product, "article", ""))
            supplier_name = _safe_str(getattr(product, "autodb_supplier_name", "")) or _safe_str(getattr(product, "display_brand_name", ""))
            if not article:
                continue
            if supplier_id <= 0 and not supplier_name:
                continue
            if self._has_trusted_link_quality(product):
                continue
            if self._is_non_tecdoc(product):
                continue
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

    def _base_queryset(self, *, product_ids: list[str] | None = None, only_new_tecdoc: bool = False):
        queryset = (
            Product.objects
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
            .only("id", "autodb_supplier_id", "autodb_supplier_name", "autodb_article_number", "article", "display_brand_name", "autodb_article_key")
        )
        if only_new_tecdoc:
            queryset = queryset.filter(autodb_supplier_id__isnull=False).exclude(autodb_supplier_id=0)
            queryset = queryset.filter(Q(autodb_article_key__isnull=True) | Q(autodb_article_key=""))
            queryset = queryset.exclude(
                autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
            )
        if product_ids:
            return queryset.filter(id__in=product_ids).order_by("-id")
        return queryset.order_by("-id")

    def _has_trusted_link_quality(self, product: Product) -> bool:
        product_id = str(getattr(product, "id", "") or "")
        article_key = _safe_str(getattr(product, "autodb_article_key", ""))
        if not product_id or not article_key:
            return False
        cache_key = (product_id, article_key)
        cache = getattr(self, "_trusted_cache", None)
        if cache is None:
            cache = {}
            self._trusted_cache = cache
        cached = cache.get(cache_key)
        if cached is not None:
            return bool(cached)

        trusted = AutoDbProductLinkQuality.objects.filter(
            product_id=product_id,
            autodb_article_key=article_key,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).exists()
        cache[cache_key] = bool(trusted)
        return bool(trusted)

    def _is_non_tecdoc(self, product: Product) -> bool:
        brand = _safe_str(getattr(product, "display_brand_name", "")) or _safe_str(getattr(product, "autodb_supplier_name", ""))
        if not brand:
            return False
        normalized = normalize_brand_lookup_key(brand)
        return normalized in self._non_tecdoc

    def _is_clone_linked(self, *, supplier_id: int, article: str) -> bool:
        article_value = _safe_str(article)
        key = (int(supplier_id), article_value.upper())
        cache = getattr(self, "_clone_linked_cache", None)
        if cache is None:
            cache = {}
            self._clone_linked_cache = cache
        cached = cache.get(key)
        if cached is not None:
            return bool(cached)
        article_variants: list[str] = []
        for candidate in (article_value, "".join(article_value.split())):
            value = _safe_str(candidate)
            if value and value not in article_variants:
                article_variants.append(value)
        if not article_variants:
            cache[key] = False
            return False

        storage = self.storage
        supplier_col_ap = storage.first_existing_column(table="article_prd", candidates=["supplierid", "supplierId", "SupplierId", "supplier_id", "supplier"])
        article_col_ap = storage.first_existing_column(
            table="article_prd",
            candidates=["datasupplierarticlenumber", "DataSupplierArticleNumber", "articleNumber", "articlenumber", "article", "number"],
        )
        product_col_ap = storage.first_existing_column(table="article_prd", candidates=["productId", "productid", "id", "prdId", "prdid"])
        prd_id_col = storage.first_existing_column(table="prd", candidates=["id", "productId", "productid", "prdId", "prdid"])
        if not supplier_col_ap or not article_col_ap or not product_col_ap or not prd_id_col:
            for value in article_variants:
                cache[(int(supplier_id), value.upper())] = False
            return False

        for variant in article_variants:
            rows = storage.fetch_local_rows(
                table="article_prd",
                filters={supplier_col_ap: int(supplier_id), article_col_ap: variant},
                columns=[product_col_ap],
                limit=200,
            )
            if not rows:
                continue

            product_ids = [row.get(product_col_ap) for row in rows if row.get(product_col_ap) not in (None, "")]
            if not product_ids:
                continue

            prd_rows = storage.fetch_local_rows_in(
                table="prd",
                column=prd_id_col,
                values=product_ids,
                columns=[prd_id_col],
                limit=1,
            )
            if prd_rows:
                for value in article_variants:
                    cache[(int(supplier_id), value.upper())] = True
                return True

        for value in article_variants:
            cache[(int(supplier_id), value.upper())] = False
        return False
