from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.backoffice.api.serializers import (
    BackofficeLoyaltyCustomerLookupSerializer,
    BackofficeLoyaltyIssueSerializer,
    BackofficeLoyaltyPromoSerializer,
    BackofficeLoyaltyStaffStatsSerializer,
)
from apps.backoffice.api.views._base import BackofficeAPIView
from apps.commerce.selectors import (
    list_loyalty_daily_issuance,
    list_loyalty_staff_stats,
    list_recent_loyalty_issuances,
    search_loyalty_customers,
)
from apps.commerce.services import issue_loyalty_promo, serialize_loyalty_promo_for_ui

User = get_user_model()


class BackofficeLoyaltyIssueAPIView(BackofficeAPIView):
    required_capability = "loyalty.issue"

    def post(self, request):
        serializer = BackofficeLoyaltyIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        customer = User.objects.filter(id=serializer.validated_data["customer_id"], is_active=True).first()
        if customer is None:
            raise ValidationError({"customer_id": "Customer not found."})

        try:
            promo = issue_loyalty_promo(
                customer=customer,
                issued_by=request.user,
                reason=serializer.validated_data["reason"],
                discount_type=serializer.validated_data["discount_type"],
                discount_percent=serializer.validated_data["discount_percent"],
                expires_at=serializer.validated_data.get("expires_at"),
                usage_limit=serializer.validated_data.get("usage_limit", 1),
            )
        except DjangoValidationError as exc:
            raise ValidationError(detail=exc.message_dict)

        payload = serialize_loyalty_promo_for_ui(promo=promo)
        return Response(BackofficeLoyaltyPromoSerializer(payload).data, status=status.HTTP_201_CREATED)


class BackofficeLoyaltyIssuanceListAPIView(BackofficeAPIView):
    required_capability = "loyalty.issue"

    def get(self, request):
        raw_limit = request.query_params.get("limit", "25")
        try:
            limit = int(raw_limit)
        except ValueError:
            limit = 25
        promos = list_recent_loyalty_issuances(limit=max(1, min(limit, 200)))
        payload = [serialize_loyalty_promo_for_ui(promo=promo) for promo in promos]
        return Response(BackofficeLoyaltyPromoSerializer(payload, many=True).data)


class BackofficeLoyaltyStatsAPIView(BackofficeAPIView):
    required_capability = "loyalty.issue"

    def get(self, request):
        raw_days = request.query_params.get("days", "14")
        try:
            days = int(raw_days)
        except ValueError:
            days = 14

        staff_rows = list_loyalty_staff_stats()
        chart_rows = list_loyalty_daily_issuance(days=max(1, min(days, 90)))

        return Response(
            {
                "staff": BackofficeLoyaltyStaffStatsSerializer(staff_rows, many=True).data,
                "chart": {
                    "by_day": chart_rows,
                },
            }
        )


class BackofficeLoyaltyCustomerLookupAPIView(BackofficeAPIView):
    required_capability = "loyalty.issue"

    def get(self, request):
        query = str(request.query_params.get("query", "") or "")
        rows = search_loyalty_customers(query=query, limit=25)
        return Response({"results": BackofficeLoyaltyCustomerLookupSerializer(rows, many=True).data})
