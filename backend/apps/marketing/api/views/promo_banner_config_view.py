from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.marketing.api.serializers import PromoBannerPublicSettingsSerializer, PromoBannerSerializer
from apps.marketing.selectors import get_active_promo_banners_queryset, get_promo_banner_settings


class PromoBannerConfigAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        settings_serializer = PromoBannerPublicSettingsSerializer(get_promo_banner_settings())
        banners_serializer = PromoBannerSerializer(
            get_active_promo_banners_queryset(),
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "settings": settings_serializer.data,
                "banners": banners_serializer.data,
            }
        )

