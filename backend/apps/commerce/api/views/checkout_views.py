from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commerce.api.serializers import (
    CheckoutNovaPoshtaLookupQuerySerializer,
    CheckoutPromoApplySerializer,
    CheckoutPromoClearSerializer,
    CheckoutNovaPoshtaStreetLookupQuerySerializer,
    CheckoutNovaPoshtaWarehouseLookupQuerySerializer,
    CheckoutPreviewQuerySerializer,
    CheckoutSubmitSerializer,
    OrderSerializer,
)
from apps.commerce.api.views.cart_views import _serialize_user_cart
from apps.commerce.models import Order
from apps.commerce.services import (
    LoyaltyPromoValidationError,
    MonobankWebhookService,
    build_checkout_preview,
    build_selector_widget_init_payload,
    build_widget_init_payload,
    get_monobank_settings,
    get_order_payment,
    handle_liqpay_webhook,
    submit_checkout,
)
from apps.commerce.services.nova_poshta import NovaPoshtaLookupService, NovaPoshtaSenderProfileService
from apps.commerce.services.nova_poshta.errors import NovaPoshtaBusinessRuleError, NovaPoshtaIntegrationError


class CheckoutPreviewAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query_serializer = CheckoutPreviewQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        delivery_method = query_serializer.validated_data.get("delivery_method")
        promo_code = query_serializer.validated_data.get("promo_code")
        try:
            preview = build_checkout_preview(user=request.user, delivery_method=delivery_method, promo_code=promo_code)
        except LoyaltyPromoValidationError as exc:
            raise ValidationError(detail={"promo_code": str(exc.message), "promo_code_error": exc.code})

        return Response(_build_checkout_preview_response(request=request, preview=preview))


class CheckoutPromoApplyAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutPromoApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        promo_code = serializer.validated_data.get("promo_code")
        delivery_method = serializer.validated_data.get("delivery_method")
        try:
            preview = build_checkout_preview(user=request.user, delivery_method=delivery_method, promo_code=promo_code)
        except LoyaltyPromoValidationError as exc:
            raise ValidationError(detail={"promo_code": str(exc.message), "promo_code_error": exc.code})
        return Response(_build_checkout_preview_response(request=request, preview=preview))


class CheckoutPromoClearAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutPromoClearSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        delivery_method = serializer.validated_data.get("delivery_method")
        preview = build_checkout_preview(user=request.user, delivery_method=delivery_method)
        payload = _build_checkout_preview_response(request=request, preview=preview)
        payload["cleared"] = True
        return Response(payload)


class CheckoutSubmitAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = submit_checkout(
                user=request.user,
                payload=serializer.validated_data,
                monobank_webhook_url=request.build_absolute_uri("/api/commerce/payments/monobank/webhook/"),
                monobank_redirect_url=request.build_absolute_uri("/checkout"),
                liqpay_server_url=request.build_absolute_uri("/api/commerce/payments/liqpay/webhook/"),
                liqpay_result_url=request.build_absolute_uri("/checkout"),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=exc.message_dict)

        response_data = OrderSerializer(order, context={"request": request}).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class CheckoutOrderMonobankWidgetAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id, user_id=request.user.id)
        payment = get_order_payment(order)
        if payment.provider != payment.PROVIDER_MONOBANK:
            return Response({"detail": "This order does not use Monobank payment."}, status=status.HTTP_400_BAD_REQUEST)

        widget = build_widget_init_payload(payment=payment)
        widget_error = ""
        if not widget:
            settings = get_monobank_settings()
            if not (settings.widget_key_id or "").strip():
                widget_error = "Monobank widget keyId is not configured."
            elif not (settings.widget_private_key or "").strip():
                widget_error = "Monobank widget private key is not configured."
            else:
                widget_error = "Failed to initialize MonoPay widget. Check widget private key format (ECDSA P-256 PEM) and OpenSSL availability."

        return Response(
            {
                "order_id": str(order.id),
                "invoice_id": payment.monobank_invoice_id,
                "page_url": payment.monobank_page_url,
                "widget": (
                    {
                        "key_id": widget.key_id,
                        "request_id": widget.request_id,
                        "signature": widget.signature,
                        "payload_base64": widget.payload_base64,
                    }
                    if widget
                    else None
                ),
                "widget_error": widget_error,
            }
        )


class CheckoutMonobankSelectorWidgetAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        widget = build_selector_widget_init_payload(user=request.user)
        widget_error = ""
        if not widget:
            settings = get_monobank_settings()
            if not (settings.widget_key_id or "").strip():
                widget_error = "Monobank widget keyId is not configured."
            elif not (settings.widget_private_key or "").strip():
                widget_error = "Monobank widget private key is not configured."
            else:
                widget_error = "Failed to initialize MonoPay selector widget. Check widget private key format (ECDSA P-256 PEM) and OpenSSL availability."

        return Response(
            {
                "widget": (
                    {
                        "key_id": widget.key_id,
                        "request_id": widget.request_id,
                        "signature": widget.signature,
                        "payload_base64": widget.payload_base64,
                    }
                    if widget
                    else None
                ),
                "widget_error": widget_error,
            }
        )


class MonobankWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"ok": True})

    def post(self, request):
        body = request.body or b""
        x_sign = request.headers.get("X-Sign", "")

        service = MonobankWebhookService()
        try:
            payment, applied = service.handle(body=body, x_sign=x_sign)
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else getattr(exc, "messages", [str(exc)])
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "ok": True,
                "order_id": str(payment.order_id),
                "invoice_id": payment.monobank_invoice_id,
                "applied": applied,
            }
        )


class LiqPayWebhookAPIView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        data = request.data.get("data", "")
        signature = request.data.get("signature", "")

        try:
            payment, applied = handle_liqpay_webhook(
                data=str(data or ""),
                signature=str(signature or ""),
            )
        except DjangoValidationError as exc:
            detail = exc.message_dict if hasattr(exc, "message_dict") else getattr(exc, "messages", [str(exc)])
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "ok": True,
                "order_id": str(payment.order_id),
                "liqpay_order_id": payment.liqpay_order_id,
                "applied": applied,
            }
        )


class CheckoutNovaPoshtaSettlementsLookupAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutNovaPoshtaLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = _resolve_checkout_nova_poshta_lookup_service()
        if isinstance(service, Response):
            return service

        try:
            rows = service.search_settlements(
                query=serializer.validated_data.get("query", ""),
                locale=serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class CheckoutNovaPoshtaWarehousesLookupAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        query_serializer = CheckoutNovaPoshtaWarehouseLookupQuerySerializer(data=request.data)
        query_serializer.is_valid(raise_exception=True)
        service = _resolve_checkout_nova_poshta_lookup_service()
        if isinstance(service, Response):
            return service

        try:
            rows = service.get_warehouses(
                city_ref=query_serializer.validated_data.get("city_ref", ""),
                query=query_serializer.validated_data.get("query", ""),
                locale=query_serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


class CheckoutNovaPoshtaStreetsLookupAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutNovaPoshtaStreetLookupQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service = _resolve_checkout_nova_poshta_lookup_service()
        if isinstance(service, Response):
            return service

        try:
            rows = service.search_streets(
                settlement_ref=serializer.validated_data["settlement_ref"],
                query=serializer.validated_data.get("query", ""),
                locale=serializer.validated_data.get("locale", "uk"),
            )
        except NovaPoshtaIntegrationError as exc:
            return _nova_poshta_error_response(exc)

        return Response({"results": rows})


def _resolve_checkout_nova_poshta_lookup_service() -> NovaPoshtaLookupService | Response:
    sender_service = NovaPoshtaSenderProfileService()
    try:
        sender = sender_service.get_default_active_profile()
    except NovaPoshtaBusinessRuleError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return NovaPoshtaLookupService(api_token=sender.api_token)


def _nova_poshta_error_response(exc: NovaPoshtaIntegrationError) -> Response:
    context = exc.context
    return Response(
        {
            "detail": str(exc),
            "errors": context.errors,
            "warnings": context.warnings,
            "info": context.info,
            "errorCodes": context.error_codes,
            "warningCodes": context.warning_codes,
            "infoCodes": context.info_codes,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _build_checkout_preview_response(*, request, preview) -> dict:
    return {
        "cart": _serialize_user_cart(request=request),
        "checkout_preview": {
            "items_count": preview.items_count,
            "subtotal": preview.subtotal,
            "delivery_fee": preview.delivery_fee,
            "discount_total": preview.discount_total,
            "total": preview.total,
            "promo": preview.promo,
            "warnings": preview.warnings,
        },
    }
