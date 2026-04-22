from __future__ import annotations

from rest_framework.response import Response

from apps.backoffice.api.serializers.footer_settings_serializer import BackofficeFooterSettingsSerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.marketing.selectors import get_footer_settings


class BackofficeFooterSettingsAPIView(BackofficeAPIView):
    required_capability = "footer.settings"

    def get(self, request):
        serializer = BackofficeFooterSettingsSerializer(get_footer_settings())
        return Response(serializer.data)

    def patch(self, request):
        settings = get_footer_settings()
        serializer = BackofficeFooterSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
