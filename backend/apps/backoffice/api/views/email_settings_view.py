from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.serializers.email_settings_serializer import (
    EmailDeliverySettingsSerializer,
    EmailDeliveryTestResponseSerializer,
    EmailDeliveryTestSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.core.selectors import get_email_delivery_settings
from apps.core.services import send_email_settings_test_message


class BackofficeEmailSettingsAPIView(BackofficeAPIView):
    required_capability = "settings.manage"

    def get(self, request):
        serializer = EmailDeliverySettingsSerializer(get_email_delivery_settings())
        return Response(serializer.data)

    def patch(self, request):
        settings = get_email_delivery_settings()
        serializer = EmailDeliverySettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BackofficeEmailSettingsTestAPIView(BackofficeAPIView):
    required_capability = "settings.manage"

    def post(self, request):
        serializer = EmailDeliveryTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = send_email_settings_test_message(recipient=serializer.validated_data["recipient"])
        response_serializer = EmailDeliveryTestResponseSerializer(result)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
