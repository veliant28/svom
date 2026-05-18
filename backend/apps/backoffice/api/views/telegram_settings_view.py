from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.serializers import (
    TelegramSettingsSerializer,
    TelegramTestMessageResponseSerializer,
    TelegramTestMessageSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.core.selectors import get_telegram_settings
from apps.core.services import TelegramDispatchError, send_telegram_test_message


class BackofficeTelegramSettingsAPIView(BackofficeAPIView):
    required_capability = "telegram.manage"

    def get(self, request):
        serializer = TelegramSettingsSerializer(get_telegram_settings())
        return Response(serializer.data)

    def patch(self, request):
        settings = get_telegram_settings()
        serializer = TelegramSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BackofficeTelegramTestAPIView(BackofficeAPIView):
    required_capability = "telegram.manage"

    def post(self, request):
        serializer = TelegramTestMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        text = str(serializer.validated_data.get("text") or "").strip() or "SVOM test notification"
        try:
            send_telegram_test_message(bot_kind=serializer.validated_data["bot"], text=text)
        except TelegramDispatchError as exc:
            payload = TelegramTestMessageResponseSerializer({"ok": False, "message": str(exc)}).data
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)

        payload = TelegramTestMessageResponseSerializer({"ok": True, "message": "Message sent."}).data
        return Response(payload, status=status.HTTP_200_OK)
