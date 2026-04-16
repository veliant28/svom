from rest_framework.generics import ListAPIView

from apps.catalog.api.serializers import CategoryListSerializer
from apps.catalog.selectors import get_active_categories_queryset


class CategoryListAPIView(ListAPIView):
    serializer_class = CategoryListSerializer
    pagination_class = None

    def get_queryset(self):
        return get_active_categories_queryset()
