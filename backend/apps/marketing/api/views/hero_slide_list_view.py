from rest_framework.generics import ListAPIView

from apps.marketing.api.serializers import HeroSlideSerializer
from apps.marketing.selectors import get_active_hero_slides_queryset


class HeroSlideListAPIView(ListAPIView):
    serializer_class = HeroSlideSerializer
    pagination_class = None

    def get_queryset(self):
        return get_active_hero_slides_queryset()
