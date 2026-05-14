from __future__ import annotations

from dataclasses import asdict

from django.core.paginator import Paginator
from django.db.models import Exists, Q
from rest_framework import status
from rest_framework.response import Response

from apps.autodb.models import AutoDbMatchJob
from apps.autodb.services.matching.brand_coverage import AutoDbBrandCoverageAuditService

from .._base import BackofficeAPIView
from .serializers import serialize_job, serialize_job_detail
from .utils import job_trusted_link_exists_queryset, parse_bool, parse_positive_int, parse_supplier_id, safe_str


class BackofficeAutoDbMatchingJobsAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request):
        page = parse_positive_int(request.query_params.get("page"), default=1)
        page_size = parse_positive_int(request.query_params.get("page_size"), default=25, maximum=100)
        queryset = self._filtered_queryset(request).order_by(*self._ordering(request)).distinct()
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        return Response({"count": paginator.count, "results": [serialize_job(item) for item in page_obj.object_list]})

    def _base_queryset(self):
        return (
            AutoDbMatchJob.objects.select_related(
                "product",
                "product__brand",
                "product__category",
                "product__product_price",
                "supplier_offer",
                "supplier_offer__supplier",
            )
            .prefetch_related("evidence", "product__supplier_offers__supplier")
            .annotate(_trusted=Exists(job_trusted_link_exists_queryset()))
            .filter(_trusted=False)
        )

    def _filtered_queryset(self, request):
        queryset = self._base_queryset()
        query = safe_str(request.query_params.get("q"))
        supplier_code = safe_str(request.query_params.get("supplier_code"))
        brand = safe_str(request.query_params.get("brand"))
        autodb_supplier = safe_str(request.query_params.get("autodb_supplier"))
        matching_status = safe_str(request.query_params.get("matching_status"))
        article_source = safe_str(request.query_params.get("article_source"))
        tecdoc_status = safe_str(request.query_params.get("tecdoc_status"))
        has_price = parse_bool(request.query_params.get("has_price"))
        stock_gt_0 = parse_bool(request.query_params.get("stock_gt_0"))

        if query:
            queryset = queryset.filter(
                Q(product__sku__icontains=query)
                | Q(product__svom_sku__icontains=query)
                | Q(product__name__icontains=query)
                | Q(raw_brand__icontains=query)
                | Q(article_value__icontains=query)
                | Q(canonical_article__icontains=query)
                | Q(supplier_code__icontains=query)
            )
        if supplier_code:
            queryset = queryset.filter(supplier_code=supplier_code)
        if brand:
            queryset = queryset.filter(Q(raw_brand__icontains=brand) | Q(product__brand__name__icontains=brand))
        if autodb_supplier:
            supplier_id = parse_supplier_id(autodb_supplier)
            queryset = queryset.filter(resolved_supplier_id=supplier_id) if supplier_id else queryset.filter(raw_brand__icontains=autodb_supplier)
        if matching_status:
            queryset = queryset.filter(status=matching_status)
        if article_source:
            queryset = queryset.filter(article_source_type=article_source)
        if has_price is not None:
            queryset = queryset.filter(product__product_price__isnull=not has_price)
        queryset = self._apply_stock_filter(queryset, stock_gt_0)
        queryset = self._apply_tecdoc_filter(queryset, tecdoc_status)
        return self._apply_flag_filters(queryset, request)

    def _apply_stock_filter(self, queryset, stock_gt_0: bool | None):
        if stock_gt_0 is True:
            return queryset.filter(Q(supplier_offer__stock_qty__gt=0) | Q(product__available_stock_qty_cached__gt=0))
        if stock_gt_0 is False:
            return queryset.filter(Q(supplier_offer__stock_qty__lte=0) | Q(supplier_offer__isnull=True))
        return queryset

    def _apply_tecdoc_filter(self, queryset, tecdoc_status: str):
        if tecdoc_status == "tecdoc":
            return queryset.exclude(resolved_supplier_id__isnull=True).exclude(status=AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC)
        if tecdoc_status == "non_tecdoc":
            return queryset.filter(status=AutoDbMatchJob.STATUS_SKIPPED_NON_TECDOC)
        if tecdoc_status == "unknown":
            return queryset.filter(
                Q(resolved_supplier_id__isnull=True)
                | Q(status__in=[AutoDbMatchJob.STATUS_SKIPPED_BRAND_UNRESOLVED, AutoDbMatchJob.STATUS_SKIPPED_UNSAFE_AMBIGUOUS])
            )
        return queryset

    def _apply_flag_filters(self, queryset, request):
        flag_status_map = {
            "only_safe_candidates": AutoDbMatchJob.STATUS_SAFE_LINK_CANDIDATE,
            "needs_review": AutoDbMatchJob.STATUS_NEEDS_REVIEW,
            "quota_paused": AutoDbMatchJob.STATUS_QUOTA_PAUSED,
            "bad_article_source": AutoDbMatchJob.STATUS_SKIPPED_BAD_ARTICLE_SOURCE,
            "split_needed": AutoDbMatchJob.STATUS_SKIPPED_SPLIT_NEEDED,
            "unsafe_ambiguous": AutoDbMatchJob.STATUS_SKIPPED_UNSAFE_AMBIGUOUS,
        }
        for param, status_value in flag_status_map.items():
            if parse_bool(request.query_params.get(param)) is True:
                queryset = queryset.filter(status=status_value)
        return queryset

    def _ordering(self, request) -> tuple[str, str]:
        ordering_map = {
            "sku": "product__sku",
            "name": "product__name",
            "brand": "raw_brand",
            "supplier_code": "supplier_code",
            "article": "canonical_article",
            "status": "status",
            "updated_at": "updated_at",
            "stock": "supplier_offer__stock_qty",
        }
        sort_key = safe_str(request.query_params.get("ordering")) or "updated_at"
        descending = sort_key.startswith("-")
        clean_sort = sort_key[1:] if descending else sort_key
        ordering = ordering_map.get(clean_sort, "updated_at")
        if descending or clean_sort == "updated_at":
            ordering = f"-{ordering}"
        return ordering, "id"


class BackofficeAutoDbMatchingJobDetailAPIView(BackofficeAPIView):
    required_capability = "autocatalog.view"

    def get(self, request, id):
        job = (
            AutoDbMatchJob.objects.select_related(
                "product",
                "product__brand",
                "product__category",
                "product__product_price",
                "supplier_offer",
                "supplier_offer__supplier",
            )
            .prefetch_related("evidence", "product__supplier_offers__supplier")
            .get(id=id)
        )
        return Response(serialize_job_detail(job))


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
