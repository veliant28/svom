from rest_framework.generics import RetrieveAPIView

from apps.catalog.api.serializers import ProductDetailSerializer
from apps.catalog.selectors import get_product_detail_queryset


class ProductDetailAPIView(RetrieveAPIView):
    serializer_class = ProductDetailSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return get_product_detail_queryset()
