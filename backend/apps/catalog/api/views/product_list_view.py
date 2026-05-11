from django.core.paginator import InvalidPage
from django.db.models import F
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination

from apps.catalog.api.filters import ProductFilterSet
from apps.catalog.api.serializers import ProductListSerializer
from apps.catalog.selectors import get_public_products_queryset
from apps.catalog.services import FitmentFilteringService
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
    def _parse_bool(value: str) -> bool:
        normalized = str(value or "").strip().lower()
        return normalized in {"1", "true", "yes", "on"}

    @staticmethod
    def _with_positive_supplier_stock(queryset):
        return queryset.filter(
            supplier_offers__is_available=True,
            supplier_offers__stock_qty__gt=0,
        ).distinct()

    def get_queryset(self):
        queryset = get_public_products_queryset().annotate(
            available_stock_qty=F("available_stock_qty_cached")
        )
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = ProductSearchService().apply(queryset, query)
        queryset, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params=self.request.query_params,
        )
        if self._parse_bool(self.request.query_params.get("popular", "")):
            featured = self._with_positive_supplier_stock(queryset).filter(
                is_featured=True,
                product_price__final_price__gt=0,
            )
            if featured.exists():
                return featured.order_by("-updated_at", "-created_at", "-available_stock_qty_cached", "name", "id")
            return self._with_positive_supplier_stock(queryset).filter(
                product_price__final_price__gt=0,
            ).order_by("-updated_at", "-created_at", "-available_stock_qty_cached", "name", "id")
        return queryset
