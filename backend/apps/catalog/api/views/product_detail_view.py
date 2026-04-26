from rest_framework.generics import RetrieveAPIView

from apps.catalog.api.serializers import ProductDetailSerializer
from apps.catalog.selectors import get_product_detail_queryset
from apps.catalog.services import FITMENT_ALL, FitmentFilteringService


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
