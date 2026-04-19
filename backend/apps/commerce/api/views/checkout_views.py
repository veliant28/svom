from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commerce.api.serializers import (
    CheckoutNovaPoshtaLookupQuerySerializer,
    CheckoutNovaPoshtaStreetLookupQuerySerializer,
    CheckoutNovaPoshtaWarehouseLookupQuerySerializer,
    CheckoutPreviewQuerySerializer,
    CheckoutSubmitSerializer,
    OrderSerializer,
)
from apps.commerce.api.views.cart_views import _serialize_user_cart
from apps.commerce.services import build_checkout_preview, submit_checkout
from apps.commerce.services.nova_poshta import NovaPoshtaLookupService, NovaPoshtaSenderProfileService
from apps.commerce.services.nova_poshta.errors import NovaPoshtaBusinessRuleError, NovaPoshtaIntegrationError


class CheckoutPreviewAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query_serializer = CheckoutPreviewQuerySerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)

        delivery_method = query_serializer.validated_data.get("delivery_method")
        preview = build_checkout_preview(user=request.user, delivery_method=delivery_method)

        return Response(
            {
                "cart": _serialize_user_cart(request=request),
                "checkout_preview": {
                    "items_count": preview.items_count,
                    "subtotal": preview.subtotal,
                    "delivery_fee": preview.delivery_fee,
                    "total": preview.total,
                    "warnings": preview.warnings,
                },
            }
        )


class CheckoutSubmitAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            order = submit_checkout(user=request.user, payload=serializer.validated_data)
        except DjangoValidationError as exc:
            raise ValidationError(detail=exc.message_dict)

        response_data = OrderSerializer(order, context={"request": request}).data
        return Response(response_data, status=status.HTTP_201_CREATED)


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
