from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import DestroyAPIView, ListAPIView

from apps.catalog.models import Product
from apps.commerce.api.serializers import WishlistAddSerializer, WishlistItemSerializer
from apps.commerce.api.views.querysets import get_wishlist_items_queryset
from apps.commerce.models import WishlistItem


class WishlistListAPIView(ListAPIView):
    serializer_class = WishlistItemSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return get_wishlist_items_queryset(user_id=self.request.user.id)


class WishlistItemCreateAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = WishlistAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = get_object_or_404(Product.objects.filter(is_active=True), id=serializer.validated_data["product_id"])

        item, _ = WishlistItem.objects.get_or_create(user=request.user, product=product)

        response_data = WishlistItemSerializer(
            item,
            context={"request": request},
        ).data
        return Response(response_data, status=status.HTTP_201_CREATED)


class WishlistItemDeleteAPIView(DestroyAPIView):
    serializer_class = WishlistItemSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "item_id"

    def get_queryset(self):
        return get_wishlist_items_queryset(user_id=self.request.user.id)
