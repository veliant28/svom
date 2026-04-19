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

    serializer_class = ProductListSerializer
    pagination_class = CatalogProductPagination
    filterset_class = ProductFilterSet
    ordering_fields = ("name", "created_at", "product_price__final_price")
    ordering = ("name",)

    def get_queryset(self):
        queryset = get_public_products_queryset()
        query = self.request.query_params.get("q", "").strip()
        if query:
            queryset = ProductSearchService().apply(queryset, query)
        queryset, _ = FitmentFilteringService().apply(
            queryset=queryset,
            params=self.request.query_params,
        )
        return queryset
