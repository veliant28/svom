from rest_framework.generics import ListAPIView

from apps.catalog.api.serializers import BrandListSerializer
from apps.catalog.selectors import get_active_brands_queryset


class BrandListAPIView(ListAPIView):
    serializer_class = BrandListSerializer
    pagination_class = None

    def get_queryset(self):
        return get_active_brands_queryset()
