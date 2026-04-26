from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from apps.backoffice.api.serializers import (
    BackofficeOrderReceiptActionSerializer,
    BackofficeVchasnoKasaConnectionCheckSerializer,
    BackofficeVchasnoKasaSettingsSerializer,
    BackofficeVchasnoKasaShiftStatusSerializer,
    BackofficeVchasnoReceiptListSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.commerce.models import Order, OrderReceipt
from apps.commerce.services.vchasno_kasa import (
    VchasnoKasaError,
    close_vchasno_shift,
    get_open_receipt_url,
    get_vchasno_kasa_settings,
    get_vchasno_shift_status,
    has_order_receipt_table,
    has_vchasno_kasa_settings_table,
    issue_order_receipt,
    open_vchasno_shift,
    serialize_receipt_summary,
    sync_order_receipt,
    test_vchasno_kasa_connection,
)


class BackofficeVchasnoKasaSettingsAPIView(BackofficeAPIView):
    def get(self, request):
        serializer = BackofficeVchasnoKasaSettingsSerializer(get_vchasno_kasa_settings(), context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        if not has_vchasno_kasa_settings_table():
            return Response(
                {
                    "code": "VCHASNO_KASA_SCHEMA_NOT_READY",
                    "message": "Интеграция Вчасно.Каса еще не подготовлена. Примените миграции.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        settings = get_vchasno_kasa_settings()
        serializer = BackofficeVchasnoKasaSettingsSerializer(settings, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeVchasnoKasaTestConnectionAPIView(BackofficeAPIView):
    def post(self, request):
        payload = test_vchasno_kasa_connection()
        serializer = BackofficeVchasnoKasaConnectionCheckSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeVchasnoKasaReceiptListAPIView(BackofficeAPIView):
    def get(self, request):
        if not has_order_receipt_table():
            serializer = BackofficeVchasnoReceiptListSerializer({"count": 0, "results": []})
            return Response(serializer.data, status=status.HTTP_200_OK)
        queryset = (
            OrderReceipt.objects
            .filter(provider=OrderReceipt.PROVIDER_VCHASNO_KASA)
            .select_related("order")
            .order_by("-updated_at", "-created_at")[:20]
        )
        serializer = BackofficeVchasnoReceiptListSerializer({"count": len(queryset), "results": list(queryset)})
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeVchasnoKasaShiftStatusAPIView(BackofficeAPIView):
    def get(self, request):
        serializer = BackofficeVchasnoKasaShiftStatusSerializer(get_vchasno_shift_status())
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeVchasnoKasaOpenShiftAPIView(BackofficeAPIView):
    def post(self, request):
        try:
            payload = open_vchasno_shift(actor=request.user)
        except VchasnoKasaError as exc:
            return Response(exc.as_api_payload(), status=exc.status_code)
        serializer = BackofficeVchasnoKasaShiftStatusSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeVchasnoKasaCloseShiftAPIView(BackofficeAPIView):
    def post(self, request):
        try:
            payload = close_vchasno_shift(actor=request.user)
        except VchasnoKasaError as exc:
            return Response(exc.as_api_payload(), status=exc.status_code)
        serializer = BackofficeVchasnoKasaShiftStatusSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeOrderVchasnoKasaIssueAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order.objects.prefetch_related("items"), id=order_id)
        existing_summary = serialize_receipt_summary(order=order)
        already_exists = bool(existing_summary["can_open"])
        try:
            issue_order_receipt(order=order, actor=request.user)
        except VchasnoKasaError as exc:
            return Response(exc.as_api_payload(), status=exc.status_code)
        payload = {
            "receipt": serialize_receipt_summary(order=order),
            "already_exists": already_exists,
            "sync_performed": False,
        }
        serializer = BackofficeOrderReceiptActionSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeOrderVchasnoKasaSyncAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order.objects.prefetch_related("items"), id=order_id)
        try:
            sync_order_receipt(order=order, actor=request.user)
        except VchasnoKasaError as exc:
            return Response(exc.as_api_payload(), status=exc.status_code)
        payload = {
            "receipt": serialize_receipt_summary(order=order),
            "already_exists": True,
            "sync_performed": True,
        }
        serializer = BackofficeOrderReceiptActionSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeOrderVchasnoKasaOpenAPIView(BackofficeAPIView):
    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        try:
            receipt_url = get_open_receipt_url(order=order)
        except VchasnoKasaError as exc:
            return Response(exc.as_api_payload(), status=exc.status_code)
        if request.query_params.get("mode", "").strip().lower() == "json":
            return Response({"url": receipt_url}, status=status.HTTP_200_OK)
        return HttpResponseRedirect(receipt_url)
