from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.marketing.api.serializers.footer_settings_serializer import FooterSettingsSerializer
from apps.marketing.selectors import get_footer_settings


class FooterSettingsAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        serializer = FooterSettingsSerializer(get_footer_settings())
        return Response(serializer.data)
