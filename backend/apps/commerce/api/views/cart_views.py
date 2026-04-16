from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product
from apps.commerce.api.serializers import CartItemCreateSerializer, CartItemQuantityUpdateSerializer, CartSerializer
from apps.commerce.api.views.querysets import get_cart_queryset
from apps.commerce.models import CartItem
from apps.commerce.services import add_product_to_cart, get_or_create_user_cart, remove_cart_item, set_cart_item_quantity


def _serialize_user_cart(*, request):
    get_or_create_user_cart(request.user)
    cart = get_cart_queryset(user_id=request.user.id).first()
    assert cart is not None
    return CartSerializer(cart, context={"request": request}).data


class CartRetrieveAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(_serialize_user_cart(request=request))


class CartItemCreateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = get_object_or_404(Product.objects.filter(is_active=True), id=serializer.validated_data["product_id"])
        add_product_to_cart(
            user=request.user,
            product=product,
            quantity=serializer.validated_data["quantity"],
        )

        return Response(_serialize_user_cart(request=request), status=status.HTTP_201_CREATED)


class CartItemUpdateDeleteAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        serializer = CartItemQuantityUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = get_object_or_404(
            CartItem.objects.select_related("cart"),
            id=item_id,
            cart__user=request.user,
        )
        set_cart_item_quantity(item=item, quantity=serializer.validated_data["quantity"])
        return Response(_serialize_user_cart(request=request))

    def delete(self, request, item_id):
        item = get_object_or_404(
            CartItem.objects.select_related("cart"),
            id=item_id,
            cart__user=request.user,
        )
        remove_cart_item(item=item)
        return Response(_serialize_user_cart(request=request), status=status.HTTP_200_OK)
