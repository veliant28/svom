import logging

from rest_framework.generics import RetrieveAPIView

from apps.catalog.api.serializers import ProductDetailSerializer
from apps.catalog.selectors import get_product_detail_queryset
from apps.catalog.services import FITMENT_ALL, FitmentFilteringService
from apps.catalog.services.utr_product_enrichment import request_visible_utr_enrichment

logger = logging.getLogger(__name__)


class ProductDetailAPIView(RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        params = self.request.query_params.copy()
        params["fitment"] = FITMENT_ALL
        queryset, _ = FitmentFilteringService().apply(
            queryset=get_product_detail_queryset(),
            params=params,
        )
        return queryset

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        self._enqueue_product_utr_enrichment(response.data)
        return response

    def _enqueue_product_utr_enrichment(self, payload):
        if not isinstance(payload, dict):
            return

        product_id = payload.get("id")
        if not product_id:
            return

        try:
            request_visible_utr_enrichment(
                product_ids=[str(product_id)],
                request=self.request,
                enqueue=True,
                mode="detail",
                allow_sync_fallback=False,
            )
        except Exception:
            logger.exception("product_detail_utr_enqueue_failed product_id=%s", product_id)
