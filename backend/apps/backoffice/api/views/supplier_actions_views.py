from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.api.views.supplier_workspace_views import supplier_action_error_response
from apps.backoffice.services import SupplierWorkspaceService
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierCooldownError, SupplierIntegrationError


class SupplierImportActionSerializer(serializers.Serializer):
    dry_run = serializers.BooleanField(default=False)
    dispatch_async = serializers.BooleanField(default=False)


class SupplierSyncPricesActionSerializer(serializers.Serializer):
    dispatch_async = serializers.BooleanField(default=False)


class SupplierPublishMappedProductsSerializer(serializers.Serializer):
    include_needs_review = serializers.BooleanField(default=False)
    dry_run = serializers.BooleanField(default=False)
    reprice_after_publish = serializers.BooleanField(default=True)


class SupplierTokenObtainAPIView(BackofficeAPIView):
    def post(self, request, code: str):
        try:
            payload = SupplierWorkspaceService().obtain_token(supplier_code=code)
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierTokenRefreshAPIView(BackofficeAPIView):
    def post(self, request, code: str):
        try:
            payload = SupplierWorkspaceService().refresh_token(supplier_code=code)
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierConnectionCheckAPIView(BackofficeAPIView):
    def post(self, request, code: str):
        try:
            payload = SupplierWorkspaceService().check_connection(supplier_code=code)
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierImportRunAPIView(BackofficeAPIView):
    def post(self, request, code: str):
        serializer = SupplierImportActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = SupplierWorkspaceService().run_import(
                supplier_code=code,
                dry_run=data.get("dry_run", False),
                dispatch_async=data.get("dispatch_async", False),
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierPricesSyncAPIView(BackofficeAPIView):
    def post(self, request, code: str):
        serializer = SupplierSyncPricesActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = SupplierWorkspaceService().sync_prices(
                supplier_code=code,
                dispatch_async=data.get("dispatch_async", False),
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierPublishMappedProductsAPIView(BackofficeAPIView):
    def post(self, request, code: str):
        serializer = SupplierPublishMappedProductsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = SupplierWorkspaceService().publish_mapped_products(
                supplier_code=code,
                include_needs_review=data.get("include_needs_review", False),
                dry_run=data.get("dry_run", False),
                reprice_after_publish=data.get("reprice_after_publish", True),
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except SupplierIntegrationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload, status=status.HTTP_200_OK)


class UtrBrandsImportAPIView(BackofficeAPIView):
    def post(self, request):
        try:
            payload = SupplierWorkspaceService().import_utr_brands()
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)
