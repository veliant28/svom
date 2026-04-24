from rest_framework.response import Response
from rest_framework.views import APIView

from apps.marketing.api.serializers import HeroSlideSerializer, HeroSliderPublicSettingsSerializer
from apps.marketing.selectors import get_active_hero_slides_queryset, get_hero_slider_settings


class HeroSlideConfigAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        settings_serializer = HeroSliderPublicSettingsSerializer(get_hero_slider_settings())
        slides_serializer = HeroSlideSerializer(
            get_active_hero_slides_queryset(),
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "settings": settings_serializer.data,
                "slides": slides_serializer.data,
            }
        )
