from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.services import SupplierWorkspaceService
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierCooldownError, SupplierIntegrationError


class SupplierSettingsSerializer(serializers.Serializer):
    login = serializers.CharField(required=False, allow_blank=True, max_length=255)
    password = serializers.CharField(required=False, allow_blank=True, max_length=255)
    browser_fingerprint = serializers.CharField(required=False, allow_blank=True, max_length=128)
    is_enabled = serializers.BooleanField(required=False)


class SupplierWorkspaceListAPIView(BackofficeAPIView):
    def get(self, request):
        rows = SupplierWorkspaceService().list_suppliers()
        return Response(rows, status=status.HTTP_200_OK)


class SupplierWorkspaceDetailAPIView(BackofficeAPIView):
    def get(self, request, code: str):
        try:
            payload = SupplierWorkspaceService().get_workspace(supplier_code=code)
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierWorkspaceSettingsAPIView(BackofficeAPIView):
    def patch(self, request, code: str):
        serializer = SupplierSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = SupplierWorkspaceService().update_settings(
                supplier_code=code,
                login=data.get("login"),
                password=data.get("password"),
                browser_fingerprint=data.get("browser_fingerprint"),
                is_enabled=data.get("is_enabled"),
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except SupplierIntegrationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


def supplier_action_error_response(exc: Exception) -> Response:
    if isinstance(exc, SupplierCooldownError):
        return Response(
            {
                "detail": f"Слишком рано. Следующий запрос к UTR можно выполнить через {exc.retry_after_seconds} сек.",
                "retry_after_seconds": exc.retry_after_seconds,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    if isinstance(exc, (SupplierClientError, SupplierIntegrationError)):
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({"detail": "Supplier action failed."}, status=status.HTTP_400_BAD_REQUEST)
