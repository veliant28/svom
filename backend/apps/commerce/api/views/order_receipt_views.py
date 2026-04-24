from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response

from apps.commerce.api.views.querysets import get_orders_queryset
from apps.commerce.services.vchasno_kasa import VchasnoKasaError, get_open_receipt_url


class AccountOrderReceiptOpenAPIView(GenericAPIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return get_orders_queryset(user_id=self.request.user.id)

    def get(self, request, order_id):
        order = get_object_or_404(self.get_queryset(), id=order_id)
        try:
            receipt_url = get_open_receipt_url(order=order)
        except VchasnoKasaError as exc:
            return Response(exc.as_api_payload(), status=exc.status_code)
        if request.query_params.get("mode", "").strip().lower() == "json":
            return Response({"url": receipt_url}, status=status.HTTP_200_OK)
        return HttpResponseRedirect(receipt_url)
