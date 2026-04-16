from rest_framework.generics import ListAPIView

from apps.marketing.api.serializers import PromoBannerSerializer
from apps.marketing.selectors import get_active_promo_banners_queryset


class PromoBannerListAPIView(ListAPIView):
    serializer_class = PromoBannerSerializer
    pagination_class = None

    def get_queryset(self):
        return get_active_promo_banners_queryset()
