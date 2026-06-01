from django.core.paginator import InvalidPage
from django.db.models import Count, F, Q
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from apps.catalog.api.filters import ProductFilterSet
from apps.catalog.api.serializers import ProductListSerializer
from apps.catalog.models import AutoDbProductLinkQuality
from apps.catalog.selectors import get_public_products_queryset
from apps.catalog.services import FitmentFilteringService
from apps.catalog.services.product_fitment_lookup import resolve_selected_passanger_car_id
from apps.compatibility.models import ProductFitment
from apps.search.services import ProductSearchService


class ProductListAPIView(ListAPIView):
    class CatalogProductPagination(PageNumberPagination):
        page_size = 52
        page_size_query_param = "page_size"
        max_page_size = 100

        def paginate_queryset(self, queryset, request, view=None):
            page_size = self.get_page_size(request)
            if not page_size:
                return None

            paginator = self.django_paginator_class(queryset, page_size)
            page_number = self.get_page_number(request, paginator)

            try:
                self.page = paginator.page(page_number)
            except InvalidPage:
                # When filters shrink result set (for example after selecting vehicle),
                # keep API stable by returning the first page instead of HTTP 404.
                self.page = paginator.page(1)

            if paginator.num_pages > 1 and self.template is not None:
                self.display_page_controls = True

            self.request = request
            return list(self.page)

    serializer_class = ProductListSerializer
    pagination_class = CatalogProductPagination
    filterset_class = ProductFilterSet
    ordering_fields = ("name", "created_at", "product_price__final_price", "available_stock_qty", "available_stock_qty_cached")
    ordering = ("-available_stock_qty", "name", "id")

    @staticmethod
    def _is_fitment_all_mode(request) -> bool:
        return str(request.query_params.get("fitment") or "").strip().lower() == "all"

    @staticmethod
    def _selected_vehicle_id(request) -> int | None:
        return resolve_selected_passanger_car_id(request)

    def _prime_page_fitment_counts(self, rows: list) -> None:
        product_ids = [str(getattr(row, "id", "")) for row in rows if getattr(row, "id", None)]
        if not product_ids:
            return
        article_key_by_product = {
            str(getattr(row, "id", "")): str(getattr(row, "autodb_article_key", "") or "").strip()
            for row in rows
            if getattr(row, "id", None)
        }
        trusted_products: set[str] = set()
        if any(getattr(row, "_has_trusted_link_quality", None) is None for row in rows):
            trusted_rows = AutoDbProductLinkQuality.objects.filter(
                product_id__in=product_ids,
                status=AutoDbProductLinkQuality.STATUS_TRUSTED,
            ).values_list("product_id", "autodb_article_key")
            for product_id, article_key in trusted_rows:
                pid = str(product_id)
                if str(article_key or "").strip() == article_key_by_product.get(pid, ""):
                    trusted_products.add(pid)

        counts = (
            ProductFitment.objects.filter(
                product_id__in=product_ids,
                autodb_passanger_car_id__isnull=False,
                is_stale=False,
                excluded_from_public_filtering=False,
                quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
                source__in=(ProductFitment.SOURCE_AUTODB_PRO, ProductFitment.SOURCE_MANUAL),
            )
            .values("product_id")
            .annotate(
                autodb_count=Count(
                    "autodb_passanger_car_id",
                    filter=Q(source=ProductFitment.SOURCE_AUTODB_PRO),
                    distinct=True,
                ),
                manual_count=Count(
                    "autodb_passanger_car_id",
                    filter=Q(source=ProductFitment.SOURCE_MANUAL),
                    distinct=True,
                ),
            )
        )
        counts_by_product = {
            str(row["product_id"]): {
                "autodb": int(row["autodb_count"] or 0),
                "manual": int(row["manual_count"] or 0),
            }
            for row in counts
        }
        for row in rows:
            product_id = str(getattr(row, "id", ""))
            values = counts_by_product.get(product_id, {"autodb": 0, "manual": 0})
            autodb_count = int(values["autodb"])
            manual_count = int(values["manual"])
            trusted_attr = getattr(row, "_has_trusted_link_quality", None)
            has_trusted_link = bool(trusted_attr) if trusted_attr is not None else (product_id in trusted_products)
            total = manual_count + (autodb_count if has_trusted_link else 0)
            setattr(row, "_public_fitment_count", int(total))
            setattr(row, "has_fitment_data", bool(total > 0))

    def _prime_page_fitment_compatibility(self, rows: list) -> None:
        selected_vehicle_id = self._selected_vehicle_id(self.request)
        if not rows:
            return
        if not selected_vehicle_id:
            for row in rows:
                setattr(row, "fits_selected_vehicle", None)
            return

        product_ids = [str(getattr(row, "id", "")) for row in rows if getattr(row, "id", None)]
        if not product_ids:
            return
        article_key_by_product = {
            str(getattr(row, "id", "")): str(getattr(row, "autodb_article_key", "") or "").strip()
            for row in rows
            if getattr(row, "id", None)
        }
        trusted_rows = AutoDbProductLinkQuality.objects.filter(
            product_id__in=product_ids,
            status=AutoDbProductLinkQuality.STATUS_TRUSTED,
        ).values_list("product_id", "autodb_article_key")
        trusted_products: set[str] = set()
        for product_id, article_key in trusted_rows:
            pid = str(product_id)
            if str(article_key or "").strip() == article_key_by_product.get(pid, ""):
                trusted_products.add(pid)

        selected_fitments = ProductFitment.objects.filter(
            product_id__in=product_ids,
            autodb_passanger_car_id=selected_vehicle_id,
            is_stale=False,
            excluded_from_public_filtering=False,
            quality_status=ProductFitment.QUALITY_STATUS_TRUSTED,
            source__in=(ProductFitment.SOURCE_AUTODB_PRO, ProductFitment.SOURCE_MANUAL),
        ).values_list("product_id", "source")

        manual_products: set[str] = set()
        autodb_products: set[str] = set()
        for product_id, source in selected_fitments:
            pid = str(product_id)
            if str(source or "") == ProductFitment.SOURCE_MANUAL:
                manual_products.add(pid)
            else:
                autodb_products.add(pid)

        for row in rows:
            product_id = str(getattr(row, "id", ""))
            fits = product_id in manual_products or (
                product_id in autodb_products and product_id in trusted_products
            )
            setattr(row, "fits_selected_vehicle", bool(fits))

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            self._prime_page_fitment_counts(page)
            self._prime_page_fitment_compatibility(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        rows = list(queryset)
        self._prime_page_fitment_counts(rows)
        self._prime_page_fitment_compatibility(rows)
        serializer = self.get_serializer(rows, many=True)
        return Response(serializer.data)

    def get_queryset(self):
        queryset = get_public_products_queryset().annotate(
            available_stock_qty=F("available_stock_qty_cached")
        )
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = ProductSearchService().apply(queryset, query)
        if self._is_fitment_all_mode(self.request):
            return queryset
        queryset, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params=self.request.query_params,
        )
        return queryset
