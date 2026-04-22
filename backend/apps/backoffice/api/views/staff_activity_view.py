from __future__ import annotations

from rest_framework import serializers
from rest_framework.response import Response

from apps.backoffice.api.views._base import BackofficeAPIView
from apps.backoffice.selectors import build_backoffice_staff_activity_payload


class BackofficeStaffActivityQuerySerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=("manager", "operator"))
    days = serializers.IntegerField(required=False, min_value=1, max_value=90, default=14)


class BackofficeStaffActivityAPIView(BackofficeAPIView):
    required_capability = "backoffice.access"

    def get(self, request):
        serializer = BackofficeStaffActivityQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = build_backoffice_staff_activity_payload(
            role=serializer.validated_data["role"],
            days=serializer.validated_data.get("days", 14),
        )
        return Response(payload)
