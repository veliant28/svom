from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.commerce.api.serializers import CheckoutPreviewQuerySerializer, CheckoutSubmitSerializer, OrderSerializer
from apps.commerce.api.views.cart_views import _serialize_user_cart
from apps.commerce.services import build_checkout_preview, submit_checkout


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
