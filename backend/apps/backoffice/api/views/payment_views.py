from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.backoffice.api.serializers import (
    BackofficeMonobankPaymentActionResponseSerializer,
    BackofficeMonobankPaymentActionSerializer,
    BackofficeOrderPaymentSerializer,
    MonobankConnectionCheckSerializer,
    MonobankCurrencyResponseSerializer,
    MonobankSettingsSerializer,
    NovaPaySettingsSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.commerce.models import Order
from apps.commerce.services.monobank import (
    MonobankApiError,
    cancel_invoice_payment,
    finalize_invoice_hold,
    get_invoice_fiscal_checks,
    get_currency_rates,
    get_monobank_settings,
    get_order_payment,
    get_urls_for_request,
    refresh_invoice_status,
    remove_invoice,
    test_monobank_connection,
)
from apps.commerce.services.novapay import get_novapay_settings


class BackofficeMonobankSettingsAPIView(BackofficeAPIView):
    def get(self, request):
        settings = get_monobank_settings()
        urls = get_urls_for_request(request=request)
        serializer = MonobankSettingsSerializer(settings, context=urls)
        return Response(serializer.data)

    def patch(self, request):
        settings = get_monobank_settings()
        urls = get_urls_for_request(request=request)
        serializer = MonobankSettingsSerializer(settings, data=request.data, partial=True, context=urls)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BackofficeMonobankConnectionTestAPIView(BackofficeAPIView):
    def post(self, request):
        result = test_monobank_connection()
        serializer = MonobankConnectionCheckSerializer(result)
        return Response(serializer.data, status=status.HTTP_200_OK)


class BackofficeMonobankCurrencyAPIView(BackofficeAPIView):
    def get(self, request):
        force_refresh = request.query_params.get("refresh", "").strip().lower() in {"1", "true", "yes"}
        payload = get_currency_rates(force_refresh=force_refresh)
        serializer = MonobankCurrencyResponseSerializer(payload)
        return Response(serializer.data)


class BackofficeNovaPaySettingsAPIView(BackofficeAPIView):
    def get(self, request):
        settings = get_novapay_settings()
        serializer = NovaPaySettingsSerializer(settings)
        return Response(serializer.data)

    def patch(self, request):
        settings = get_novapay_settings()
        serializer = NovaPaySettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class BackofficeOrderPaymentRefreshAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        payment = get_order_payment(order)

        if payment.provider == payment.PROVIDER_MONOBANK and payment.monobank_invoice_id:
            refresh_invoice_status(payment=payment)
            payment.refresh_from_db()

        serializer = BackofficeOrderPaymentSerializer(payment)
        return Response(serializer.data)


class BackofficeOrderPaymentMonobankActionAPIView(BackofficeAPIView):
    def post(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        payment = get_order_payment(order)

        serializer = BackofficeMonobankPaymentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        amount_minor = serializer.validated_data.get("amount")

        provider_result: dict = {}
        fiscal_checks: list[dict] = []

        try:
            if action == "refresh":
                refresh_invoice_status(payment=payment)
                payment.refresh_from_db()
            elif action == "cancel":
                provider_result = cancel_invoice_payment(payment=payment, amount_minor=amount_minor)
                payment.refresh_from_db()
            elif action == "remove":
                provider_result = remove_invoice(payment=payment)
                payment.refresh_from_db()
            elif action == "finalize":
                provider_result = finalize_invoice_hold(payment=payment, amount_minor=amount_minor)
                payment.refresh_from_db()
            elif action == "fiscal_checks":
                fiscal_checks = get_invoice_fiscal_checks(payment=payment)
        except (DjangoValidationError, MonobankApiError) as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        response_serializer = BackofficeMonobankPaymentActionResponseSerializer(
            {
                "action": action,
                "payment": payment,
                "provider_result": provider_result,
                "fiscal_checks": fiscal_checks,
            }
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)
