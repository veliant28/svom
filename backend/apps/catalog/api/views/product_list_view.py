import logging

from django.conf import settings
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination

from apps.catalog.api.filters import ProductFilterSet
from apps.catalog.api.serializers import ProductListSerializer
from apps.catalog.selectors import get_public_products_queryset
from apps.catalog.services import FitmentFilteringService
from apps.catalog.services.utr_product_enrichment import request_visible_utr_enrichment
from apps.search.services import ProductSearchService

logger = logging.getLogger(__name__)


class ProductListAPIView(ListAPIView):
    class CatalogProductPagination(PageNumberPagination):
        page_size = 52
        page_size_query_param = "page_size"
        max_page_size = 100

    serializer_class = ProductListSerializer
    pagination_class = CatalogProductPagination
    filterset_class = ProductFilterSet
    ordering_fields = ("name", "created_at", "product_price__final_price", "available_stock_qty")
    ordering = ("-available_stock_qty", "name", "id")

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

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        self._enqueue_visible_utr_enrichment(response.data)
        return response

    def _enqueue_visible_utr_enrichment(self, payload):
        if not isinstance(payload, dict):
            return

        rows = payload.get("results")
        if not isinstance(rows, list):
            return

        product_ids: list[str] = []
        top_n = max(int(getattr(settings, "UTR_LAZY_CATALOG_APPLICABILITY_TOP_N", 12)), 0)
        if top_n <= 0:
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            product_id = row.get("id")
            if product_id:
                product_ids.append(str(product_id))
            if len(product_ids) >= top_n:
                break

        if not product_ids:
            return

        try:
            request_visible_utr_enrichment(
                product_ids=product_ids,
                request=self.request,
                enqueue=True,
                mode="catalog",
                allow_sync_fallback=False,
            )
        except Exception:
            logger.exception("catalog_visible_utr_enqueue_failed count=%s", len(product_ids))
