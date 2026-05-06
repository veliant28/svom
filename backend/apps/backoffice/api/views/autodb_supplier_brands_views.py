from __future__ import annotations

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.autodb.selectors.admin_supplier_brands import list_admin_supplier_brands
from apps.backoffice.permissions import IsStaffOrSuperuser


def _parse_positive_int(value, *, default: int, minimum: int = 1, maximum: int | None = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    parsed = max(parsed, minimum)
    if maximum is not None:
        parsed = min(parsed, maximum)
    return parsed


def _parse_is_active_flag(value) -> bool | None:
    normalized = str(value or "").strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    return None


class BackofficeAutoDbSupplierBrandListAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, IsStaffOrSuperuser]
    required_capability = "brands.view"

    def get(self, request):
        payload = list_admin_supplier_brands(
            q=str(request.query_params.get("q") or "").strip(),
            is_active=_parse_is_active_flag(request.query_params.get("is_active")),
            page=_parse_positive_int(request.query_params.get("page"), default=1),
            page_size=_parse_positive_int(request.query_params.get("page_size"), default=20, maximum=200),
        )
        return Response(payload)
