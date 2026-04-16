from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers, status
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.api.views.supplier_workspace_views import supplier_action_error_response
from apps.backoffice.services import SupplierPriceWorkflowService
from apps.supplier_imports.services.integrations.exceptions import SupplierClientError, SupplierCooldownError, SupplierIntegrationError


class SupplierPriceListRequestSerializer(serializers.Serializer):
    format = serializers.CharField(required=False, allow_blank=True, default="xlsx", max_length=16)
    in_stock = serializers.BooleanField(required=False, default=True)
    show_scancode = serializers.BooleanField(required=False, default=False)
    utr_article = serializers.BooleanField(required=False, default=False)
    visible_brands = serializers.ListField(
        required=False,
        default=list,
        child=serializers.IntegerField(min_value=1),
    )
    categories = serializers.ListField(
        required=False,
        default=list,
        child=serializers.CharField(max_length=64),
    )
    models_filter = serializers.ListField(
        required=False,
        default=list,
        child=serializers.CharField(max_length=120),
    )


class SupplierPriceListListAPIView(BackofficeAPIView):
    def get(self, request, code: str):
        try:
            rows = SupplierPriceWorkflowService().list_price_lists(supplier_code=code)
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"count": len(rows), "results": rows}, status=status.HTTP_200_OK)


class SupplierPriceListParamsAPIView(BackofficeAPIView):
    def get(self, request, code: str):
        try:
            payload = SupplierPriceWorkflowService().get_request_params(supplier_code=code)
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierPriceListRequestAPIView(BackofficeAPIView):
    def post(self, request, code: str):
        serializer = SupplierPriceListRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            row = SupplierPriceWorkflowService().request_price_list(
                supplier_code=code,
                requested_format=str(data.get("format", "xlsx")).strip() or "xlsx",
                in_stock=bool(data.get("in_stock", True)),
                show_scancode=bool(data.get("show_scancode", False)),
                utr_article=bool(data.get("utr_article", False)),
                visible_brands=list(data.get("visible_brands", [])),
                categories=list(data.get("categories", [])),
                models_filter=list(data.get("models_filter", [])),
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response({"price_list": row}, status=status.HTTP_200_OK)


class SupplierPriceListDownloadAPIView(BackofficeAPIView):
    def post(self, request, code: str, price_list_id: str):
        try:
            row = SupplierPriceWorkflowService().download_price_list(
                supplier_code=code,
                price_list_id=price_list_id,
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response({"price_list": row}, status=status.HTTP_200_OK)


class SupplierPriceListImportAPIView(BackofficeAPIView):
    def post(self, request, code: str, price_list_id: str):
        try:
            payload = SupplierPriceWorkflowService().import_price_list_to_raw(
                supplier_code=code,
                price_list_id=price_list_id,
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)


class SupplierPriceListDeleteAPIView(BackofficeAPIView):
    def post(self, request, code: str, price_list_id: str):
        try:
            payload = SupplierPriceWorkflowService().delete_price_list(
                supplier_code=code,
                price_list_id=price_list_id,
            )
        except ObjectDoesNotExist:
            return Response({"detail": "Supplier workspace not found."}, status=status.HTTP_404_NOT_FOUND)
        except (SupplierCooldownError, SupplierClientError, SupplierIntegrationError) as exc:
            return supplier_action_error_response(exc)
        return Response(payload, status=status.HTTP_200_OK)
