from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from apps.backoffice.api.serializers import BackofficeOrderHistoryEventSerializer, BackofficeWaybillHistoryEventSerializer
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.commerce.models import Order, OrderEvent, OrderNovaPoshtaWaybillEvent


class OrderHistoryAPIView(BackofficeAPIView):
    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        events = OrderEvent.objects.filter(order=order).select_related("created_by").order_by("-created_at")
        return Response({"results": BackofficeOrderHistoryEventSerializer(events, many=True).data})


class OrderWaybillHistoryAPIView(BackofficeAPIView):
    def get(self, request, order_id):
        order = get_object_or_404(Order, id=order_id)
        events = (
            OrderNovaPoshtaWaybillEvent.objects.filter(order=order)
            .select_related("created_by", "waybill")
            .order_by("-created_at")
        )
        return Response({"results": BackofficeWaybillHistoryEventSerializer(events, many=True).data})
