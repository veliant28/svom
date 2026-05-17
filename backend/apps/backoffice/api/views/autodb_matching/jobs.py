from __future__ import annotations

from dataclasses import asdict
import re

from django.core.paginator import Paginator
from django.db.models import F, OuterRef, Q, Subquery
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.autodb.models import AutoDbMatchJob
from apps.autodb.services.matching.constants import NON_TECDOC_BRAND_KEYS
from apps.autodb.services.raw_clone_storage import AutoDbRawCloneStorage
from apps.autodb.services.supplier_brand_matcher import normalize_brand_lookup_key
from apps.catalog.models import AutoDbProductLinkQuality, Product
from apps.autodb.services.matching.brand_coverage import AutoDbBrandCoverageAuditService

from .._base import BackofficeAPIView
from .serializers import (
    serialize_fallback_product,
    serialize_fallback_product_detail,
    serialize_job_detail,
)
from .utils import parse_bool, parse_positive_int, parse_supplier_id, safe_str


class BackofficeAutoDbMatchingJobsAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"
    FALLBACK_LINKED_STATUS_ALIASES = {
        AutoDbMatchJob.STATUS_LINKED,
    }
    FALLBACK_LOCAL_FOUND_STATUS_ALIASES = {
        AutoDbMatchJob.STATUS_LOCAL_FOUND,
    }
    FALLBACK_REMOTE_FOUND_STATUS_ALIASES = {
        AutoDbMatchJob.STATUS_REMOTE_FOUND,
    }
    FALLBACK_UNRESOLVED_STATUS_ALIASES = {
        AutoDbMatchJob.STATUS_NEW,
        AutoDbMatchJob.STATUS_NEEDS_REVIEW,
        AutoDbMatchJob.STATUS_SKIPPED_BRAND_UNRESOLVED,
        AutoDbMatchJob.STATUS_SKIPPED_UNSAFE_AMBIGUOUS,
        AutoDbMatchJob.STATUS_SKIPPED_SPLIT_NEEDED,
        AutoDbMatchJob.STATUS_QUOTA_PAUSED,
        AutoDbMatchJob.STATUS_REMOTE_PENDING,
        AutoDbMatchJob.STATUS_REMOTE_NOT_FOUND,
    }

    def get(self, request):
        page = parse_positive_int(request.query_params.get("page"), default=1)
        page_size = parse_positive_int(request.query_params.get("page_size"), default=25, maximum=100)
        matching_status = safe_str(request.query_params.get("matching_status"))
        queryset = self._fallback_unlinked_products_queryset(request)
        queryset = self._apply_linked_fresh_ordering(queryset, request=request, matching_status=matching_status).distinct()
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        results = [
            serialize_fallback_product(
                item,
                matching_status=self._fallback_status_for_response(item=item, requested_status=matching_status),
                tecdoc_state=self._fallback_tecdoc_status(item),
            )
            for item in page_obj.object_list
        ]
        return Response({"count": paginator.count, "results": results})

    def _fallback_unlinked_products_queryset(self, request):
        matching_status = safe_str(request.query_params.get("matching_status"))
        tecdoc_status = safe_str(request.query_params.get("tecdoc_status"))
        queryset = (
            Product.objects.select_related("category", "product_price")
            .prefetch_related("supplier_offers__supplier")
        )
        queryset = self._apply_fallback_tecdoc_filter(
            queryset,
            tecdoc_status=tecdoc_status,
            matching_status=matching_status,
            linked_mode=True,
        )
        query = safe_str(request.query_params.get("q"))
        supplier_code = safe_str(request.query_params.get("supplier_code"))
        brand = safe_str(request.query_params.get("brand"))
        autodb_supplier = safe_str(request.query_params.get("autodb_supplier"))
        article_source = safe_str(request.query_params.get("article_source"))
        has_price = parse_bool(request.query_params.get("has_price"))
        stock_gt_0 = parse_bool(request.query_params.get("stock_gt_0"))

        if query:
            queryset = queryset.filter(
                Q(sku__icontains=query)
                | Q(svom_sku__icontains=query)
                | Q(name__icontains=query)
                | Q(display_brand_name__icontains=query)
                | Q(autodb_supplier_name__icontains=query)
                | Q(article__icontains=query)
            )
        if supplier_code:
            queryset = queryset.filter(supplier_offers__supplier__code=supplier_code)
        if brand:
            queryset = queryset.filter(Q(display_brand_name__icontains=brand) | Q(autodb_supplier_name__icontains=brand))
        if autodb_supplier:
            supplier_id = parse_supplier_id(autodb_supplier)
            queryset = queryset.filter(autodb_supplier_id=supplier_id) if supplier_id else queryset.filter(
                Q(display_brand_name__icontains=autodb_supplier)
                | Q(autodb_supplier_name__icontains=autodb_supplier)
            )
        if matching_status:
            if matching_status in self.FALLBACK_LINKED_STATUS_ALIASES:
                queryset = self._filter_fallback_linked_queryset(queryset)
            elif matching_status in self.FALLBACK_LOCAL_FOUND_STATUS_ALIASES:
                queryset = self._filter_fallback_local_found_queryset(queryset)
            elif matching_status in self.FALLBACK_REMOTE_FOUND_STATUS_ALIASES:
                return queryset.none()
            elif matching_status == AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC:
                queryset = self._only_explicit_non_tecdoc_brands(queryset)
            elif matching_status == AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE:
                queryset = queryset.filter(Q(article__isnull=True) | Q(article=""))
            elif matching_status == AutoDbMatchJob.STATUS_NEW:
                queryset = self._exclude_explicit_non_tecdoc_brands(queryset)
                queryset = queryset.filter(Q(article__isnull=False) & ~Q(article=""))
                queryset = queryset.filter(Q(autodb_article_key__isnull=True) | Q(autodb_article_key=""))
            elif matching_status == AutoDbMatchJob.STATUS_NEEDS_REVIEW:
                queryset = queryset.filter(
                    autodb_link_qualities__autodb_article_key=F("autodb_article_key"),
                    autodb_link_qualities__status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
                )
            elif matching_status in self.FALLBACK_UNRESOLVED_STATUS_ALIASES:
                return queryset.none()
            else:
                return queryset.none()
        if article_source and article_source not in {"product_article", "product"}:
            return queryset.none()
        if has_price is not None:
            queryset = queryset.filter(product_price__isnull=not has_price)
        if stock_gt_0 is True:
            queryset = queryset.filter(Q(available_stock_qty_cached__gt=0) | Q(supplier_offers__stock_qty__gt=0))
        elif stock_gt_0 is False:
            queryset = queryset.filter(Q(available_stock_qty_cached__lte=0) & Q(supplier_offers__isnull=True))
        if self._any_flag_filter_enabled(request):
            return queryset.none()
        return queryset

    def _exclude_explicit_non_tecdoc_brands(self, queryset):
        regex = self._non_tecdoc_brand_regex()
        if not regex:
            return queryset
        return queryset.exclude(
            Q(display_brand_name__iregex=regex)
            | Q(autodb_supplier_name__iregex=regex)
        )

    def _only_explicit_non_tecdoc_brands(self, queryset):
        regex = self._non_tecdoc_brand_regex()
        if not regex:
            return queryset.none()
        return queryset.filter(
            Q(display_brand_name__iregex=regex)
            | Q(autodb_supplier_name__iregex=regex)
        )

    def _non_tecdoc_brand_regex(self) -> str:
        non_tecdoc = sorted(
            {
                str(item).strip()
                for item in NON_TECDOC_BRAND_KEYS
                if str(item).strip()
            }
        )
        if not non_tecdoc:
            return ""
        pattern = "|".join(re.escape(item) for item in non_tecdoc if item)
        if not pattern:
            return ""
        return rf"^\s*(?:{pattern})\s*$"

    def _apply_fallback_tecdoc_filter(self, queryset, *, tecdoc_status: str, matching_status: str, linked_mode: bool):
        del linked_mode
        if matching_status == AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC:
            return self._only_explicit_non_tecdoc_brands(queryset)
        if tecdoc_status == "non_tecdoc":
            return self._only_explicit_non_tecdoc_brands(queryset)
        if tecdoc_status == "tecdoc":
            queryset = self._exclude_explicit_non_tecdoc_brands(queryset)
            return queryset.filter(autodb_supplier_id__isnull=False).filter(
                (
                    Q(autodb_article_number__isnull=False)
                    & ~Q(autodb_article_number="")
                )
                | (
                    Q(article__isnull=False)
                    & ~Q(article="")
                )
            )
        if tecdoc_status == "unknown":
            return queryset.filter(
                Q(autodb_supplier_id__isnull=True)
                | (
                    Q(autodb_supplier_id__isnull=False)
                    & (
                        Q(autodb_article_number__isnull=True)
                        | Q(autodb_article_number="")
                    )
                    & (
                        Q(article__isnull=True)
                        | Q(article="")
                    )
                )
            )
        if (
            matching_status not in self.FALLBACK_LINKED_STATUS_ALIASES
            and matching_status not in self.FALLBACK_LOCAL_FOUND_STATUS_ALIASES
            and matching_status not in self.FALLBACK_REMOTE_FOUND_STATUS_ALIASES
        ):
            return self._exclude_explicit_non_tecdoc_brands(queryset)
        return queryset

    def _is_non_tecdoc_product(self, item: Product) -> bool:
        brand = safe_str(getattr(item, "display_brand_name", "")) or safe_str(getattr(item, "autodb_supplier_name", ""))
        if not brand:
            return False
        normalized = normalize_brand_lookup_key(brand)
        normalized_non_tecdoc = {
            normalize_brand_lookup_key(str(value).strip())
            for value in NON_TECDOC_BRAND_KEYS
            if str(value).strip()
        }
        return normalized in normalized_non_tecdoc

    def _fallback_tecdoc_status(self, product: Product) -> str:
        if self._is_non_tecdoc_product(product):
            return "non_tecdoc"
        supplier_id = int(getattr(product, "autodb_supplier_id", 0) or 0)
        article = safe_str(getattr(product, "autodb_article_number", "")) or safe_str(getattr(product, "article", ""))
        if supplier_id > 0 and article:
            return "tecdoc"
        return "unknown"

    def _fallback_serialized_status(self, *, item: Product, requested_status: str) -> str:
        if self._has_needs_review_quality(item):
            return AutoDbMatchJob.STATUS_NEEDS_REVIEW
        if requested_status in self.FALLBACK_REMOTE_FOUND_STATUS_ALIASES:
            return AutoDbMatchJob.STATUS_REMOTE_FOUND
        if requested_status in self.FALLBACK_LINKED_STATUS_ALIASES:
            supplier_id = int(getattr(item, "autodb_supplier_id", 0) or 0)
            article = safe_str(getattr(item, "autodb_article_number", "")) or safe_str(getattr(item, "article", ""))
            has_link = bool(safe_str(getattr(item, "autodb_article_key", "")))
            return AutoDbMatchJob.STATUS_LINKED if supplier_id > 0 and article and has_link and self._is_clone_linked(
                supplier_id=supplier_id,
                article=article,
            ) else AutoDbMatchJob.STATUS_NEW
        if requested_status in self.FALLBACK_LOCAL_FOUND_STATUS_ALIASES:
            supplier_id = int(getattr(item, "autodb_supplier_id", 0) or 0)
            article = safe_str(getattr(item, "autodb_article_number", "")) or safe_str(getattr(item, "article", ""))
            has_link = bool(safe_str(getattr(item, "autodb_article_key", "")))
            return AutoDbMatchJob.STATUS_LOCAL_FOUND if supplier_id > 0 and article and not has_link else AutoDbMatchJob.STATUS_NEW
        if requested_status == AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC:
            return AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC
        if requested_status == AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE:
            return AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE
        if self._is_non_tecdoc_product(item):
            return AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC
        supplier_id = int(getattr(item, "autodb_supplier_id", 0) or 0)
        article = safe_str(getattr(item, "autodb_article_number", "")) or safe_str(getattr(item, "article", ""))
        has_link = bool(safe_str(getattr(item, "autodb_article_key", "")))
        if supplier_id > 0 and article and has_link and self._is_clone_linked(supplier_id=supplier_id, article=article):
            return AutoDbMatchJob.STATUS_LINKED
        if supplier_id > 0 and article and not has_link:
            return AutoDbMatchJob.STATUS_LOCAL_FOUND
        if not str(getattr(item, "article", "") or "").strip():
            return AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE
        return AutoDbMatchJob.STATUS_NEW

    def _fallback_status_for_response(self, *, item: Product, requested_status: str) -> str:
        if requested_status:
            return requested_status
        return self._fallback_serialized_status(item=item, requested_status=requested_status)

    def _apply_linked_fresh_ordering(self, queryset, *, request, matching_status: str):
        if matching_status in self.FALLBACK_LINKED_STATUS_ALIASES:
            trusted_checked = (
                AutoDbProductLinkQuality.objects.filter(
                    product_id=OuterRef("pk"),
                    autodb_article_key=OuterRef("autodb_article_key"),
                    status=AutoDbProductLinkQuality.STATUS_TRUSTED,
                )
                .order_by("-checked_at", "-updated_at")
                .values("checked_at")[:1]
            )
            return queryset.annotate(_linked_checked_at=Subquery(trusted_checked)).order_by("-_linked_checked_at", "-updated_at", "id")
        return queryset.order_by(*self._fallback_ordering(request))

    def _filter_fallback_linked_queryset(self, queryset):
        candidate = queryset.filter(autodb_supplier_id__isnull=False).exclude(autodb_article_key__isnull=True).exclude(autodb_article_key="")
        linked_ids = self._linked_product_ids(candidate)
        if not linked_ids:
            return queryset.none()
        return queryset.filter(id__in=linked_ids)

    def _filter_fallback_local_found_queryset(self, queryset):
        candidate = queryset.filter(autodb_supplier_id__isnull=False).filter(
            (
                Q(autodb_article_number__isnull=False)
                & ~Q(autodb_article_number="")
            )
            | (
                Q(article__isnull=False)
                & ~Q(article="")
            )
        )
        return candidate.filter(Q(autodb_article_key__isnull=True) | Q(autodb_article_key=""))

    def _has_needs_review_quality(self, item: Product) -> bool:
        article_key = safe_str(getattr(item, "autodb_article_key", ""))
        if not article_key:
            return False
        return AutoDbProductLinkQuality.objects.filter(
            product_id=item.id,
            autodb_article_key=article_key,
            status=AutoDbProductLinkQuality.STATUS_NEEDS_MANUAL_REVIEW,
        ).exists()

    def _linked_product_ids(self, queryset) -> list[str]:
        ids: list[str] = []
        rows = queryset.values("id", "autodb_supplier_id", "autodb_article_number", "article").iterator(chunk_size=250)
        for row in rows:
            supplier_id = int(row.get("autodb_supplier_id") or 0)
            article = safe_str(row.get("autodb_article_number")) or safe_str(row.get("article"))
            if supplier_id <= 0 or not article:
                continue
            if self._is_clone_linked(supplier_id=supplier_id, article=article):
                ids.append(str(row.get("id")))
        return ids

    def _has_local_article(self, *, supplier_id: int, article: str) -> bool:
        key = (int(supplier_id), safe_str(article).upper())
        cache = getattr(self, "_clone_local_article_cache", None)
        if cache is None:
            cache = {}
            self._clone_local_article_cache = cache
        cached = cache.get(key)
        if cached is not None:
            return bool(cached)
        storage = self._clone_storage()
        supplier_col_an = storage.first_existing_column(table="article_numbers", candidates=["supplierid", "supplierId", "SupplierId", "supplier_id", "supplier"])
        article_col_an = storage.first_existing_column(
            table="article_numbers",
            candidates=["datasupplierarticlenumber", "DataSupplierArticleNumber", "articleNumber", "articlenumber", "article", "number"],
        )
        if supplier_col_an and article_col_an:
            rows = storage.fetch_local_rows(
                table="article_numbers",
                filters={supplier_col_an: int(supplier_id), article_col_an: article},
                columns=[article_col_an],
                limit=1,
            )
            if rows:
                cache[key] = True
                return True
        linked = self._is_clone_linked(supplier_id=supplier_id, article=article)
        cache[key] = linked
        return linked

    def _is_clone_linked(self, *, supplier_id: int, article: str) -> bool:
        key = (int(supplier_id), safe_str(article).upper())
        cache = getattr(self, "_clone_linked_cache", None)
        if cache is None:
            cache = {}
            self._clone_linked_cache = cache
        cached = cache.get(key)
        if cached is not None:
            return bool(cached)
        storage = self._clone_storage()
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

    def _clone_storage(self) -> AutoDbRawCloneStorage:
        storage = getattr(self, "_clone_storage_cache", None)
        if storage is None:
            storage = AutoDbRawCloneStorage()
            self._clone_storage_cache = storage
        return storage

    def _fallback_ordering(self, request) -> tuple[str, str]:
        ordering_map = {
            "sku": "sku",
            "name": "name",
            "brand": "display_brand_name",
            "article": "article",
            "updated_at": "updated_at",
            "stock": "available_stock_qty_cached",
        }
        sort_key = safe_str(request.query_params.get("ordering")) or "updated_at"
        descending = sort_key.startswith("-")
        clean_sort = sort_key[1:] if descending else sort_key
        ordering = ordering_map.get(clean_sort, "updated_at")
        if descending or clean_sort == "updated_at":
            ordering = f"-{ordering}"
        return ordering, "id"

    def _any_flag_filter_enabled(self, request) -> bool:
        flag_params = (
            "only_safe_candidates",
            "needs_review",
            "quota_paused",
            "bad_article_source",
            "split_needed",
            "unsafe_ambiguous",
        )
        return any(parse_bool(request.query_params.get(item)) is True for item in flag_params)


class BackofficeAutoDbMatchingJobDetailAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request, id):
        helper = BackofficeAutoDbMatchingJobsAPIView()
        product = (
            Product.objects.select_related("category", "product_price")
            .prefetch_related("supplier_offers__supplier")
            .filter(id=id)
            .first()
        )
        if product is not None:
            status_guess = helper._fallback_serialized_status(item=product, requested_status="")
            tecdoc_state = helper._fallback_tecdoc_status(product)
            return Response(
                serialize_fallback_product_detail(
                    product,
                    matching_status=status_guess,
                    tecdoc_state=tecdoc_state,
                )
            )
        job = (
            AutoDbMatchJob.objects.select_related(
                "product",
                "product__category",
                "product__product_price",
                "supplier_offer",
                "supplier_offer__supplier",
            )
            .prefetch_related("evidence", "product__supplier_offers__supplier")
            .filter(id=id)
            .first()
        )
        if job is not None:
            return Response(serialize_job_detail(job))
        raise NotFound()


class BackofficeAutoDbMatchingBrandCoverageAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        try:
            rows = AutoDbBrandCoverageAuditService().audit(
                supplier_code=safe_str(request.query_params.get("supplier_code")),
                limit=parse_positive_int(request.query_params.get("limit"), default=200, maximum=1000),
            )
        except Exception as exc:  # noqa: BLE001
            return Response({"count": 0, "results": [], "error": safe_str(exc)}, status=status.HTTP_200_OK)
        payload = [asdict(item) for item in rows]
        return Response({"count": len(payload), "results": payload})
