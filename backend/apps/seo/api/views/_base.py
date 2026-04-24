from __future__ import annotations

from collections.abc import Iterable

from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.backoffice.permissions import IsStaffOrSuperuser


SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class SeoBackofficePermission(IsStaffOrSuperuser):
    def _resolve_required_capabilities(self, *, request, view) -> tuple[str, ...]:
        use_read_caps = str(request.method or "").upper() in SAFE_METHODS
        many_attr = "required_capabilities_read" if use_read_caps else "required_capabilities_write"
        one_attr = "required_capability_read" if use_read_caps else "required_capability_write"

        explicit_many = getattr(view, many_attr, None)
        if isinstance(explicit_many, Iterable) and not isinstance(explicit_many, (str, bytes)):
            values = [str(value or "").strip() for value in explicit_many if str(value or "").strip()]
            if values:
                return tuple(values)

        explicit_one = str(getattr(view, one_attr, "") or "").strip()
        if explicit_one:
            return (explicit_one,)

        if use_read_caps:
            return ("seo.view",)
        return ("seo.manage",)


class SeoBackofficeAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, SeoBackofficePermission]
    required_capability_read = "seo.view"
    required_capability_write = "seo.manage"
