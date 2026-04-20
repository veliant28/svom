from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from apps.commerce.api.serializers import OrderSerializer
from apps.commerce.api.views.querysets import get_orders_queryset


class OrderListAPIView(ListAPIView):
    serializer_class = OrderSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return get_orders_queryset(user_id=self.request.user.id)


class OrderDetailAPIView(RetrieveAPIView):
    serializer_class = OrderSerializer
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_orders_queryset(user_id=self.request.user.id)
